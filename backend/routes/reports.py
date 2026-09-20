import time
import stripe
import requests
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Profile, WorkspaceUser
from backend.middleware.authorization import require_manager
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

router = APIRouter()

@router.get("/reports/financial")
def download_financial_report(
    start_date: str,
    end_date: str,
    db: Session = Depends(get_db),
    membership: WorkspaceUser = Depends(require_manager)
):
    owner_id = membership.workspace_id

    profile = db.query(Profile).filter(Profile.user_id == owner_id).first()
    if not profile or not profile.stripe_account_id:
        raise HTTPException(400, "Compte Stripe non connecté")

    try:
        report_run = stripe.reporting.ReportRun.create(
            report_type="balance.summary.1",
            parameters={
                "interval_start": int(datetime.fromisoformat(start_date).timestamp()),
                "interval_end": int(datetime.fromisoformat(end_date).timestamp()),
            },
            stripe_account=profile.stripe_account_id,
        )
    except stripe.error.StripeError as e:
        raise HTTPException(400, f"Erreur Stripe : {e.user_message or str(e)}")

    for _ in range(30):
        run = stripe.reporting.ReportRun.retrieve(
            report_run.id,
            stripe_account=profile.stripe_account_id
        )
        if run.status == "succeeded":
            break
        if run.status == "failed":
            raise HTTPException(500, "La génération du rapport a échoué côté Stripe")
        time.sleep(2)
    else:
        raise HTTPException(504, "Le rapport prend trop de temps à se générer, réessaie dans un instant")

    file_id = run.result.id
    file_url = f"https://files.stripe.com/v1/files/{file_id}/contents"
    resp = requests.get(file_url, auth=(stripe.api_key, ""))
    if resp.status_code != 200:
        raise HTTPException(500, "Impossible de récupérer le fichier du rapport")

    return StreamingResponse(
        iter([resp.content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=rapport_financier_{start_date}_{end_date}.csv"}
    )