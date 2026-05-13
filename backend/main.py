from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from backend.routes.lien import router as lien_router
from backend.routes.users import router as users_router
from backend.routes.payments import router as payments_router 
from backend.routes.transfer import router as transfer_router
from backend.database import init_db
from backend.models import Link
from backend.database import Base, engine
from backend.routes import payout
from backend.models import UserDB, Wallet, Payment, Withdrawal, WalletTransaction
from backend.routes.webhook.abonnement import router as webhook_router
from backend.routes.webhook.paiement import router as paiement_webhook_router
from fastapi.staticfiles import StaticFiles
import os
from backend.routes.export import router as export_router
from backend.routes.api_keys import router as api_keys_router
from backend.routes.webhooks_api import router as webhooks_api_router
from backend.middleware.log_middleware import LogMiddleware
from backend.routes.logs import router as logs_router
from backend.routes.wallet import router as wallet_router
from backend.routes.webhook.stripe import router as stripe_router
from backend.routes.app import router as ai_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lien_router)
app.include_router(users_router)
app.include_router(payments_router)
app.include_router(payout.router)
app.include_router(transfer_router)
app.include_router(webhook_router)
app.include_router(paiement_webhook_router)
app.include_router(export_router)
app.include_router(api_keys_router)
app.include_router(webhooks_api_router)
app.add_middleware(LogMiddleware)
app.include_router(logs_router)
app.include_router(wallet_router)
app.include_router(stripe_router)
app.include_router(ai_router)



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "frontend/html")),
    name="static"
)


init_db()
Base.metadata.create_all(bind=engine)

@app.get("/")
def home():
    return {"message": "SaaS backend ready"}
    
@app.get("/about")
def about():
     return {"project": "Mon SaaS", "status": "en construction"}


    
