from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import csv
import io
from backend.models import Payment
from backend.auth import get_current_user
from backend.database import get_db
from fastapi import Query
from datetime import datetime

router = APIRouter()



@router.get("/export/csv")
def export_csv(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None)
):

    query = db.query(Payment).filter(Payment.user_id == user.id)

    # 🔹 filtre status
    if status:
        query = query.filter(Payment.status == status)

    # 🔹 filtre date
    if start_date:
        query = query.filter(Payment.created_at >= datetime.fromisoformat(start_date))

    if end_date:
        query = query.filter(Payment.created_at <= datetime.fromisoformat(end_date))

    transactions = query.all()

    output = io.StringIO()
    output.write("sep=;\n")
    writer = csv.writer(output, delimiter=";")

    # 🔥 Header amélioré
    writer.writerow(["date","heure", "mois", "client", "montant", "status"])

    for t in transactions:
        writer.writerow([
            t.created_at.strftime("%Y-%m-%d"),
            t.created_at.strftime("%H:%M"),
            t.created_at.strftime("%Y-%m"), 
            t.client_email,
            f"{t.amount_local:.2f} XOF",
            t.status
        ])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=transactions.csv"
        }
    )