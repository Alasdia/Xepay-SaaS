import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_payment_email(to_email, pdf_path):

    with open(pdf_path, "rb") as f:
        pdf_base64 = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "Paiement reçu",
            "html": """
                <h2>Paiement confirmé ✅</h2>
                <p>Votre facture PDF est jointe.</p>
            """,
            "attachments": [
                {
                    "filename": "facture.pdf",
                    "content": pdf_base64,
                    "type": "application/pdf"
                }
            ]
        }
    )

    print(response.status_code)
    print(response.text)