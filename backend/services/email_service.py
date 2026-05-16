import resend
import os
import base64

resend.api_key = os.getenv("RESEND_API_KEY")
print("API KEY =", os.getenv("RESEND_API_KEY"))

def send_payment_email(to_email, pdf_path):

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    resend.Emails.send({
        "from": "Xepay <noreply@xepay.com>",
        "to": [to_email],
        "subject": "Paiement reçu",
        "html": """
            <h2>Paiement confirmé ✅</h2>
            <p>Votre facture PDF est jointe.</p>
        """,
        "attachments": [
            {
                "filename": "facture.pdf",
                "content": pdf_base64
            }
        ]
    })