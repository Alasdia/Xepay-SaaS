from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse, FileResponse

from sqlalchemy.orm import Session

from backend.auth import get_current_user
from backend.database import get_db

from backend.models import (
    Payment,
    Link,
    Wallet
)

import csv
import io
import tempfile

from datetime import datetime

import matplotlib.pyplot as plt

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors


router = APIRouter()


# =========================================================
# EXPORT CSV
# =========================================================

@router.get("/export/csv")
def export_csv(
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

    output = io.StringIO()

    output.write("sep=;\n")

    writer = csv.writer(
        output,
        delimiter=";"
    )

    writer.writerow([
        "date",
        "heure",
        "mois",
        "client",
        "montant",
        "status"
    ])

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
            "Content-Disposition":
            "attachment; filename=transactions.csv"
        }
    )


# =========================================================
# EXPORT PDF
# =========================================================

@router.get("/export/pdf")
def export_pdf(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    status: str = Query(None),
    start_date: str = Query(None),
    end_date: str = Query(None)
):

    # =====================================================
    # QUERY
    # =====================================================

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

    # =====================================================
    # ANALYTICS
    # =====================================================

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

    wallet_balance = (
        wallet.available if wallet else 0
    )

    wallet_pending = (
        wallet.pending if wallet else 0
    )

    total_volume = sum(
        t.amount_local for t in transactions
    )

    total_transactions = len(transactions)

    fee_total = total_volume * 0.06

    merchant_net = total_volume - fee_total

    # =====================================================
    # PDF
    # =====================================================

    temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    )

    c = canvas.Canvas(
        temp.name,
        pagesize=letter
    )

    width, height = letter

    # =====================================================
    # HEADER
    # =====================================================

    c.setFont("Helvetica-Bold", 28)

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.drawString(
        40,
        760,
        "Xepay"
    )

    c.setFillColor(colors.black)

    c.setFont("Helvetica-Bold", 18)

    c.drawString(
        40,
        720,
        "Rapport financier"
    )

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

    # =====================================================
    # SUMMARY
    # =====================================================

    c.setFont("Helvetica-Bold", 15)

    c.drawString(
        40,
        620,
        "Résumé"
    )

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

    # =====================================================
    # LINKS ANALYTICS
    # =====================================================

    c.setFont("Helvetica-Bold", 14)

    c.drawString(
        320,
        620,
        "Links Analytics"
    )

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

    # =====================================================
    # WALLET
    # =====================================================

    c.setFont("Helvetica-Bold", 14)

    c.drawString(
        320,
        500,
        "Wallet"
    )

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

    # =====================================================
    # DONUT CHART
    # =====================================================

    paid_count = paid_links

    pending_count = max(
        active_links - paid_links,
        0
    )

    failed_count = max(
        total_links - active_links,
        0
    )

    sizes = [
        paid_count,
        pending_count,
        failed_count
    ]

    colors_chart = [
        "#22c55e",
        "#facc15",
        "#ef4444"
    ]

    fig, ax = plt.subplots(
        figsize=(4, 4)
    )

    ax.pie(
        sizes,
        colors=colors_chart,
        startangle=90,
        wedgeprops=dict(width=0.35)
    )

    success_rate = (
        (paid_count / total_links) * 100
        if total_links > 0 else 0
    )

    ax.text(
        0,
        0.05,
        f"{success_rate:.1f}%",
        ha="center",
        va="center",
        fontsize=22,
        fontweight="bold",
        color="white"
    )

    ax.text(
        0,
        -0.18,
        "Payés",
        ha="center",
        va="center",
        fontsize=11,
        color="white"
    )

    fig.patch.set_facecolor(
        "#0B1F5E"
    )

    ax.set_facecolor(
        "#0B1F5E"
    )

    ax.axis("equal")

    chart_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".png"
    )

    plt.savefig(
        chart_file.name,
        bbox_inches="tight",
        transparent=False,
        facecolor=fig.get_facecolor()
    )

    plt.close()

    # =====================================================
    # DONUT CARD
    # =====================================================

    c.setFillColor(
        colors.HexColor("#0B1F5E")
    )

    c.roundRect(
        360,
        470,
        180,
        180,
        12,
        fill=1
    )

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        12
    )

    c.drawString(
        385,
        625,
        "Transactions Xepay"
    )

    c.drawImage(
        chart_file.name,
        375,
        500,
        width=120,
        height=120
    )

    c.setFont(
        "Helvetica",
        10
    )

    # PAYÉS
    c.setFillColor(
        colors.HexColor("#22c55e")
    )

    c.circle(
        500,
        590,
        4,
        fill=1
    )

    c.setFillColor(colors.white)

    c.drawString(
        510,
        586,
        "Payés"
    )

    # EN ATTENTE
    c.setFillColor(
        colors.HexColor("#facc15")
    )

    c.circle(
        500,
        570,
        4,
        fill=1
    )

    c.setFillColor(colors.white)

    c.drawString(
        510,
        566,
        "En attente"
    )

    # ÉCHOUÉS
    c.setFillColor(
        colors.HexColor("#ef4444")
    )

    c.circle(
        500,
        550,
        4,
        fill=1
    )

    c.setFillColor(colors.white)

    c.drawString(
        510,
        546,
        "Échoués"
    )

    # =====================================================
    # TABLE HEADER
    # =====================================================

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.rect(
        40,
        390,
        520,
        25,
        fill=1
    )

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        11
    )

    c.drawString(50, 398, "Date")
    c.drawString(150, 398, "Client")
    c.drawString(340, 398, "Montant")
    c.drawString(470, 398, "Statut")

    # =====================================================
    # TABLE CONTENT
    # =====================================================

    y = 370

    c.setFillColor(colors.black)

    c.setFont(
        "Helvetica",
        10
    )

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

    # =====================================================
    # FOOTER
    # =====================================================

    c.setStrokeColor(
        colors.HexColor("#1D4ED8")
    )

    c.line(
        40,
        80,
        560,
        80
    )

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        40,
        60,
        "Xepay — Rapport généré automatiquement"
    )

    c.setFont(
        "Helvetica",
        9
    )

    c.drawCentredString(
        width / 2,
        40,
        "Generated securely by Xepay"
    )

    # =====================================================
    # SAVE PDF
    # =====================================================

    c.save()

    return FileResponse(
        temp.name,
        media_type="application/pdf",
        filename="rapport_xepay.pdf"
    )