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
import os
import base64
import tempfile

from datetime import datetime

import matplotlib.pyplot as plt

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


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

    # =========================================
    # DATA
    # =========================================

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

    # =========================================
    # DONUT CHART
    # =========================================

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

    # CENTER TEXT

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

    # SAVE TEMP IMAGE

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

    # BASE64

    with open(chart_temp.name, "rb") as image_file:

        chart_base64 = base64.b64encode(
            image_file.read()
        ).decode("utf-8")

    # =========================================
    # HTML TEMPLATE
    # =========================================

    env = Environment(
        loader=FileSystemLoader(
            "backend/templates"
        )
    )

    template = env.get_template(
        "report.html"
    )

    html_content = template.render(

        user=user,

        transactions=transactions[:10],

        total_transactions=len(transactions),

        total_volume=f"{total_volume:,.2f}",

        fee_total=f"{fee_total:,.2f}",

        merchant_net=f"{merchant_net:,.2f}",

        total_links=total_links,

        active_links=active_links,

        paid_links=paid_links,

        pending_links=pending_links,

        failed_links=failed_links,

        conversion_rate=f"{conversion_rate:.1f}",

        wallet_balance=f"{wallet_balance:,.0f}",

        wallet_pending=f"{wallet_pending:,.0f}",

        chart_base64=chart_base64,

        date=datetime.utcnow().strftime(
            "%d/%m/%Y %H:%M"
        )
    )

    # =========================================
    # GENERATE PDF
    # =========================================

    temp_pdf = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    )

    HTML(
        string=html_content,
        base_url=os.getcwd()
    ).write_pdf(temp_pdf.name)

    # =========================================
    # RESPONSE
    # =========================================

    return FileResponse(
        temp_pdf.name,
        media_type="application/pdf",
        filename="rapport_xepay.pdf"
    )