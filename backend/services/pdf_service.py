from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pathlib import Path
from datetime import datetime

UPLOAD_DIR = Path("uploads/invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def generate_invoice_pdf(payment):

    filename = f"invoice_{payment.id}.pdf"
    filepath = UPLOAD_DIR / filename

    c = canvas.Canvas(str(filepath), pagesize=letter)

    # =========================
    # HEADER
    # =========================
    c.setFont("Helvetica-Bold", 26)
    c.drawString(50, 780, "Xepay")

    c.setFont("Helvetica", 14)
    c.drawString(50, 755, "Payment Receipt")

    # =========================
    # LINE
    # =========================
    c.line(50, 740, 550, 740)

    # =========================
    # PAYMENT DETAILS
    # =========================
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 700, "Payment Details")

    c.setFont("Helvetica", 12)

    c.drawString(50, 670, f"Payment ID : {payment.id}")

    c.drawString(
        50,
        645,
        f"Amount : {payment.amount} {payment.currency}"
    )

    c.drawString(
        50,
        620,
        f"Client : {payment.client_email}"
    )

    c.drawString(
        50,
        595,
        f"Status : {payment.status}"
    )

    c.drawString(
        50,
        570,
        f"Date : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )

    # =========================
    # FOOTER LINE
    # =========================
    c.line(50, 120, 550, 120)

    # =========================
    # FOOTER
    # =========================
    c.setFont("Helvetica", 10)

    c.drawString(
        50,
        100,
        "Powered by Xepay"
    )

    c.drawRightString(
        550,
        100,
        "https://xepay.ai"
    )

    c.save()

    return str(filepath)