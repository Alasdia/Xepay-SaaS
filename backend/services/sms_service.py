import os
from twilio.rest import Client

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER")

client = Client(TWILIO_SID, TWILIO_AUTH)

def send_2fa_sms(phone: str, code: str):
    try:
        client.messages.create(
            body=f"Xepay — votre code de vérification : {code}",
            from_=TWILIO_FROM,
            to=phone
        )
    except Exception as e:
        print("❌ Erreur envoi SMS 2FA:", e)