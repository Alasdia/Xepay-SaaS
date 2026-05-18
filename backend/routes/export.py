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
import base64

from datetime import datetime

import matplotlib.pyplot as plt

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.pagesizes import A4
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
# EXPORT PDF PREMIUM
# =========================================================

@router.get("/export/pdf")
def export_pdf(
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # =====================================================
    # DATA
    # =====================================================

    transactions = db.query(Payment).filter(
        Payment.user_id == user.id
    ).all()

    wallet = db.query(Wallet).filter(
        Wallet.user_id == user.id
    ).first()

    links = db.query(Link).filter(
        Link.user_id == user.id
    ).all()

    total_links = len(links)

    active_links = len([
        l for l in links if l.active
    ])

    paid_links = len([
        t for t in transactions
        if t.status == "paid"
    ])

    pending_links = len([
        t for t in transactions
        if t.status == "pending"
    ])

    failed_links = len([
        t for t in transactions
        if t.status == "failed"
    ])

    conversion_rate = (
        (paid_links / total_links) * 100
        if total_links > 0 else 0
    )

    total_volume = sum(
        t.amount_local for t in transactions
    )

    fee_total = total_volume * 0.06

    merchant_net = total_volume - fee_total

    wallet_balance = (
        wallet.available if wallet else 0
    )

    wallet_pending = (
        wallet.pending if wallet else 0
    )

    # =====================================================
    # DONUT CHART
    # =====================================================

    values = [
        paid_links,
        pending_links,
        failed_links
    ]

    colors_chart = [
        "#22C55E",
        "#FACC15",
        "#EF4444"
    ]

    fig, ax = plt.subplots(
        figsize=(5, 5)
    )

    fig.patch.set_facecolor("#081F6B")

    ax.set_facecolor("#081F6B")

    ax.pie(
        values,
        colors=colors_chart,
        startangle=90,
        wedgeprops=dict(
            width=0.32,
            edgecolor="#081F6B",
            linewidth=8
        )
    )

    ax.text(
        0,
        0.08,
        f"{conversion_rate:.1f}%",
        ha="center",
        va="center",
        fontsize=28,
        color="white",
        weight="bold"
    )

    ax.text(
        0,
        -0.18,
        "Payés",
        ha="center",
        va="center",
        fontsize=12,
        color="white"
    )

    ax.axis("equal")

    chart_temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".png"
    )

    plt.savefig(
        chart_temp.name,
        bbox_inches="tight",
        transparent=True,
        facecolor=fig.get_facecolor()
    )

    plt.close()

    # =====================================================
    # PDF
    # =====================================================

    pdf_temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    )

    c = canvas.Canvas(
        pdf_temp.name,
        pagesize=A4
    )

    width, height = A4

    # =====================================================
    # BACKGROUND
    # =====================================================

    c.setFillColor(colors.white)

    c.rect(
        0,
        0,
        width,
        height,
        fill=1
    )

    # =====================================================
    # HEADER
    # =====================================================

    c.setFont(
        "Helvetica-Bold",
        30
    )

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.drawString(
        40,
        740,
        "Xepay"
    )

    c.setFillColor(colors.black)

    c.setFont(
        "Helvetica-Bold",
        24
    )

    c.drawString(
        40,
        695,
        "Rapport financier"
    )

    c.setFont(
        "Helvetica",
        12
    )

    c.drawString(
        40,
        660,
        f"Utilisateur : {user.email}"
    )

    c.drawString(
        40,
        635,
        f"Date : {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
    )

    # =====================================================
    # SUMMARY CARD
    # =====================================================

    # SHADOW

    c.setFillColor(
        colors.HexColor("#EEF2FF")
    )

    c.roundRect(
        46,
        466,
        205,
        125,
        10,
        fill=1,
        stroke=0
    )

    # CARD

    c.setFillColor(colors.white)

    c.roundRect(
        40,
        540,
        170,
        125,
        12,
        fill=1,
        stroke=0
    )

    # BORDER

    c.setStrokeColor(
        colors.HexColor("#E5E7EB")
    )

    c.roundRect(
        40,
        540,
        170,
        125,
        12,
        fill=0
    )

    # TITLE

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.setFont(
        "Helvetica-Bold",
        18
    )

    c.drawString(
        60,
        590,
        "Résumé"
    )

    # CONTENT

    c.setFillColor(colors.black)

    c.setFont(
        "Helvetica",
        12
    )

    c.drawString(
        60,
        555,
        f"Transactions : {len(transactions)}"
    )

    c.drawString(
        60,
        530,
        f"Volume total : {total_volume:,.0f} XOF"
    )

    c.drawString(
        60,
        490,
        f"Commissions : {fee_total:,.0f} XOF"
    )

    # NET

    c.setFillColor(
        colors.HexColor("#22C55E")
    )

    c.setFont(
        "Helvetica-Bold",
        13
    )

    c.drawString(
        60,
        460,
        f"Net : {merchant_net:,.0f} XOF"
    )

    # =====================================================
    # LINKS CARD
    # =====================================================

    # SHADOW

    c.setFillColor(
        colors.HexColor("#EEF2FF")
    )

    c.roundRect(
        225,
        540,
        170,
        125,
        12,
        fill=1,
        stroke=0
    )

    # CARD

    c.setFillColor(colors.white)

    c.roundRect(
        225,
        540,
        170,
        125,
        12,
        fill=1,
        stroke=0
    )

    # BORDER

    c.setStrokeColor(
        colors.HexColor("#E5E7EB")
    )

    c.roundRect(
        225,
        540,
        170,
        125,
        12,
        fill=0
    )

    # TITLE

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.setFont(
        "Helvetica-Bold",
        18
    )

    c.drawString(
        245,
        590,
        "Links Analytics"
    )

    # CONTENT

    c.setFillColor(colors.black)

    c.setFont(
        "Helvetica",
        12
    )

    c.drawString(
        310,
        550,
        f"Créés : {total_links}"
    )

    c.drawString(
        310,
        520,
        f"Actifs : {active_links}"
    )

    c.drawString(
        310,
        490,
        f"Payés : {paid_links}"
    )

    # CONVERSION

    c.setFillColor(
        colors.HexColor("#22C55E")
    )

    c.setFont(
        "Helvetica-Bold",
        13
    )

    c.drawString(
        310,
        460,
        f"Conversion : {conversion_rate:.1f}%"
    )

    # =====================================================
    # DONUT CARD
    # =====================================================

    c.setFillColor(
        colors.HexColor("#081F6B")
    )

    c.roundRect(
        410,
        520,
        145,
        145,
        12,
        fill=1
    )

    c.drawImage(
        chart_temp.name,
        430,
        545,
        width=100,
        height=100,
        mask='auto'
    )

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        12
    )

    c.drawCentredString(
        482,
        640,
        "Transactions"
    )

    # =====================================================
    # WALLET
    # =====================================================

    c.setFillColor(colors.white)

    c.roundRect(
        40,
        445,
        710,
        60,
        10,
        fill=1
    )

    c.setStrokeColor(
        colors.HexColor("#E5E7EB")
    )

    c.roundRect(
        40,
        390,
        540,
        50,
        10,
        fill=0
    )

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.setFont(
        "Helvetica-Bold",
        14
    )

    c.drawString(
        55,
        410,
        "Wallet"
    )

    c.setFont(
        "Helvetica",
        12
    )

    c.drawString(
        220,
        410,
        f"Disponible : {wallet_balance:,.0f} XOF"
    )

    c.setFillColor(
        colors.HexColor("#F59E0B")
    )

    c.drawString(
        420,
        410,
        f"En attente : {wallet_pending:,.0f} XOF"
    )

    # =====================================================
    # TABLE HEADER
    # =====================================================

    c.setFillColor(
        colors.HexColor("#1D4ED8")
    )

    c.roundRect(
        40,
        400,
        710,
        36,
        6,
        fill=1
    )

    c.setFillColor(colors.white)

    c.setFont(
        "Helvetica-Bold",
        11
    )

    c.drawString(55, 360, "Date")
    c.drawString(180, 360, "Client")
    c.drawString(380, 360, "Montant")
    c.drawString(640, 360, "Statut")

    # =====================================================
    # TABLE CONTENT
    # =====================================================

    y = 330

    # ROW LINE

    c.setStrokeColor(
        colors.HexColor("#F1F5F9")
    )

    c.line(
        40,
        y - 14,
        740,
        y - 14
    )

    for t in transactions[:10]:

        c.setFillColor(colors.black)

        c.setFont(
            "Helvetica",
            10
        )

        c.drawString(
            55,
            y,
            t.created_at.strftime("%Y-%m-%d")
        )

        c.drawString(
            180,
            y,
            t.client_email[:24]
        )

        c.drawString(
            380,
            y,
            f"{t.amount_local:,.0f} XOF"
        )

        # STATUS BADGE

        if t.status == "paid":

            c.setFillColor(
                colors.HexColor("#DCFCE7")
            )

            c.roundRect(
                630,
                y - 5,
                55,
                18,
                8,
                fill=1
            )

            c.setFillColor(
                colors.HexColor("#16A34A")
            )

            c.drawString(
                508,
                y,
                "Payé"
            )

        elif t.status == "pending":

            c.setFillColor(
                colors.HexColor("#FEF3C7")
            )

            c.roundRect(
                495,
                y - 5,
                65,
                18,
                8,
                fill=1
            )

            c.setFillColor(
                colors.HexColor("#D97706")
            )

            c.drawString(
                500,
                y,
                "Attente"
            )

        else:

            c.setFillColor(
                colors.HexColor("#FEE2E2")
            )

            c.roundRect(
                495,
                y - 5,
                60,
                18,
                8,
                fill=1
            )

            c.setFillColor(
                colors.HexColor("#DC2626")
            )

            c.drawString(
                505,
                y,
                "Échec"
            )

        y -= 28

    # =====================================================
    # FOOTER
    # =====================================================

    c.setStrokeColor(
        colors.HexColor("#1D4ED8")
    )

    c.line(
        40,
        60,
        580,
        60
    )

    c.setFillColor(colors.black)

    c.setFont(
        "Helvetica",
        10
    )

    c.drawString(
        40,
        40,
        "Xepay — Rapport généré automatiquement"
    )

    c.setFillColor(
        colors.HexColor("#1D4ED8")
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

    # =====================================================
    # RESPONSE
    # =====================================================

    return FileResponse(
        pdf_temp.name,
        media_type="application/pdf",
        filename="rapport_xepay.pdf"
    )