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
            "from": "Xepay <noreply@alasdia.com>",
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
            "from": "Xepay <noreply@alasdia.com>",
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

def send_invitation_email(
    to_email,
    invite_link,
    inviter_email,
    role
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
            "subject": "Invitation à rejoindre Xepay",
            "html": f"""
                <h2>Vous avez été invité sur Xepay 🚀</h2>

                <p>
                    <b>{inviter_email}</b>
                    vous a invité à rejoindre son workspace.
                </p>

                <p>
                    Rôle attribué :
                    <b>{role}</b>
                </p>

                <br>

                <a
                    href="{invite_link}"
                    style="
                        background:#2563eb;
                        color:white;
                        padding:12px 20px;
                        border-radius:8px;
                        text-decoration:none;
                        font-weight:bold;
                    "
                >
                    Rejoindre Xepay
                </a>

                <br><br>

                <p>
                    Ou utilisez ce lien :
                </p>

                <p>{invite_link}</p>
            """
        }
    )

    print("INVITATION EMAIL")
    print(response.status_code)
    print(response.text)

def send_login_alert_email(email, device, ip):

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [email],
            "subject": "Nouvelle connexion à votre compte Xepay",
            "html": f"""
                <h2>Nouvelle connexion détectée 🔐</h2>

                <p>
                    Une connexion à votre compte Xepay a été détectée.
                </p>

                <p>
                    <b>Appareil :</b> {device}
                </p>

                <p>
                    <b>Adresse IP :</b> {ip}
                </p>

                <br>

                <p>
                    Si c'était vous, aucune action n'est nécessaire.
                </p>

                <p>
                    Si vous ne reconnaissez pas cette activité,
                    changez immédiatement votre mot de passe et activez la double authentification.
                </p>

                <br>

                <p>
                    L'équipe Xepay.
                </p>
            """
        }
    )

    print("LOGIN ALERT EMAIL")
    print(response.status_code)
    print(response.text)

def send_payment_failed_email(to_email, reason="Paiement échoué ou annulé"):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Échec du paiement",
            "html": f"""
                <h2>Paiement non abouti ❌</h2>
                <p>Le paiement n'a pas pu être finalisé.</p>
                <p><b>Raison :</b> {reason}</p>
            """
        }
    )
    print("FAILED EMAIL", response.status_code, response.text)

def send_payment_refunded_email(to_email, amount):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Remboursement effectué",
            "html": f"""
                <h2>Remboursement confirmé 🔄</h2>
                <p>Un montant de <b>{amount}</b> a été remboursé sur votre transaction.</p>
            """
        }
    )
    print("REFUND EMAIL", response.status_code, response.text)

def send_payout_success_email(to_email, amount):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Virement réussi",
            "html": f"""
                <h2>Virement vers votre compte exécuté ✅</h2>
                <p>Votre virement d'un montant de <b>{amount}</b> a été effectué avec succès.</p>
            """
        }
    )
    print("PAYOUT SUCCESS EMAIL", response.status_code, response.text)

def send_payout_failed_email(to_email, amount):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Échec du virement",
            "html": f"""
                <h2>Virement échoué ou annulé ❌</h2>
                <p>Le virement de <b>{amount}</b> n'a pas pu aboutir. Les fonds ont été recrédités sur votre solde disponible.</p>
            """
        }
    )
    print("PAYOUT FAILED EMAIL", response.status_code, response.text)

def send_account_updated_email(to_email):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Mise à jour de votre compte Stripe Connect",
            "html": f"""
                <h2>Compte mis à jour 🔄</h2>
                <p>Les informations de votre profil et de votre compte Connect ont été synchronisées avec succès.</p>
            """
        }
    )
    print("ACCOUNT UPDATED EMAIL", response.status_code, response.text)

def send_subscription_updated_email(to_email, plan, status):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Mise à jour de votre abonnement Xepay",
            "html": f"""
                <h2>Abonnement mis à jour 🔄</h2>
                <p>Votre abonnement pour le plan <b>{plan}</b> a été mis à jour.</p>
                <p>Statut actuel : <b>{status}</b></p>
            """
        }
    )
    print("SUBSCRIPTION UPDATED EMAIL", response.status_code, response.text)

def send_subscription_canceled_email(to_email):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Résiliation de votre abonnement Xepay",
            "html": f"""
                <h2>Abonnement résilié ⚠️</h2>
                <p>Votre abonnement a été résilié. Vous êtes retourné sur le plan gratuit (Free).</p>
            """
        }
    )
    print("SUBSCRIPTION CANCELED EMAIL", response.status_code, response.text)

def send_payment_failed_subscription_email(to_email):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Échec du prélèvement de votre abonnement",
            "html": f"""
                <h2>Échec de paiement ❌</h2>
                <p>Le prélèvement automatique pour votre abonnement a échoué. Veuillez mettre à jour votre moyen de paiement.</p>
            """
        }
    )
    print("SUBSCRIPTION PAYMENT FAILED EMAIL", response.status_code, response.text)
