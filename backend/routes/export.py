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
from backend.models import (
    Payment,
    Link,
    Profile,
    Wallet,
    WalletTransaction
)

import matplotlib.pyplot as plt

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


from fastapi.responses import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
import tempfile


@router.get("/export/pdf")
def export_pdf(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None)
):

    query = db.query(Payment).filter(
        Payment.user_id == user.id
    )

    if status:
        query = query.filter(
            Payment.status == status
        )

    if start_date:
        query = query.filter(
            Payment.created_at >= datetime.fromisoformat(start_date)
        )

    if end_date:
        query = query.filter(
            Payment.created_at <= datetime.fromisoformat(end_date)
        )

    transactions = query.all()

    wallet = db.query(Wallet).filter(
        Wallet.user_id == user.id
    ).first()

    links = db.query(Link).filter(
        Link.user_id == user.id
    ).all()

    # ===== LINKS ANALYTICS =====

    total_links = len(links)

    active_links = len([
        l for l in links
        if l.active
    ])

    paid_links = len(transactions)

    conversion_rate = (
        (paid_links / total_links) * 100
        if total_links > 0 else 0
    )

    # ===== WALLET =====

    wallet_balance = wallet.available if wallet else 0

    wallet_pending = wallet.pending if wallet else 0

    total_volume = sum(t.amount_local for t in transactions)

    total_transactions = len(transactions)

    fee_total = total_volume * 0.06

    merchant_net = total_volume - fee_total

    temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    )

    c = canvas.Canvas(temp.name, pagesize=letter)

    width, height = letter

    # HEADER
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#1D4ED8"))
    c.drawString(40, 760, "Xepay")

    c.setFillColor(colors.black)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(40, 720, "Rapport financier")

    c.setFont("Helvetica", 11)

    c.drawString(
        40,
        695,
        f"Utilisateur : {user.email}"
    )

    c.drawString(
        40,
        675,
        f"Date : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
    )

    # SUMMARY
    c.setFont("Helvetica-Bold", 15)

    c.drawString(40, 620, "Résumé")

    c.setFont("Helvetica", 12)

    c.drawString(
        40,
        590,
        f"Transactions : {total_transactions}"
    )

    c.drawString(
        40,
        565,
        f"Volume total : {total_volume:,.2f} XOF"
    )

    c.drawString(
        40,
        540,
        f"Commissions Xepay : {fee_total:,.2f} XOF"
    )

    c.drawString(
        40,
        515,
        f"Net marchand : {merchant_net:,.2f} XOF"
    )

    # ===== LINKS =====

    c.setFont("Helvetica-Bold", 14)

    c.drawString(320, 620, "Links Analytics")

    c.setFont("Helvetica", 11)

    c.drawString(
        320,
        595,
        f"Liens créés : {total_links}"
    )

    c.drawString(
        320,
        575,
        f"Liens actifs : {active_links}"
    )

    c.drawString(
        320,
        555,
        f"Liens payés : {paid_links}"
    )

    c.drawString(
        320,
        535,
        f"Conversion : {conversion_rate:.1f}%"
    )

    # ===== WALLET =====

    c.setFont("Helvetica-Bold", 14)

    c.drawString(320, 500, "Wallet")

    c.setFont("Helvetica", 11)

    c.drawString(
        320,
        480,
        f"Disponible : {wallet_balance:,.0f} XOF"
    )

    c.drawString(
        320,
        460,
        f"En attente : {wallet_pending:,.0f} XOF"
    )

    # TABLE HEADER
    c.setFillColor(colors.HexColor("#1D4ED8"))

    c.rect(40, 450, 520, 25, fill=1)

    c.setFillColor(colors.white)

    c.setFont("Helvetica-Bold", 11)

    c.drawString(50, 458, "Date")
    c.drawString(150, 458, "Client")
    c.drawString(340, 458, "Montant")
    c.drawString(470, 458, "Statut")

    # TABLE CONTENT
    y = 430

    c.setFillColor(colors.black)

    c.setFont("Helvetica", 10)

    for t in transactions[:15]:

        c.drawString(
            50,
            y,
            t.created_at.strftime("%Y-%m-%d")
        )

        c.drawString(
            150,
            y,
            t.client_email[:28]
        )

        c.drawString(
            340,
            y,
            f"{t.amount_local:,.0f} XOF"
        )

        c.drawString(
            470,
            y,
            t.status
        )

        y -= 22

    # FOOTER
    c.setStrokeColor(colors.HexColor("#1D4ED8"))

    c.line(40, 80, 560, 80)

    c.setFont("Helvetica", 10)

    c.drawString(
        40,
        60,
        "Xepay — Rapport généré automatiquement"
    )

    c.setFont("Helvetica", 9)

    c.drawCentredString(
        width / 2,
        40,
        "Generated securely by Xepay"
    )

    # ===== GRAPHIQUE =====

    labels = ["Payés", "En attente", "Échoués"]

    values = [
        paid_links,
        active_links - paid_links,
        max(total_links - active_links, 0)
    ]

    colors_chart = ["#22c55e", "#facc15", "#ef4444"]

    plt.figure(figsize=(2.2, 2.2))

    plt.pie(
        values,
        labels=labels,
        autopct='%1.1f%%',
        colors=colors_chart
    )

    plt.title("Transactions Xepay")

    chart_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".png"
    )

    plt.savefig(chart_file.name, bbox_inches="tight")

    plt.close()

    # ===== INSERTION PDF =====

    c.drawImage(
        chart_file.name,
        340,
        120,
        width=140,
        height=140
    )

    c.save()

    return FileResponse(
        temp.name,
        media_type="application/pdf",
        filename="rapport_xepay.pdf"
    )