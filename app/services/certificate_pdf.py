import os
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = landscape(A4)
CONTENT_W = PAGE_W - 160
GOLD = colors.HexColor("#b08d3c")
NAVY = colors.HexColor("#1f2a44")


def _fit_font_size(text: str, font: str, max_width: float, start: int, minimum: int) -> int:
    size = start
    while size > minimum and stringWidth(text, font, size) > max_width:
        size -= 1
    return size


def _centered(c: canvas.Canvas, y: float, text: str, font: str, size: int, color=NAVY) -> None:
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawCentredString(PAGE_W / 2, y, text)


def generate_certificate_pdf(
    path: str | Path,
    *,
    recipient_name: str,
    title: str,
    issued_by: str,
    issue_date: date,
    certificate_id: str,
) -> None:
    """Render the single predefined template. Written to a temp file then renamed,
    so a failure never leaves a half-written certificate behind."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        c = canvas.Canvas(str(tmp), pagesize=(PAGE_W, PAGE_H))
        c.setTitle(f"Certificate - {recipient_name}")
        c.setAuthor(issued_by)

        # border
        c.setStrokeColor(GOLD)
        c.setLineWidth(4)
        c.rect(25, 25, PAGE_W - 50, PAGE_H - 50)
        c.setLineWidth(1)
        c.rect(35, 35, PAGE_W - 70, PAGE_H - 70)

        _centered(c, 480, "CERTIFICATE", "Helvetica-Bold", 46, GOLD)
        _centered(c, 445, "OF COMPLETION", "Helvetica", 18)
        _centered(c, 395, "This is to certify that", "Helvetica-Oblique", 16)

        name_size = _fit_font_size(recipient_name, "Helvetica-Bold", CONTENT_W, 40, 12)
        _centered(c, 340, recipient_name, "Helvetica-Bold", name_size)
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.8)
        c.line(PAGE_W / 2 - 200, 328, PAGE_W / 2 + 200, 328)

        _centered(c, 290, "has successfully completed", "Helvetica-Oblique", 16)

        y = 255
        for line in simpleSplit(title, "Helvetica-Bold", 22, CONTENT_W):
            _centered(c, y, line, "Helvetica-Bold", 22)
            y -= 28

        _centered(c, 110, f"Date: {issue_date.strftime('%d %B %Y')}", "Helvetica", 12)
        issuer = f"Issued by: {issued_by}"
        issuer_size = _fit_font_size(issuer, "Helvetica", CONTENT_W, 12, 8)
        _centered(c, 90, issuer, "Helvetica", issuer_size)
        _centered(c, 55, f"Certificate ID: {certificate_id}", "Helvetica", 8, colors.grey)

        c.showPage()
        c.save()
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
