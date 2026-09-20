function setStatutChip(el) {
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  const select = document.getElementById('filter-statut');
  select.value = el.dataset.statut;
  select.dispatchEvent(new Event('change'));
}
function setTypeChip(el) {
  document.querySelectorAll('.type-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  currentType = el.dataset.type;
  offset = 0;
  transactions = [];
  chargerTransactions();
}
async function downloadFinancialReport() {
  const startDate = document.getElementById("startDate").value;
  const endDate = document.getElementById("endDate").value;
  if (!startDate || !endDate) {
    showToast("Sélectionne une période (du / au) avant de générer le rapport", "warning");
    return;
  }
  const btn = document.getElementById("exportFinancialReportBtn");
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i class="bi bi-hourglass-split me-1"></i> Génération en cours...`;
  try {
    const res = await fetch(
      `https://api.alasdia.com/reports/financial?start_date=${startDate}&end_date=${endDate}`,
      {
        headers: {
          "Authorization": "Bearer " + localStorage.getItem("token"),
          "X-Workspace-Id": localStorage.getItem("workspace_id")
        }
      }
    );
    if (res.status === 403) {
      showUpgradeModal();
      return;
    }
    if (!res.ok) {
      let message = "Erreur lors de la génération du rapport";
      try {
        const data = await res.json();
        if (typeof data.detail === "string") message = data.detail;
      } catch (e) {}
      showToast(message, "error");
      return;
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rapport_financier_${startDate}_${endDate}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast("Rapport téléchargé avec succès");
  } catch (err) {
    showToast("Erreur de connexion au serveur", "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}
document.addEventListener("DOMContentLoaded", () => {
  const reportBtn = document.getElementById("exportFinancialReportBtn");
  if (reportBtn) {
    reportBtn.addEventListener("click", downloadFinancialReport);
  }
});
async function exportCSV() {
  console.log("CLICK OK")
  const startDate = document.getElementById("startDate").value
  const endDate = document.getElementById("endDate").value
  const status = document.getElementById("statusFilter")?.value
  const params = new URLSearchParams()
  if (status) params.append("status", status)
  if (startDate) params.append("start_date", startDate)
  if (endDate) params.append("end_date", endDate)
  const res = await fetch(`https://api.alasdia.com/export/csv?${params}`, {
    headers: {
      "Authorization": "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  if (res.status === 403) {
    showUpgradeModal()
    return
  }
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "transactions.csv"
  document.body.appendChild(a)
  a.click()
  a.remove()
}
async function exportPDF() {
  const startDate = document.getElementById("startDate").value
  const endDate = document.getElementById("endDate").value
  const status = document.getElementById("filter-statut").value
  const params = new URLSearchParams()
  if (status) params.append("status", status)
  if (startDate) params.append("start_date", startDate)
  if (endDate) params.append("end_date", endDate)
  const res = await fetch(
    `https://api.alasdia.com/export/pdf?${params}`,
    {
      headers: {
        "Authorization": "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    }
  )
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = "rapport_xepay.pdf"
  document.body.appendChild(a)
  a.click()
  a.remove()
}
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("exportBtn").addEventListener("click", exportCSV)
})
document
  .getElementById("exportPdfBtn")
  .addEventListener("click", exportPDF)
document.addEventListener("DOMContentLoaded", async () => {
  const token = localStorage.getItem("token")
  if (!token) {
    window.location.href = "login.html"
    return
  }
  const res = await fetch("https://api.alasdia.com/me", {
    headers: {
      "Authorization": "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  const user = await res.json()
  const lock = document.getElementById("transactions-lock");
  if (user.plan === "free") {
    document.body.classList.add("locked-page");
    lock.style.display = "flex";
    return;
  }
  document.body.classList.remove("locked-page");
  lock.style.display = "none";
  loadStats();
  chargerTransactions();
  chargerWallet();
  loadWalletHistory();
})
const statusMap = {
  paid: "Réussi",
  pending: "En attente",
  expired: "Échoué"
};
let statusChart = null;
function renderStatusChart(paid, pending, failed) {
  const ctx = document.getElementById("statusChart");
  if (!ctx) return;
  if (statusChart) {
    statusChart.destroy();
  }
  const centerTextPlugin = {
    id: "centerText",
    beforeDraw(chart) {
      const { ctx } = chart;
      const meta = chart.getDatasetMeta(0);
      if (!meta.data.length) return;
      const x = meta.data[0].x;
      const y = meta.data[0].y;
      const total = paid + pending + failed;
      const percent = total > 0 ? ((paid / total) * 100).toFixed(1) : 0;
      ctx.save();
      ctx.font = "bold 26px Arial";
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(percent + "%", x, y);
      ctx.restore();
    }
  };
  statusChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Payés", "En attente", "Échoués"],
      datasets: [{
        data: [paid, pending, failed],
        backgroundColor: [
          "#4ade80",
          "#facc15",
          "#f87171"
        ],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "55%",
      plugins: {
        legend: {
          position: "right",
          align: "center",
          labels: {
            color: "white",
            boxWidth: 18,
            boxHeight: 18,
            padding: 20,
            usePointStyle: false
          }
        }
      }
    },
    plugins:[centerTextPlugin]
  });
}
document.getElementById("filter-statut").addEventListener("change", () => {
  offset = 0
  transactions = []
  chargerTransactions()
})
let transactions = []
let offset = 0;
const limit = 10;
let isLoading = false;
let currentType = "";
const avatarPalette = ['#22d3ee','#facc15','#ec4899','#4ade80','#a78bfa','#fb923c','#60a5fa','#f87171'];
function avatarColor(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % avatarPalette.length;
  return avatarPalette[h];
}
const typeIcon = {
  payment: "bi-credit-card",
  withdraw: "bi-bank",
  transfer: "bi-arrow-left-right"
};
function statusBadgeClass(status) {
  if (["paid", "success"].includes(status)) return "badge-success";
  if (["pending", "processing"].includes(status)) return "badge-warning";
  return "badge-danger";
}
function afficherTransactions(data) {
  console.log("DATA REÇUE 👉", data)
  const tbody = document.getElementById('tbody-transactions')
  const vide = document.getElementById('etat-vide')
  if (data.length === 0) {
    if (offset === 0) {
      tbody.innerHTML = ''
      vide.classList.remove('d-none')
      document.getElementById('nb-transactions').textContent = '0 transactions'
    }
    return
  }
  vide.classList.add('d-none')
  document.getElementById('nb-transactions').textContent =
    `${transactions.length} transaction${transactions.length > 1 ? 's' : ''}`
  const html = data.map((t, i) => {
  const amount = (t.amount_local ?? t.amount);
  const currency = (t.currency_local ?? t.currency);
  const displayName = t.type === "payment" ? (t.label || "Client") : (t.label || "Transfert");
  const color = avatarColor(displayName || 'x');
  return `
    <tr onclick="voirDetailActivite(${i})" style="cursor:pointer;">
      <td>
        <div class="d-flex align-items-center gap-3">
          <div class="avatar" style="background:${color};">
            ${t.type === "payment"
              ? (displayName ? displayName[0].toUpperCase() : "?")
              : `<i class="bi ${typeIcon[t.type] || 'bi-arrow-left-right'}"></i>`}
          </div>
          <div>
            <div class="fw-semibold">${displayName}</div>
            <small style="color: #9ca3af; font-size:0.75rem;">
              ${t.type === "payment" ? "Client" : t.type === "withdraw" ? "Retrait" : "Transfert"}
            </small>
          </div>
        </div>
      </td>
      <td>
        <span class="amount-cell">${amount.toLocaleString("fr-FR")}</span><span class="amount-currency">${currency}</span>
      </td>
      <td>
        <span class="status-pill ${statusBadgeClass(t.status)}">
          ${statusMap[t.status] || t.status}
        </span>
      </td>
      <td style="color: #6b7280; font-size: 0.85rem;">
        ${
          t.date && !isNaN(new Date(t.date))
            ? new Date(t.date).toLocaleDateString("fr-FR", {
              day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit"
            })
            : "N/A"
        }
      </td>
      <td style="text-align:right;">
        <button onclick="event.stopPropagation()"
          style="background:#f9fafb; border:1px solid #e5e7eb; color:#6b7280; width:32px; height:32px; border-radius:8px; cursor:pointer;">
          <i class="bi bi-eye"></i>
        </button>
      </td>
    </tr>
  `
  }).join('');
  if (offset === 0) {
    tbody.innerHTML = html;
  } else {
    tbody.innerHTML += html;
  }
}
function voirDetailActivite(index) {
  const t = transactions[index];
  if (!t) return;
  const d = t.details || {};
  let rows = [];
  const displayName = t.type === "payment" ? t.label : (t.label || "Transfert");
  const amount = (t.amount_local ?? t.amount);
  const currency = (t.currency_local ?? t.currency);
  if (t.type === "payment") {
    rows = [
      ["Montant reçu", `${amount.toLocaleString("fr-FR")} ${currency}`],
      ["Montant d'origine", `${d.amount_origin ?? "-"} ${d.currency_origin ?? ""}`],
      ["Taux utilisé", d.rate_used ?? "-"],
      ["Frais", `${d.fee_amount ?? 0}`],
      ["Carte", `${d.card_brand ?? "-"} •••• ${d.card_last4 ?? "----"}`],
      ["Expiration carte", d.card_exp_month && d.card_exp_year ? `${d.card_exp_month}/${d.card_exp_year}` : "-"],
      ["Session Stripe", d.stripe_session_id ?? "-"],
      ["Payment Intent", d.stripe_payment_intent_id ?? "-"],
      ["Compte Stripe", d.stripe_account_id ?? "-"],
      ["Lien de paiement", d.link_id ?? "-"]
    ];
  } else if (t.type === "withdraw") {
    rows = [
      ["Montant", `${amount.toLocaleString("fr-FR")} ${currency}`],
      ["Référence", d.reference ?? "-"],
      ["Payout Stripe", d.stripe_payout_id ?? "-"],
      ["Traité le", d.processed_at ? new Date(d.processed_at).toLocaleString("fr-FR") : "-"]
        ];
  } else if (t.type === "transfer") {
    rows = [
      ["Montant", `${amount.toLocaleString("fr-FR")} ${currency}`],
      ["Référence", d.reference ?? "-"],
      ["Correspondant", d.counterparty_email ?? "-"],
      ["Frais", `${d.fee_amount ?? 0} XOF`],
      ["Note", d.description ?? "-"]
    ];
  }
  document.getElementById("detail-title").innerText = displayName;
  document.getElementById("detail-sub").innerText =
    (t.type === "payment" ? "Paiement" : t.type === "withdraw" ? "Retrait" : "Transfert") +
    " · " + statusMap[t.status] || t.status;
  document.getElementById("detail-body").innerHTML = rows.map(([label, value]) => `
    <div class="d-flex justify-content-between py-3 border-bottom">
      <span class="text-muted">${label}</span>
      <span class="fw-semibold" style="text-align:right; max-width:60%; word-break:break-all;">${value}</span>
    </div>
  `).join("");
  document.querySelector(".row.g-3.mb-3").style.display = "none";
  document.querySelector(".row.g-3.mb-4").style.display = "none";
  document.querySelector(".toolbar").style.display = "none";
  document.querySelector(".table-wrap:not(#detail-view)").style.display = "none";
  document.getElementById("detail-view").style.display = "block";
}
function fermerDetail() {
  document.querySelector(".row.g-3.mb-3").style.display = "";
  document.querySelector(".row.g-3.mb-4").style.display = "";
  document.querySelector(".toolbar").style.display = "";
  document.querySelector(".table-wrap:not(#detail-view)").style.display = "";
  document.getElementById("detail-view").style.display = "none";
}
async function chargerTransactions() {
  console.log("CHARGER TRANSACTIONS CALLED")
  if (isLoading) return;
  isLoading = true;
  const loader = document.getElementById("loading-more");
  loader.classList.remove("d-none");
  try {
    const statut = document.getElementById("filter-statut").value
    const params = new URLSearchParams({ offset, limit })
    if (currentType) params.append("type", currentType)
    if (statut) params.append("status", statut)
    const url = `https://api.alasdia.com/activity?${params}`
    const res = await fetch(url, {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    console.log("OFFSET =", offset)
    const data = await res.json()
    console.log("OFFSET =", offset, data)
    transactions = [...transactions, ...data]
    afficherTransactions(data)
    offset += data.length;
  } catch (err) {
    console.error("Erreur activity:", err)
  }
  isLoading = false;
  loader.classList.add("d-none");
}
async function rafraichir(btn) {
  try {
    btn.style.transition = "transform 0.6s linear"
    btn.style.transform = "rotate(360deg)"
    btn.disabled = true
    await chargerTransactions()
    await loadStats()
  } catch (err) {
    console.error(err)
  } finally {
    setTimeout(() => {
      btn.style.transform = "rotate(0deg)"
      btn.disabled = false
    }, 600)
  }
}
function filtrerTransactions() {
  const search = document.getElementById('search-input').value.toLowerCase()
  const statut = document.getElementById('filter-statut').value
  const filtered = transactions.filter(t => {
    const matchSearch = (t.label || "").toLowerCase().includes(search)
    const matchStatus = !statut || t.status === statut
    return matchSearch && matchStatus
  })
  afficherTransactions(filtered)
}
function resetFiltres() {
  document.getElementById('search-input').value = ''
  document.getElementById('filter-statut').value = ''
  document.getElementById('filter-devise').value = ''
}
console.log("DATA =", transactions);
function renderStats(stats) {
  document.getElementById("total-xof").innerText =
    (stats.total_received || 0).toLocaleString("fr-FR") + " XOF";
  document.getElementById("pending-xof").innerText =
    (stats.pending_total || 0).toLocaleString("fr-FR") + " XOF";
  document.getElementById("success-rate").innerText =
    (stats.success_rate || 0) + "%";
  renderStatusChart(
    stats.paid_links || 0,
    stats.pending_links || 0,
    stats.failed_links || 0
  );
}
function renderLinksKPI(plan) {
  const usage = plan.usage || {};
  const createdEl = document.getElementById("links-created");
  const paidEl = document.getElementById("links-paid");
  const barEl = document.getElementById("links-progress-bar");
  const linksLimitText = usage.links_limit === null ? "Illimité" : usage.links_limit;
  const paidLimitText = usage.paid_limit === null ? "Illimité" : usage.paid_limit;
  if (createdEl) createdEl.innerText = `${usage.paid_count ?? 0} / ${paidLimitText}`;
  if (paidEl) paidEl.innerText = `Sur un maximum de ${linksLimitText} liens créés`;
  if (barEl) {
    const pct = usage.paid_limit > 0
      ? Math.min(100, (usage.paid_count / usage.paid_limit) * 100)
      : 0;
    barEl.style.width = pct + "%";
  }
}
async function loadStats() {
  try {
    const token = localStorage.getItem("token");
    const response = await fetch("https://api.alasdia.com/stats", {
      headers: {
        Authorization: "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const stats = await response.json();
    window.LAST_STATS = stats;
    console.log(stats)
    renderStatusChart(
      stats.paid_count || 0,
      stats.pending_link || 0,
      stats.failed_links || 0
    )
    document.getElementById("success-rate").textContent =
      (stats.success_rate || 0) + "%"
    renderStats(stats);
  } catch (error) {
    console.error("Erreur stats:", error);
  }
}
async function chargerWallet() {
  try {
    const res = await fetch("https://api.alasdia.com/wallet/me", {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    const data = await res.json()
    console.log("MES DONNES:", data)
    const lockedEl = document.getElementById("wallet-locked")
    const balanceEl = document.getElementById("wallet-balance")
    const nextEl = document.getElementById("wallet-next")
    console.log("lockedEl:", lockedEl)
    console.log("balanceEl:", balanceEl)
    balanceEl.innerText =
      Number(data.available || 0).toLocaleString("fr-FR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + " XOF"
    const lockedAmountEl = document.getElementById("locked-amount");
    if (lockedAmountEl) {
      lockedAmountEl.innerText =
        Number(data.locked_amount || 0).toLocaleString("fr-FR", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        }) + " XOF";
    }
    const lockedCountdownEl = document.getElementById("locked-countdown");
    if (lockedCountdownEl) {
      if (data.next_available_at) {
        const lockedTarget = new Date(data.next_available_at);
        function updateLockedCountdown() {
          lockedCountdownEl.innerText = formatCountdown(lockedTarget);
        }
        updateLockedCountdown();
        setInterval(updateLockedCountdown, 1000);
      } else {
        lockedCountdownEl.innerText = "Aucun montant verrouillé";
      }
    }
  } catch (err) {
    console.error("Erreur wallet:", err)
  }
}
function formatCountdown(targetDate) {
  const now = new Date()
  const diff = new Date(targetDate) - now
  if (diff <= 0) return "Disponible maintenant"
  const totalSeconds = Math.floor(diff / 1000)
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  let result = "Disponible dans "
  if (days > 0) result += `${days}j `
  if (hours > 0 || days > 0) result += `${hours}h `
  if (minutes > 0 || hours > 0 || days > 0) result += `${minutes}min `
  result += `${seconds}s`
  return result
}
async function loadWalletHistory() {
  try {
    const token = localStorage.getItem("token");
    const historyList = document.getElementById("walletHistoryList");
    const res = await fetch("https://api.alasdia.com/wallet/history", {
      headers: {
        "Authorization": `Bearer ${token}`,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await res.json();
    console.log("WALLET HISTORY :", data)
    if (!data.transactions || data.transactions.length === 0) {
      historyList.innerHTML = "<small>Aucun mouvement wallet</small>";
      return;
    }
    const html = data.transactions.map(tx => {
      const estRetraitEnAttente = tx.type === 'withdraw' && tx.status === 'pending';
      const boutonAnnuler = estRetraitEnAttente && tx.withdrawal_id
        ? `<div style="margin-top: 8px; text-align: right;">
            <button
              onclick="annulerRetrait('${tx.withdrawal_id}')"
              style="
                background:#facc15;
                color:#111827;
                border:none;
                padding:5px 12px;
                border-radius:6px;
                font-size:11px;
                font-weight:600;
                cursor:pointer;
              ">
              Annuler le retrait
            </button>
          </div>`
        : '';
        return `
          <div class="wallet-item" style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 10px;">
            <div class="wallet-row">
              <span class="wallet-label">Type :</span>
              <span class="wallet-value">
                ${tx.type === 'deposit' ? 'Dépôt' : tx.type === 'withdraw' ? 'Retrait' : tx.type}
              </span>
            </div>
            <div class="wallet-row">
              <span class="wallet-label">Montant :</span>
              <span class="wallet-value ${tx.direction === 'in' ? 'text-success' : 'text-danger'}">
                ${tx.direction === 'in' ? '+' : '-'}${Number(tx.amount).toLocaleString("fr-FR")} XOF
              </span>
            </div>
            <div class="wallet-row">
              <span class="wallet-label">Date :</span>
              <span class="wallet-value">${new Date(tx.created_at).toLocaleString("fr-FR")}</span>
            </div>
            <div class="wallet-row">
              <span class="wallet-label">Référence :</span>
              <span class="wallet-value">${tx.reference || "N/A"}</span>
            </div>
            <div class="wallet-row">
              <span class="wallet-label">Note :</span>
              <span class="wallet-value">${tx.description || "-"}</span>
            </div>
            ${boutonAnnuler}
          </div>
        `;
      }).join("");
      historyList.innerHTML = html;
      console.log(
        "HTML WALLET HISTORY :",
        historyList.innerHTML
      );
  } catch (e) {
    const historyList = document.getElementById("walletHistoryList");
    if (historyList) {
      historyList.innerHTML = "<small>Erreur chargement historique</small>";
    }
  }
}
console.log("VERSION TEST XEPAY 001");
async function annulerRetrait(retraitId) {
  console.log("ID DU RETRAIT À ANNULER :", retraitId);
  if (!retraitId) {
    showToast(
      "Identifiant du retrait introuvable",
      "error"
    );
    return;
  }
  if (!confirm(
     "Voulez-vous vraiment annuler ce retrait ? Les fonds seront recrédités."
  )) {
    return;
  }
  try {
    const token = localStorage.getItem("token");
    const workspaceId = localStorage.getItem("workspace_id");
    const res = await fetch(
      `https://api.alasdia.com/withdrawals/${retraitId}/cancel`,
      {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + token,
          "X-Workspace-Id": workspaceId
        }
      }
    );
    const data = await res.json();
    console.log("RÉPONSE :", data);
    if (!res.ok) {
      showToast(
        data.detail || "Erreur lors de l'annulation",
        "error"
      );
      return;
    }
    showToast(
      "Retrait annulé avec succès !",
      "success"
    );
    await loadWalletHistory();
    await chargerWallet();
  } catch (err) {
    console.error(
      "Erreur annulation retrait :",
      err
    );
    showToast(
      "Erreur de connexion au serveur",
      "error"
    );
  }
}
const confirmBtn = document.getElementById("confirmWithdrawBtn");
if (confirmBtn) {
  confirmBtn.addEventListener("click", async () => {
    if (confirmBtn.disabled) return;
    confirmBtn.disabled = true;
    const token = localStorage.getItem("token");
    const amount = parseFloat(document.getElementById("withdrawAmount").value);
    if (!amount || amount <= 0) {
      alert("Montant invalide");
      confirmBtn.disabled = false;
      return;
    }
    try {
      const res = await fetch("https://api.alasdia.com/withdraw", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
          "X-Workspace-Id": localStorage.getItem("workspace_id")
        },
        body: JSON.stringify({ amount })
      });
      const data = await res.json();
      if (!res.ok) {
        let message = "Impossible d'effectuer ce retrait";
        if (data.detail === "Permission insuffisante") {
          message = "Seul le propriétaire du compte peut effectuer un retrait";
        } else if (typeof data.detail === "string") {
          message = data.detail;
        }
        showToast(message, "error");
        closeWithdrawModalCleanly();
        return;
      }
      const res2 = await fetch(`https://api.alasdia.com/withdraw/${data.id}/process`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-Workspace-Id": localStorage.getItem("workspace_id")
        }
      });
      const data2 = await res2.json();
      if (!res2.ok) {
        showToast(data2.detail || "Erreur lors du traitement Stripe", "error");
        closeWithdrawModalCleanly();
        return;
      }
      showToast("Retrait envoyé avec succès");
      closeWithdrawModalCleanly();
      document.getElementById("withdrawAmount").value = "";
      setTimeout(() => location.reload(), 1200);
    } catch (err) {
      showToast("Erreur serveur, veuillez réessayer", "error");
      closeWithdrawModalCleanly();
    } finally {
      confirmBtn.disabled = false;
    }
  });
}
const successCard = document.getElementById("successCard");
const chartTooltip = document.getElementById("chartTooltip");
if (successCard && chartTooltip) {
    successCard.addEventListener("mouseenter", () => {
        chartTooltip.style.display = "block";
    });
    successCard.addEventListener("mouseleave", () => {
        chartTooltip.style.display = "none";
    });
}
const scrollBox = document.getElementById("transactions-scroll-box");
if (scrollBox) {
  scrollBox.addEventListener("scroll", () => {
    const scrollTop = scrollBox.scrollTop;
    const visibleHeight = scrollBox.clientHeight;
    const totalHeight = scrollBox.scrollHeight;
    if (scrollTop + visibleHeight >= totalHeight - 50) {
      chargerTransactions();
    }
  });
}
async function loadPlan() {
  try {
    const token = localStorage.getItem("token");
    const workspaceId = localStorage.getItem("workspace_id");

    const res = await fetch("https://api.alasdia.com/me/plan", {
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": workspaceId
      }
    });
    const data = await res.json();
    window.GLOBAL_PLAN = data;
    const el = document.getElementById("plan-name");
    if (el) el.textContent = data.plan;
    const paidLimit = data.usage ? data.usage.paid_limit : data.paid_limit;
    const el2 = document.getElementById("plan-limit");
    if (el2) {
      el2.textContent = paidLimit === null || paidLimit === undefined ? "Illimité" : paidLimit;
    }
    renderLinksKPI(data);
  } catch (err) {
    console.error("Erreur loadPlan:", err);
  }
}
window.onload = () => {
  loadPlan()
}
function closeWithdrawModalCleanly() {
  const modalEl = document.getElementById("withdrawModal");
  const modal = bootstrap.Modal.getInstance(modalEl);
  if (modal) modal.hide();
  setTimeout(() => {
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
    document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
  }, 300);
}
function showUpgradeModal(feature = null) {
  const plan = window.GLOBAL_PLAN?.plan;
  updateUpgradeModal(plan, feature);
  const modal = new bootstrap.Modal(
    document.getElementById("modalUpgrade")
  );
  modal.show();
}
function updateUpgradeModal(plan, feature) {
  document.querySelectorAll(".plan-card")
    .forEach(card => {
      card.classList.remove("plan-disabled");
    });
  if (feature === "multi-users") {
    document.querySelector(".plan-starter")
      .classList.add("plan-disabled");

    document.querySelector(".plan-pro")
      .classList.add("plan-disabled");

    return;
  }
  if (plan === "free") {
    document.querySelector(".plan-starter")
      .classList.add("plan-disabled");
  }
  if (plan === "pro") {
    document.querySelector(".plan-pro")
      .classList.add("plan-disabled");
  }
  if (plan === "business") {
    document.querySelector(".plan-business")
      .classList.add("plan-disabled");
  }
}
function checkApiAccess(event) {
    const plan = localStorage.getItem("plan");
    if (plan === "free") {
        sessionStorage.setItem("openApiUpgrade", "true");
    }
}
function checkMultiUsersAccess(event) {
    const plan = localStorage.getItem("plan");
    if (plan !== "business") {
        sessionStorage.setItem(
            "openMultiUsersUpgrade",
            "true"
        );
    }
}
async function upgrade(plan) {
  const token = localStorage.getItem("token");
  const res = await fetch(
    "https://api.alasdia.com/create-checkout-session",
    {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        plan: plan
      })
    }
  );
  const data = await res.json();
  if (!res.ok || !data.url) {
    showToast("Erreur lors de l'ouverture de Stripe", "error");
    return;
  }
  window.location.href = data.url;
}
const modalUpgradeEl = document.getElementById("modalUpgrade");
if (modalUpgradeEl) {
  modalUpgradeEl.addEventListener("shown.bs.modal", () => {
    document.querySelectorAll("#modalUpgrade .reveal")
      .forEach((el, index) => {
        setTimeout(() => {
          el.classList.add("visible");
        }, index * 100);
      });
  });
}
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const icons = { success: "✅", error: "⚠️", warning: "⏳" };
  const toast = document.createElement("div");
  toast.className = `toast-notif-item ${type}`;
  toast.innerHTML = `<span class="icon">${icons[type] || icons.success}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}
async function initStripeBalanceReport() {
  const container = document.getElementById("stripe-balance-report-container");
  const mount = document.getElementById("stripe-balance-report");
  if (!container || !mount) return;
  try {
    const stripeConnectInstance = window.StripeConnect.init({
      publishableKey: "pk_test_51TJYk921oAuf4OUmVuqkub7cs2OUkWGpYlS4IgpfZrF7p6lY4v1YxRirVv1QSZD8Qof4JU78mmLgexh5wINo0vlo00c7HTwz5x",
      fetchClientSecret: async () => {
        const res = await fetch("https://api.alasdia.com/reports/connect-session", {
          method: "POST",
          headers: {
            "Authorization": "Bearer " + localStorage.getItem("token"),
            "X-Workspace-Id": localStorage.getItem("workspace_id")
          }
        });
        if (!res.ok) throw new Error("Impossible de créer la session Stripe");
        const data = await res.json();
        return data.client_secret;
      },
    });
    const balanceReport = stripeConnectInstance.create("balance-report");
    mount.innerHTML = "";
    mount.appendChild(balanceReport);
    container.style.display = "block";
  } catch (err) {
    console.error("Erreur chargement rapport Stripe:", err);
    showToast("Impossible de charger le rapport Stripe", "error");
  }
}
document.addEventListener("DOMContentLoaded", () => {
  initStripeBalanceReport();
});