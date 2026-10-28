"""Measure packaged Ritmo audio at the Windows physical speaker loopback."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import sounddevice as sd
from playwright.sync_api import expect, sync_playwright

from qa_packaged_windows import launch, quit_and_verify
from qa_study_atmosphere_packaged import sample_wav

REPO = Path(__file__).resolve().parents[1]


def level(device, seconds=1.4):
    rate = 48000
    samples = sd.rec(round(rate * seconds), samplerate=rate, channels=2,
                     device=device, dtype="float32")
    sd.wait()
    mono = samples.mean(axis=1).astype("float64")
    rms = float(np.sqrt(np.mean(mono * mono)))
    peak = float(np.max(np.abs(mono)))
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    frequencies = np.fft.rfftfreq(len(mono), 1 / rate)
    dominant = float(frequencies[np.argmax(spectrum[1:]) + 1])
    low = float(np.sum(spectrum[(frequencies >= 30) & (frequencies < 500)] ** 2))
    high = float(np.sum(spectrum[(frequencies >= 500) & (frequencies < 5000)] ** 2))
    return {"rms": rms, "peak": peak, "dominant_hz": dominant,
            "low_high_ratio": low / max(high, 1e-15)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--loopback-input", type=int, required=True)
    args = parser.parse_args()
    default_output = sd.query_devices(sd.default.device[1])
    capture = sd.query_devices(args.loopback_input)
    if "Virtual" in default_output["name"] or "CABLE" in default_output["name"]:
        raise RuntimeError("Saída padrão é virtual; selecione alto-falantes físicos")
    if capture["max_input_channels"] < 2:
        raise RuntimeError("Entrada de mixagem estéreo não disponível")
    if not any(name in capture["name"].casefold() for name in ("mixagem estéreo", "stereo mix")):
        raise RuntimeError("A captura precisa ser a mixagem estéreo, não um microfone")
    with args.executable.open("rb") as stream:
        package_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"package_sha256": package_hash, "speaker": default_output["name"],
              "capture": capture["name"], "sample_rate": 48000, "modes": {}}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        debug_port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="ritmo-speaker-qa-", ignore_cleanup_errors=True) as folder:
        root = Path(folder)
        data = root / "Ritmo"
        data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        config = json.loads((REPO / "config" / "config.json").read_text(encoding="utf-8"))
        config["tutor"]["model_root"] = str(root / "models-not-installed")
        (data / "config.json").write_text(json.dumps(config), encoding="utf-8")
        old = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS")
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
            f"--remote-debugging-port={debug_port} --remote-debugging-address=127.0.0.1"
        )
        process = None
        browser = None
        page = None
        try:
            process, app_port = launch(args.executable.resolve(), root)
            if old is None:
                os.environ.pop("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", None)
            else:
                os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = old
            with sync_playwright() as playwright:
                browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
                pages = [candidate for context in browser.contexts for candidate in context.pages
                         if candidate.url.startswith(f"http://127.0.0.1:{app_port}")]
                if len(pages) != 1:
                    raise RuntimeError(f"Esperada uma página nativa do Ritmo, encontradas {len(pages)}")
                page = pages[0]
                expect(page.locator("#view-inicio")).to_be_visible()
                page.locator('nav a[data-view-target="plano"]').click()
                page.locator("#subject-name").fill("Matéria sintética")
                page.locator("#subject-submit").click()
                expect(page.locator("#subjects-list")).to_contain_text("Matéria sintética")
                page.locator('nav a[data-view-target="estudar"]').click()
                page.locator("#subject-select").select_option(index=1)
                page.locator("#start-btn").click()
                expect(page.locator("#session-panel")).to_be_visible()
                page.locator("#focus-volume").focus()
                page.keyboard.press("End")

                report["baseline"] = level(args.loopback_input)
                for mode in ("rain", "brown", "file"):
                    if mode == "file":
                        page.locator("#focus-file").set_input_files({
                            "name": "som-sintetico.wav", "mimeType": "audio/wav", "buffer": sample_wav()})
                    page.locator("#focus-sound").select_option(mode)
                    page.locator("#focus-play").click()
                    expect(page.locator("#focus-play")).to_have_text("Pausar som")
                    page.wait_for_timeout(300)
                    active = level(args.loopback_input)
                    page.locator("#focus-play").click()
                    expect(page.locator("#focus-play")).to_have_text("Reproduzir")
                    page.wait_for_timeout(700)
                    stopped = level(args.loopback_input, .6)
                    report["modes"][mode] = {"active": active, "stopped": stopped}
                    print(mode, "active", active["rms"], "stopped", stopped["rms"], flush=True)
                    threshold = max(.0005, report["baseline"]["rms"] * 3,
                                    stopped["rms"] * 3)
                    if active["rms"] <= threshold:
                        raise AssertionError(f"{mode}: sinal não confirmado nos alto-falantes: {report['modes'][mode]}")
                if not 210 <= report["modes"]["file"]["active"]["dominant_hz"] <= 230:
                    raise AssertionError("WAV sintético não mostrou frequência de 220 Hz")
                if (report["modes"]["brown"]["active"]["low_high_ratio"] <=
                        5 * report["modes"]["rain"]["active"]["low_high_ratio"]):
                    raise AssertionError("Ruído marrom não apresentou predominância de graves")
                quit_and_verify(page, process, app_port)
                process = None
                browser.close()
                browser = None
        except Exception:
            print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
            raise
        finally:
            if old is None:
                os.environ.pop("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", None)
            else:
                os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = old
            if process and process.poll() is None:
                if "app_port" in locals():
                    try:
                        urllib.request.urlopen(urllib.request.Request(
                            f"http://127.0.0.1:{app_port}/api/app/quit", data=b"{}",
                            method="POST"), timeout=3).close()
                    except OSError:
                        pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Saída física confirmada:", ", ".join(
        f"{mode} RMS={result['active']['rms']:.5f}"
        for mode, result in report["modes"].items()))


if __name__ == "__main__":
    main()
