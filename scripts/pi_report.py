"""Generate a sanitized partial PI report; tooling only, not an app dependency."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--render-dir", required=True, type=Path)
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "docs/projeto-integrador/relatorio.md"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("PIBody", fontName="Helvetica", fontSize=10.5,
                             leading=15.2, spaceAfter=9, textColor=colors.HexColor("#233c3c"),
                             alignment=TA_LEFT, allowWidows=0, allowOrphans=0))
    styles.add(ParagraphStyle("PITitle", parent=styles["PIBody"], fontName="Helvetica-Bold",
                             fontSize=23, leading=28, spaceAfter=18, keepWithNext=True))
    styles.add(ParagraphStyle("PISection", parent=styles["PIBody"], fontName="Helvetica-Bold",
                             fontSize=13, leading=18, spaceBefore=13, spaceAfter=8,
                             keepWithNext=True, textColor=colors.HexColor("#196b62")))
    story = []
    for block in source.read_text(encoding="utf-8").strip().split("\n\n"):
        text = block.replace("\n", " ").strip()
        style = "PIBody"
        if text.startswith("# "):
            text, style = text[2:], "PITitle"
        elif text.startswith("## "):
            text, style = text[3:], "PISection"
        text = text.replace("—", "-").replace("–", "-").replace("\u2011", "-")
        text = escape(text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        story.append(Paragraph(text, styles[style]))
    story.append(Spacer(1, 10))

    def page(canvas, doc):
        canvas.setStrokeColor(colors.HexColor("#bfd3cd"))
        canvas.line(48, A4[1] - 43, A4[0] - 48, A4[1] - 43)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.setFillColor(colors.HexColor("#196b62"))
        canvas.drawString(48, A4[1] - 33, "RITMO  /  PROJETO INTEGRADOR")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#506360"))
        canvas.drawRightString(A4[0] - 48, A4[1] - 33, "PARCIAL - DADOS SINTÉTICOS")
        canvas.drawString(48, 31, "23/11/2026 | Identificação e fotos pessoais fora do repositório público")
        canvas.drawRightString(A4[0] - 48, 31, str(doc.page))

    doc = SimpleDocTemplate(str(args.output), pagesize=A4, leftMargin=48, rightMargin=48,
                            topMargin=67, bottomMargin=55, title="Ritmo - Relatório parcial do PI",
                            author="Projeto pessoal Ritmo", subject="Evidências técnicas sanitizadas; versão em elaboração")
    doc.build(story, onFirstPage=page, onLaterPages=page)

    import pypdfium2
    from pypdf import PdfReader
    from PIL import Image, ImageDraw
    reader = PdfReader(args.output)
    assert len(reader.pages) > 1
    assert all((p.extract_text() or "").strip() for p in reader.pages)
    args.render_dir.mkdir(parents=True, exist_ok=True)
    pdf = pypdfium2.PdfDocument(args.output)
    thumbnails = []
    for i in range(len(pdf)):
        image = pdf[i].render(scale=1.3).to_pil().convert("RGB")
        image.save(args.render_dir / f"page-{i + 1:02}.png")
        image.thumbnail((298, 422))
        thumbnails.append(image.copy())
    sheet = Image.new("RGB", (640, ((len(thumbnails) + 1) // 2) * 450), "#e4eae7")
    draw = ImageDraw.Draw(sheet)
    for i, image in enumerate(thumbnails):
        x, y = (i % 2) * 320 + 10, (i // 2) * 450 + 20
        sheet.paste(image, (x, y))
        draw.text((x, y - 15), f"Page {i+1}", fill="black")
    sheet.save(args.render_dir / "contact.png")
    result = {"pages": len(reader.pages), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
              "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(), "status": "partial-report",
              "humanEvaluation": False, "photographsProvided": False}
    args.output.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
