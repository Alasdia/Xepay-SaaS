import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

def send_payment_email(to_email, pdf_path):

    print("PDF PATH:", pdf_path)
    print("PDF EXISTS:", os.path.exists(pdf_path))

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

def send_merchant_notification(to_email, payment):

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <onboarding@resend.dev>",
            "to": [to_email],
            "subject": "Nouveau paiement reçu",
            "html": f"""
                <h2>Nouveau paiement reçu ✅</h2>

                <p>
                    Vous avez reçu un paiement de
                    <b>{payment.amount} {payment.currency}</b>
                </p>

                <p>
                    Client : {payment.client_email}
                </p>

                <p>
                    Statut : {payment.status}
                </p>
            """
        }
    )

    print(response.status_code)
    print(response.text)
    print("MERCHANT EMAIL SENT")
    print(response.status_code)
    print(response.text)

def send_subscription_email(
    to_email,
    plan,
    invoice_pdf,
    hosted_invoice_url
):

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Abonnement Xepay activé",
            "html": f"""
                <h2>Bienvenue sur Xepay 🚀</h2>
                <p>
                    Votre abonnement <b>{plan}</b> est maintenant actif.
                </p>
                <p>
                    Télécharger votre facture :
                </p>
                <a href="{invoice_pdf}">
                    Télécharger le PDF
                </a>
                <br><br>
                <a href="{hosted_invoice_url}">
                    Voir la facture Stripe
                </a>
            """
        }
    )
    print(response.status_code)
    print(response.text)