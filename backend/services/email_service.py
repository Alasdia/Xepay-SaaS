import html
import logging
import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
# Boîte interne Xepay (jamais doola, jamais le marchand) qui reçoit les
# demandes de correction Buildness (voir send_buildness_correction_
# request_internal_email ci-dessous) - doola n'a de relation directe
# qu'avec Xepay, un humain ici relaie ensuite manuellement vers leur
# support s'il y a lieu.
BUILDNESS_CORRECTION_NOTIFY_EMAIL = os.getenv("BUILDNESS_CORRECTION_NOTIFY_EMAIL")
# Boîte interne Xepay (jamais le marchand) qui reçoit les demandes de
# boutique Shopify "prête à l'emploi" (Buildshop, voir send_shopify_
# store_request_internal_email ci-dessous) - un humain assigne ensuite
# manuellement une boutique déjà provisionnée (services/
# buildshop_service.py) et effectue le transfert Partner Dashboard,
# confirmé impossible à automatiser.
SHOPIFY_STORE_REQUEST_NOTIFY_EMAIL = os.getenv("SHOPIFY_STORE_REQUEST_NOTIFY_EMAIL")


def is_notification_enabled(user, event_key: str, legacy_flag: bool | None = None) -> bool:
    """Paramètres > Notifications (granulaire, voir UserDB.notification_prefs).
    Clé absente -> `legacy_flag` si fourni (ancien alert_login/payment/
    suspect, pour ne pas réactiver silencieusement une alerte déjà
    désactivée par un utilisateur existant), sinon True (opt-out)."""
    if not user:
        return True
    prefs = user.notification_prefs or {}
    if event_key in prefs:
        return bool(prefs[event_key])
    if legacy_flag is not None:
        return bool(legacy_flag)
    return True


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


def send_shopify_payment_link_email(to_email, order_name, amount, currency, pay_url):
    """Envoyé par routes/webhook/shopify.py (orders/create) quand un
    client choisit la méthode manuelle "Payer via Xepay" - les
    instructions de checkout Shopify étant STATIQUES (pas de lien
    dynamique par commande possible nativement, voir le docstring de ce
    fichier côté webhook), c'est le SEUL canal qui transmette au client
    un lien de paiement propre à SA commande."""
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": f"Finalisez le paiement de votre commande {order_name}",
            "html": f"""
                <h2>Votre commande {order_name} est prête à être payée</h2>
                <p>Montant : <b>{amount} {currency}</b></p>
                <p><a href="{pay_url}">Payer maintenant</a></p>
            """
        }
    )
    print("SHOPIFY PAYMENT LINK EMAIL", response.status_code, response.text)


# Notifications Buildness (LLC/EIN via doola) - ajoutées le 2026-11-27,
# déclenchées depuis routes/webhook/doola.py (_apply_doola_event) sur les
# 3 vraies transitions de statut gérées (processing/completed/failed),
# même garde is_notification_enabled que le reste de ce fichier
# (catégorie "entreprise" dans NOTIFICATION_CATEGORIES, spa/views/
# parametres.js).
def send_buildness_processing_email(to_email, company_name):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Votre dossier de création de société est en cours",
            "html": f"""
                <h2>Dossier en cours de traitement 🧾</h2>
                <p>La formation de <b>{company_name}</b> a été transmise à l'État et est en cours de traitement.</p>
                <p>Suivez l'avancement dans "Mon entreprise" sur votre tableau de bord Xepay.</p>
            """
        }
    )
    print("BUILDNESS PROCESSING EMAIL", response.status_code, response.text)


def send_buildness_completed_email(to_email, company_name, ein_number=None):
    ein_line = f"<p>EIN (identifiant fiscal) : <b>{ein_number}</b></p>" if ein_number else ""
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Votre société est formée 🎉",
            "html": f"""
                <h2>Félicitations, votre société est formée ✅</h2>
                <p><b>{company_name}</b> est officiellement formée et son EIN a été émis.</p>
                {ein_line}
                <p>Retrouvez tous les détails et documents dans "Mon entreprise" sur votre tableau de bord Xepay.</p>
            """
        }
    )
    print("BUILDNESS COMPLETED EMAIL", response.status_code, response.text)


def send_buildness_failed_email(to_email, company_name):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [to_email],
            "subject": "Problème avec votre dossier de création de société",
            "html": f"""
                <h2>Votre dossier n'a pas pu aboutir ❌</h2>
                <p>La formation de <b>{company_name}</b> a échoué.</p>
                <p>Rendez-vous dans Paramètres &gt; Entreprise sur votre tableau de bord Xepay pour réessayer.</p>
            """
        }
    )
    print("BUILDNESS FAILED EMAIL", response.status_code, response.text)


def send_buildness_correction_request_internal_email(workspace_id, company_name, doola_company_id, field_label, requested_value, note):
    """Vers BUILDNESS_CORRECTION_NOTIFY_EMAIL (boîte interne Xepay),
    JAMAIS vers doola ni le marchand - voir BuildnessCorrectionRequest
    (models.py) : doola n'a de relation directe qu'avec Xepay, c'est
    donc un humain côté Xepay qui lit cet email et relaie manuellement
    la demande à leur support s'il y a lieu. doola_company_id (demandé
    le 2026-11-27, manquait jusqu'ici) est l'identifiant à communiquer à
    doola pour qu'ils retrouvent la société - company_name seul ne
    suffit pas (pas garanti unique chez eux, "raison sociale validée
    par l'État" peut même différer du nom demandé initialement). Pas de
    garde is_notification_enabled : ce n'est pas une préférence de
    notification du marchand, c'est une alerte opérationnelle interne,
    toujours envoyée."""
    if not BUILDNESS_CORRECTION_NOTIFY_EMAIL:
        logger.warning(
            "BUILDNESS_CORRECTION_NOTIFY_EMAIL non configuré - demande de correction "
            "(workspace_id=%s, company=%s, doolaCompanyId=%s, champ=%s) non notifiée par email.",
            workspace_id, company_name, doola_company_id, field_label,
        )
        return
    # Échappé (contrairement aux autres fonctions de ce fichier, qui
    # n'interpolent que des valeurs déjà fiables type montant/statut
    # Stripe) : field_label/requested_value/note viennent en texte libre
    # d'un membre quelconque du workspace, jamais fiable par défaut dans
    # un email HTML.
    safe_company_name = html.escape(company_name or "")
    safe_doola_company_id = html.escape(doola_company_id or "")
    safe_field_label = html.escape(field_label or "")
    safe_requested_value = html.escape(requested_value or "")
    note_line = f"<p>Note du marchand : {html.escape(note)}</p>" if note else ""
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [BUILDNESS_CORRECTION_NOTIFY_EMAIL],
            "subject": f"[Buildness] Demande de correction - {safe_company_name} ({safe_doola_company_id or 'doolaCompanyId manquant'})",
            "html": f"""
                <h2>Nouvelle demande de correction Buildness</h2>
                <p>Workspace : <b>{html.escape(workspace_id or "")}</b></p>
                <p>Société : <b>{safe_company_name}</b></p>
                <p>doolaCompanyId (à communiquer à doola) : <b>{safe_doola_company_id or "manquant - dossier jamais soumis à doola"}</b></p>
                <p>Champ à corriger : <b>{safe_field_label}</b></p>
                <p>Nouvelle valeur souhaitée : <b>{safe_requested_value}</b></p>
                {note_line}
                <p>doola n'a de relation directe qu'avec Xepay : relayer manuellement cette demande à leur support si nécessaire.</p>
            """
        }
    )
    print("BUILDNESS CORRECTION REQUEST INTERNAL EMAIL", response.status_code, response.text)


def send_shopify_store_request_internal_email(workspace_id, note):
    """Vers SHOPIFY_STORE_REQUEST_NOTIFY_EMAIL (boîte interne Xepay),
    JAMAIS vers le marchand - voir ShopifyStoreRequest (models.py) :
    aucune boutique n'est assignée/transférée automatiquement, c'est un
    humain côté Xepay qui lit cet email et assigne manuellement une
    boutique déjà provisionnée (services/buildshop_service.py) puis
    effectue le "Transfer store" (Partner Dashboard, confirmé
    impossible à automatiser via l'API publique Shopify). Pas de garde
    is_notification_enabled : ce n'est pas une préférence de
    notification du marchand, c'est une alerte opérationnelle interne,
    toujours envoyée. Peut être déclenché depuis le dashboard ou depuis
    Alhu (voir alhu_service.py::_request_shopify_store) - même route/
    même email dans les deux cas, aucune distinction nécessaire ici."""
    if not SHOPIFY_STORE_REQUEST_NOTIFY_EMAIL:
        logger.warning(
            "SHOPIFY_STORE_REQUEST_NOTIFY_EMAIL non configuré - demande de boutique Shopify "
            "(workspace_id=%s) non notifiée par email.",
            workspace_id,
        )
        return
    # Échappé (texte libre d'un membre quelconque du workspace, jamais
    # fiable par défaut dans un email HTML) - même précaution que
    # send_buildness_correction_request_internal_email ci-dessus.
    note_line = f"<p>Note du marchand : {html.escape(note)}</p>" if note else ""
    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "Xepay <noreply@alasdia.com>",
            "to": [SHOPIFY_STORE_REQUEST_NOTIFY_EMAIL],
            "subject": "[Buildshop] Nouvelle demande de boutique Shopify",
            "html": f"""
                <h2>Nouvelle demande de boutique Shopify "prête à l'emploi"</h2>
                <p>Workspace : <b>{html.escape(workspace_id or "")}</b></p>
                {note_line}
                <p>Assigner manuellement une boutique déjà provisionnée (voir GET /buildshop/readiness) puis effectuer le transfert depuis le Partner Dashboard Shopify.</p>
            """
        }
    )
    print("SHOPIFY STORE REQUEST INTERNAL EMAIL", response.status_code, response.text)
