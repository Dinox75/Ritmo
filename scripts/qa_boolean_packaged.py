"""Check the opt-in lesson in the actual executable using only synthetic data."""
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import expect, sync_playwright
from qa_packaged_windows import EDGE, launch, quit_and_verify, authorize
from tutor.boolean_lesson import scenarios


def run(executable, output):
    report = {"temporary_data": True, "student_learning_evidence": False, "flows": [],
              "executable": str(executable),
              "package_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
    with tempfile.TemporaryDirectory(prefix="ritmo-boolean-package-", ignore_cleanup_errors=True) as folder:
        root = Path(folder)
        data = root / "Ritmo"
        data.mkdir()
        (data / ".migration_disabled").write_text("1\n", encoding="ascii")
        config = json.loads((Path(__file__).resolve().parents[1] / "config/config.json").read_text(encoding="utf8"))
        config["tutor"]["model_root"] = str(root / "no-models")
        config_path = data / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=str(EDGE), headless=True)
            process = None
            try:
                process, port = launch(executable, root)
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                authorize(page, process, port)
                page.goto(f"http://127.0.0.1:{port}/boolean-lesson.html")
                expect(page.locator("#availability")).to_contain_text("Modo desligado")
                expect(page.locator("#controls")).to_be_hidden()
                authorize(page, process, port)
                page.goto(f"http://127.0.0.1:{port}/")
                quit_and_verify(page, process, port)
                process = None
                report["default_disabled"] = True
                config["experiments"] = {"boolean_lesson": True}
                config_path.write_text(json.dumps(config), encoding="utf8")
                process, port = launch(executable, root)
                for width in (390, 1366, 1920):
                    page.set_viewport_size({"width": width, "height": 1000})
                    authorize(page, process, port)
                    page.goto(f"http://127.0.0.1:{port}/boolean-lesson.html")
                    for key, task in scenarios().items():
                        page.locator("#scenario").select_option(task["family"])
                        page.locator("#start").click()
                        expect(page.locator("#stage")).to_contain_text("Conceito")
                        page.locator("#continue").focus()
                        page.keyboard.press("Enter")
                        expect(page.locator("#stage")).to_contain_text("Exemplo curto")
                        page.locator("#continue").click()
                        expect(page.locator("#stage")).to_contain_text("Primeira tentativa")

                        def submit(current, expression, conclusion):
                            name, value = next(iter(current["values"].items()))
                            page.locator("#fact-name").select_option(name)
                            page.locator("#fact-value").select_option(str(value))
                            page.locator("#expression").fill(expression)
                            page.locator("#conclusion").select_option(str(conclusion))
                            page.locator("#submit-attempt").click()

                        submit(task, task["mistake"], not task["expected"])
                        expect(page.locator("#stage")).to_contain_text("Dica e nova tentativa")
                        page.reload()
                        expect(page.locator("#stage")).to_contain_text("Dica e nova tentativa")
                        submit(task, task["expression"], task["expected"])
                        expect(page.locator("#stage")).to_contain_text("Correção fundamentada")
                        expect(page.locator("#dialog")).to_contain_text("Retomando a primeira tentativa")
                        page.locator("#continue").click()
                        expect(page.locator("#stage")).to_contain_text("Exercício de transferência")
                        transfer = task["transfer"]
                        submit(transfer, transfer["expression"], transfer["expected"])
                        expect(page.locator("#stage")).to_contain_text("Verificação concluída")
                        page.locator("#question-form").locator("xpath=..").locator("summary").click()
                        page.locator("#question").fill("Qual a probabilidade de chover amanhã?")
                        page.locator("#question-form button").click()
                        expect(page.locator("#dialog")).to_contain_text("Não consigo verificar")
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                        report["flows"].append({"width": width, "scenario": key, "passed": True})
                    page.screenshot(path=str(output / f"boolean-packaged-{width}.png"), full_page=True)
                assert not errors, errors
                authorize(page, process, port)
                page.goto(f"http://127.0.0.1:{port}/")
                quit_and_verify(page, process, port)
                process = None
                report.update(port_released=True, javascript_errors=errors, keyboard=True, reload_at_retry=True)
            finally:
                browser.close()
                if process is not None and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    result = run(args.executable.resolve(), args.output.resolve())
    (args.output / "boolean-packaged.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result), flush=True)
