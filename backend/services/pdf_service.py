from reportlab.pdfgen import canvas
from pathlib import Path

UPLOAD_DIR = Path("uploads/invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def generate_invoice_pdf(payment):

    filename = f"invoice_{payment.id}.pdf"
    filepath = UPLOAD_DIR / filename

    c = canvas.Canvas(str(filepath))

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 800, "Facture Xepay")

    c.setFont("Helvetica", 12)

    c.drawString(50, 760, f"Paiement ID : {payment.id}")
    c.drawString(50, 740, f"Montant : {payment.amount} {payment.currency}")
    c.drawString(50, 720, f"Client : {payment.email}")
    c.drawString(50, 700, f"Status : {payment.status}")

    c.save()

    return str(filepath)