from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from pathlib import Path
from datetime import datetime

UPLOAD_DIR = Path("uploads/invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def generate_invoice_pdf(payment):

    filename = f"invoice_{payment.id}.pdf"
    filepath = UPLOAD_DIR / filename

    c = canvas.Canvas(str(filepath), pagesize=letter)

    width, height = letter
    formatted_amount = f"{payment.amount:,.2f} {payment.currency}"

    # =====================================
    # HEADER
    # =====================================

    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(colors.HexColor("#1D4ED8"))

    # 🔥 descendre un peu pour éviter coupure
    c.drawString(40, 760, "Xepay")

    c.setFillColor(colors.black)

    c.setFont("Helvetica-Bold", 22)
    c.drawString(40, 715, "Reçu de paiement")

    c.setFont("Helvetica", 13)
    c.drawString(40, 690, "Merci pour votre confiance.")

    # =====================================
    # INFOS FACTURE
    # =====================================

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor("#1D4ED8"))

    c.drawRightString(
        560,
        760,
        f"FACTURE #{payment.id}"
    )

    c.setFillColor(colors.black)

    c.setFont("Helvetica", 11)

    c.drawRightString(
        560,
        735,
        f"Date : {datetime.utcnow().strftime('%d/%m/%Y')}"
    )

    c.drawRightString(
        560,
        715,
        f"Heure : {datetime.utcnow().strftime('%H:%M UTC')}"
    )

    # =====================================
    # LIGNE
    # =====================================

    c.setStrokeColor(colors.HexColor("#1D4ED8"))
    c.line(40, 670, 560, 670)

    # =====================================
    # INFORMATIONS CLIENT
    # =====================================

    c.setFillColor(colors.black)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, 630, "Informations client")

    c.setFont("Helvetica", 12)

    c.drawString(
        40,
        600,
        f"Email : {payment.client_email}"
    )

    c.drawString(
        40,
        575,
        "Pays : Sénégal"
    )

    # =====================================
    # INFORMATIONS FACTURE
    # =====================================

    c.setFont("Helvetica-Bold", 16)
    c.drawString(320, 630, "Informations de la facture")

    c.setFont("Helvetica", 12)

    c.drawString(
        320,
        600,
        f"Numéro de paiement : {payment.id}"
    )

    c.drawString(
        320,
        575,
        f"Statut : {payment.status}"
    )

    c.drawString(
        320,
        550,
        f"Devise : {payment.currency}"
    )

    # =====================================
    # DÉTAILS DU PAIEMENT
    # =====================================

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 500, "Détails du paiement")

    # HEADER TABLE
    c.setFillColor(colors.HexColor("#1D4ED8"))
    c.rect(40, 455, 520, 30, fill=1)

    c.setFillColor(colors.white)

    c.setFont("Helvetica-Bold", 12)

    c.drawString(50, 465, "Description")
    c.drawString(300, 465, "Quantité")
    c.drawString(400, 465, "Montant")

    # TABLE CONTENT
    c.setFillColor(colors.black)

    c.setFont("Helvetica", 12)

    c.drawString(
        50,
        425,
        "Paiement via lien Xepay"
    )

    c.drawString(320, 425, "1")

    c.drawString(
        430,
        425,
        formatted_amount
    )

    # LINE
    c.setStrokeColor(colors.lightgrey)
    c.line(40, 405, 560, 405)

    # =====================================
    # RÉSUMÉ FACTURE
    # =====================================

    c.setStrokeColor(colors.lightgrey)

    c.line(320, 330, 560, 330)
    c.line(320, 300, 560, 300)

    c.setFont("Helvetica", 12)

    c.drawRightString(
       470,
       345,
       "Sous-total :"
    )

    c.drawRightString(
       560,
       345,
       formatted_amount
    )

    c.drawRightString(
       470,
       315,
       "Frais Stripe :"
    )

    c.drawRightString(
       560,
       315,
       "0.00 USD"
    )

    # TOTAL
    c.setFont("Helvetica-Bold", 14)

    c.drawRightString(
       470,
       270,
       "Montant payé :"
    )

    c.setFillColor(colors.HexColor("#16A34A"))

    c.drawRightString(
       560,
       270,
       formatted_amount
    )

    c.setFillColor(colors.black)

    # =====================================
    # NOTES
    # =====================================

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, 250, "Notes")

    c.setFont("Helvetica", 11)

    c.drawString(
        40,
        225,
        "Ce document constitue un reçu de paiement."
    )

    c.drawString(
        40,
        205,
        "Aucune TVA applicable."
    )

    # =====================================
    # FOOTER
    # =====================================

    c.setStrokeColor(colors.HexColor("#1D4ED8"))
    c.line(40, 120, 560, 120)

    c.setFillColor(colors.grey)

    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, 90, "Xepay")

    c.setFont("Helvetica", 10)

    c.drawString(
        40,
        70,
        "La solution simple et sécurisée"
    )

    c.drawString(
        40,
        55,
        "pour recevoir des paiements."
    )

    c.drawRightString(
        560,
        90,
        "Besoin d'aide ?"
    )

    c.drawRightString(
        560,
        70,
        "support@xepay.ai"
    )

    c.drawRightString(
        560,
        55,
        "https://xepay.ai"
    )

    c.save()

    return str(filepath)