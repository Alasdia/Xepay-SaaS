import resend
import os
import base64
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

def send_payment_email(to_email, pdf_path):

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    print(pdf_base64[:50])

    resend.Emails.send({
        "from": "Xepay <onboarding@resend.dev>",
        "to": [to_email],
        "subject": "Paiement reçu",
        "html": "<h1>Facture PDF</h1>",
        "attachments": [
            {
                "filename": "facture.pdf",
                "content": pdf_base64
            }
        ]
    })