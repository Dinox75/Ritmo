"""Exercise the packaged study atmosphere using synthetic, disposable Windows data."""

import argparse
import ctypes
import io
import json
import math
import os
import tempfile
import time
import wave
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from qa_packaged_windows import EDGE, launch, quit_and_verify


def seconds(label):
    hours, minutes, remaining = map(int, label.split(":"))
    return hours * 3600 + minutes * 60 + remaining


def sample_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        samples = bytearray()
        for index in range(22050):
            value = int(math.sin(2 * math.pi * 220 * index / 22050) * 6000)
            samples.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(samples)
    return stream.getvalue()


def native_window_titles(pid):
    titles = []
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def collect(handle, _):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(handle):
            length = user32.GetWindowTextLengthW(handle)
            if length:
                buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(handle, buffer, length + 1)
                titles.append(buffer.value)
        return True

    user32.EnumWindows(collect, None)
    return titles


def assert_native_window(pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        titles = native_window_titles(pid)
        if any(title.startswith("Ritmo") for title in titles):
            return
        time.sleep(.2)
    raise AssertionError(f"Janela nativa do Ritmo não apareceu para PID {pid}")


def screenshots(page, folder, report):
    page.locator('nav a[data-view-target="configuracoes"]').click()
    expect(page.locator("#view-configuracoes")).to_be_visible()
    page.locator("#experience-brightness").press("Home")
    brightness = page.locator("#experience-brightness").input_value()
    assert brightness == "85", {"brightness": brightness,
                                "min": page.locator("#experience-brightness").get_attribute("min"),
                                "view": page.evaluate("document.querySelector('.view:not([hidden])')?.id")}
    for width, height in ((390, 844), (1366, 850), (1920, 1080)):
        page.set_viewport_size({"width": width, "height": height})
        for view in ("estudar", "configuracoes"):
            page.locator(f'nav a[data-view-target="{view}"]').click()
            expect(page.locator("#view-" + view)).to_be_visible()
            page.evaluate("scrollTo(0, 0)")
            metrics = page.evaluate("""() => ({viewport: innerWidth,
              document: document.documentElement.scrollWidth,
              theme: document.documentElement.dataset.theme})""")
            if metrics["document"] > width:
                raise AssertionError(f"Rolagem horizontal em {view}, {width}px: {metrics}")
            target = folder / f"ritmo-pr3-{width}-{view}.png"
            page.screenshot(path=str(target), full_page=width == 390)
            report["screens"].append({"width": width, "view": view, "metrics": metrics,
                                       "image": target.name})
            fixed = page.evaluate("""() => {
              scrollTo({top: 0, behavior: 'instant'});
              const nav = document.querySelector(innerWidth <= 780 ? '.topnav' : '.topbar');
              const before = nav.getBoundingClientRect().top;
              scrollTo({top: 400, behavior: 'instant'});
              return {before, after: nav.getBoundingClientRect().top, scrolled: scrollY,
                position: getComputedStyle(nav).position,
                dim: getComputedStyle(document.documentElement, '::after').backgroundColor,
                bodyFilter: getComputedStyle(document.body).filter};
            }""")
            assert fixed["scrolled"] > 0, (width, view, fixed)
            assert fixed["position"] == "fixed", (width, view, fixed)
            assert abs(fixed["before"] - fixed["after"]) <= 1, (width, view, fixed)
            assert fixed["bodyFilter"] == "none", (width, view, fixed)
            assert fixed["dim"] != "rgba(0, 0, 0, 0)", (width, view, fixed)
            scrolled = folder / f"ritmo-pr3-{width}-{view}-scrolled.png"
            page.screenshot(path=str(scrolled), full_page=False)
            report["screens"][-1]["fixed_navigation"] = fixed
            report["screens"][-1]["scrolled_image"] = scrolled.name
            page.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    page.locator('nav a[data-view-target="configuracoes"]').click()
    page.locator("#experience-brightness").press("End")
    report["checks"].append("navegação fixa após rolagem em Estudar e Configurações a 85%, nas três larguras")
    page.set_viewport_size({"width": 1366, "height": 850})
    page.locator('nav a[data-view-target="estudar"]').click()


def run(executable, shots):
    report = {"packaged": True, "screens": [], "checks": []}
    with tempfile.TemporaryDirectory(prefix="ritmo-atmosphere-qa-", ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        data = root / "Ritmo"
        data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        config = json.loads((Path(__file__).resolve().parents[1] / "config" / "config.json").read_text(encoding="utf-8"))
        config["tutor"]["model_root"] = str(root / "models-not-installed")
        (data / "config.json").write_text(json.dumps(config), encoding="utf-8")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(EDGE), headless=True)
            process = None
            page = None
            try:
                process, port = launch(executable, root)
                assert_native_window(process.pid)
                report["checks"].append("janela nativa WebView2 visível")
                base = f"http://127.0.0.1:{port}"
                page = browser.new_page(viewport={"width": 1366, "height": 850}, reduced_motion="reduce")
                page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base)
                expect(page.locator("#view-inicio")).to_be_visible()
                page.locator('nav a[data-view-target="plano"]').click()
                page.locator("#subject-name").fill("Matéria sintética")
                page.locator("#subject-submit").click()
                expect(page.locator("#subjects-list")).to_contain_text("Matéria sintética")
                page.locator('nav a[data-view-target="estudar"]').click()
                page.locator("#subject-select").select_option(index=1)
                page.locator("#start-btn").click()
                expect(page.locator("#session-panel")).to_be_visible()
                first = seconds(page.locator("#timer").inner_text())
                time.sleep(2.2)
                next_value = seconds(page.locator("#timer").inner_text())
                assert next_value > first, (first, next_value)
                report["checks"].append("cronômetro de foco avança")
                screenshots(page, shots, report)
                contrast = page.evaluate("""() => {
                  const rgb = value => (value.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
                  const luminance = value => rgb(value).map(n => n / 255).map(n =>
                    n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4)
                    .reduce((sum, n, i) => sum + n * [.2126, .7152, .0722][i], 0);
                  const ratio = (a, b) => {
                    const x = luminance(a), y = luminance(b);
                    return (Math.max(x, y) + .05) / (Math.min(x, y) + .05);
                  };
                  const color = selector => getComputedStyle(document.querySelector(selector)).color;
                  const background = selector => getComputedStyle(document.querySelector(selector)).backgroundColor;
                  return {legend: ratio(color('#tutor-materials legend'), background('#tutor-card')),
                    settingsLabel: ratio(color('.experience-settings .number-grid label'), background('.experience-settings')),
                    historyBackground: background('.tutor-history')};
                }""")
                assert contrast["legend"] >= 4.5, contrast
                assert contrast["settingsLabel"] >= 4.5, contrast
                assert contrast["historyBackground"] != "rgb(244, 247, 241)", contrast
                report["contrast"] = contrast
                report["checks"].append("contraste de rótulos no tema escuro")

                assert page.evaluate("audioNode === null && (!localAudio || localAudio.paused)")
                for mode in ("rain", "brown"):
                    page.locator("#focus-sound").select_option(mode)
                    page.locator("#focus-play").click()
                    expect(page.locator("#focus-play")).to_have_text("Pausar som")
                    assert page.evaluate("audioContext?.state === 'running' && !!audioNode?.source && audioNode.source.loop")
                    page.locator("#focus-volume").focus()
                    page.keyboard.press("End")
                    assert abs(page.evaluate("audioNode.gain.gain.value") - .18) < .001
                    page.locator("#focus-play").click()
                    expect(page.locator("#focus-play")).to_have_text("Reproduzir")
                    assert page.evaluate("audioNode === null")
                    report["checks"].append(mode + " inicia, ajusta volume e para")

                page.locator("#focus-file").set_input_files({"name": "som-sintetico.wav",
                    "mimeType": "audio/wav", "buffer": sample_wav()})
                page.locator("#focus-sound").select_option("file")
                page.locator("#focus-play").click()
                expect(page.locator("#focus-play")).to_have_text("Pausar som")
                assert page.evaluate("localAudio && !localAudio.paused && localAudio.loop")
                page.locator("#focus-volume").focus()
                page.keyboard.press("Home")
                assert page.evaluate("localAudio.volume === 0")
                report["checks"].append("arquivo WAV local toca em loop e respeita volume zero")

                page.locator("#pause-btn").click()
                expect(page.locator("#session-status")).to_have_text("Em pausa")
                assert page.evaluate("localAudio.paused")
                stopped = seconds(page.locator("#timer").inner_text())
                time.sleep(1.3)
                assert seconds(page.locator("#timer").inner_text()) == stopped
                page.locator("#pause-btn").click()
                expect(page.locator("#session-status")).to_have_text("Em foco")
                page.wait_for_function("localAudio && !localAudio.paused", timeout=5000)
                report["checks"].append("pausa congela foco e áudio; retomada continua ambos")

                page.locator('nav a[data-view-target="configuracoes"]').click()
                page.locator("#experience-theme").select_option("light")
                page.locator("#experience-reminders").check()
                page.locator("#experience-break").fill("5")
                page.locator("#experience-excess").fill("5")
                page.locator("#experience-completion").check()
                page.locator("#experience-form button[type=submit]").click()
                expect(page.locator("#message")).to_contain_text("Ambiente de estudo salvo")
                assert page.evaluate("document.documentElement.dataset.theme === 'light'")
                assert json.loads((data / "config.json").read_text(encoding="utf-8"))["experience"]["reminders_enabled"]
                report["checks"].append("tema e lembretes salvos em configuração temporária")

                page.locator('nav a[data-view-target="estudar"]').click()
                page.evaluate("""() => { const real = Date.now; Date.now = () => real() + 301000;
                  try { tick(); } finally { Date.now = real; } }""")
                expect(page.locator("#focus-reminder")).to_be_visible()
                expect(page.locator("#focus-reminder-text")).to_contain_text("bloco de foco terminou")
                expect(page.locator("#session-status")).to_have_text("Em foco")
                page.locator("#focus-reminder-dismiss").click()
                page.evaluate("""() => { const real = Date.now; Date.now = () => real() + 661000;
                  try { tick(); } finally { Date.now = real; } }""")
                expect(page.locator("#focus-reminder-text")).to_contain_text("tempo de foco planejado")
                page.locator("#focus-reminder-pause").click()
                expect(page.locator("#session-status")).to_have_text("Em pausa")
                report["checks"].append("lembretes de pausa e excesso; só o botão pausa")

                quit_and_verify(page, process, port)
                process = None
                page.close()
                process, port = launch(executable, root)
                assert_native_window(process.pid)
                base = f"http://127.0.0.1:{port}"
                page = browser.new_page(viewport={"width": 1366, "height": 850}, reduced_motion="reduce")
                page.goto(base)
                expect(page.locator("#view-estudar")).to_be_visible()
                expect(page.locator("#session-status")).to_have_text("Em pausa")
                assert page.evaluate("document.documentElement.dataset.theme === 'light'")
                report["checks"].append("janela reaberta com sessão pausada e tema salvo")

                page.locator("#pause-btn").click()
                expect(page.locator("#session-status")).to_have_text("Em foco")
                page.evaluate("""() => { window.__chimes = 0;
                  const original = AudioContext.prototype.createOscillator;
                  AudioContext.prototype.createOscillator = function(...args) {
                    window.__chimes++; return original.apply(this, args);
                  }; }""")
                page.locator("#finish-btn").click()
                expect(page.locator("#session-summary")).to_be_visible()
                page.wait_for_function("window.__chimes === 2", timeout=5000)
                assert page.evaluate("!audioNode && (!localAudio || localAudio.paused)")
                report["checks"].append("conclusão mostra resumo, para áudio e gera dois toques")
                assert not errors, errors
                quit_and_verify(page, process, port)
                process = None
                return report
            finally:
                if page:
                    page.close()
                browser.close()
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("screenshots", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    outcome = run(args.executable.resolve(), args.screenshots.resolve())
    args.report.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("QA do ambiente empacotado:", ", ".join(outcome["checks"]), flush=True)


if __name__ == "__main__":
    main()
