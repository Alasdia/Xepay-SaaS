async function loadPlanStatus() {
  const token = localStorage.getItem("token");
  if (!token) {
    window.location.href = "login.html";
    return;
  }
  try {
    const res = await fetch("https://api.alasdia.com/me/plan", {
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await res.json();
    console.log("PLAN DATA:", data);
    const alertBox = document.getElementById('payment-failed-alert');
    if (alertBox) {
      if (data.subscription_status === 'past_due') {
        alertBox.classList.remove('d-none');
      } else {
        alertBox.classList.add('d-none');
      }
    }
    const planName = data.plan || "free";
    localStorage.setItem("plan", planName);
  } catch (err) {
    console.error("Erreur chargement plan:", err);
  }
}
function updateKycProgress(data) {
  let percent = 0;
  if (data.stripe) {
    percent += 20;
  }
  if (!data.stripe) {
    setProgress(percent);
    return;
  }
  if (data.stripe.charges_enabled) {
    percent += 20;
  }
  if (data.stripe.payouts_enabled) {
    percent += 20;
  }
  if (!data.needs_kyc) {
    percent += 20;
  }
  if (!data.future_requirements) {
    percent += 20;
  }
  setProgress(percent);
}
function setProgress(percent) {
  const bar = document.getElementById("kyc-progress-bar");
  const text = document.getElementById("kyc-progress-text");
  bar.style.width = percent + "%";
  text.innerText = percent + "%";
  bar.classList.remove(
    "bg-danger",
    "bg-warning",
    "bg-success"
  );
  text.classList.remove(
    "text-danger",
    "text-warning",
    "text-success"
  );
  if (percent < 40) {
    bar.classList.add("bg-danger");
    text.classList.add("text-danger");
  } else if (percent < 100) {
    bar.classList.add("bg-warning");
    text.classList.add("text-warning");
  } else {
    bar.classList.add("bg-success");
    text.classList.add("text-success");
  }
}
async function initStripe() {
  const token = localStorage.getItem("token")
  if (!token) {
    window.location.href = "login.html"
    return
  }
  const res = await fetch("https://api.alasdia.com/stripe/status", {
    headers: {
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  if (!res.ok) {
    let message = "Impossible de charger les informations Stripe";
    try {
      const errData = await res.json();
      if (errData.detail === "Permission insuffisante") {
        message = "Seul le propriétaire du compte peut configurer Stripe";
      } else if (errData.detail) {
        message = errData.detail;
      }
    } catch (e) {}
    showToast(message, "error");
    const badge = document.getElementById("stripe-status-badge")
    badge.innerText = "Accès restreint"
    badge.classList.remove("status-warn", "status-pending", "status-ok")
    badge.classList.add("status-warn")
    const btn = document.getElementById("stripe-action-btn")
    btn.innerText = "Réservé au propriétaire"
    btn.disabled = true
    return
  }
  const data = await res.json()
  updateKycProgress(data);
  console.log("STRIPE DATA:", data)
  const mainAlert = document.getElementById("main-kyc-alert")
  if (!data.connected) {
    mainAlert.innerHTML = `
      <div class="alert mb-4" style="background:rgba(239,68,68,0.15);
        border:1px solid rgba(239,68,68,0.3);
        border-radius:12px;">
        <i class="fa-solid fa-triangle-exclamation warning-icon"></i> Configurez Stripe pour activer les paiements
      </div>
    `
  }
  else if (data.needs_kyc) {
    mainAlert.innerHTML = `
      <div class="alert mb-4" style="background:rgba(255,193,7,0.15);
        border:1px solid rgba(255,193,7,0.3);
        border-radius:12px;">
        <i class="fa-solid fa-triangle-exclamation warning-icon"></i> Vérification KYC requise pour continuer à recevoir des paiements
      </div>
    `
  }
  else if (!data.future_requirements) {
    mainAlert.innerHTML = `
      <div class="alert mb-4" style="background:rgba(34,197,94,0.15);
        border:1px solid rgba(34,197,94,0.3);
        border-radius:12px;">
        <i class="fa-solid fa-circle-check"></i> Compte entièrement vérifié
      </div>
    `;
  }
  else {
    mainAlert.innerHTML = `
      <div class="alert mb-4" style="background:rgba(255,193,7,0.15);
        border:1px solid rgba(255,193,7,0.3);
        border-radius:12px;">
        <i class="fa-solid fa-triangle-exclamation warning-icon"></i> Compte opérationnel, vérification finale incomplète
      </div>
    `;
  }
  const btn = document.getElementById("stripe-action-btn")
  const badge = document.getElementById("stripe-status-badge")
  btn.disabled = false
  btn.classList.remove("btn-warning", "btn-success")
  if (!data.connected || data.needs_kyc || data.future_requirements) {
    btn.classList.add("btn-warning");
  } else {
    btn.classList.add("btn-success");
  }
  badge.classList.remove("status-warn","stauts-pending", "status-ok")
  if (!data.connected) {
    badge.innerText = "Non configuré"
    badge.classList.add("status-warn")
    btn.innerText = "Configurer Stripe"
    btn.onclick = async () => {
      btn.innerText = "Chargement..."
      btn.disabled = true
      try {
        const res = await fetch("https://api.alasdia.com/onboarding", {
          method: "POST",
          headers: { 
            Authorization: "Bearer " + token,
            "X-Workspace-Id": localStorage.getItem("workspace_id")
          }
        })
        const d = await res.json()
        if (!res.ok) {
          let message = d.detail || "Erreur Stripe onboarding";
          if (d.detail === "Permission insuffisante") {
            message = "Seul le propriétaire du compte peut configurer Stripe";
          }
          showToast(message, "error");
          btn.innerText = "Configurer Stripe";
          btn.disabled = false;
          return
        }
        window.location.href = d.url
      } catch (e) {
        btn.innerText = "Erreur, réessayer"
        btn.disabled = false
      }
    }
  }
  else if (data.needs_kyc) {
    badge.innerText = "Vérification requise"
    badge.classList.add("status-pending")
    btn.innerText = "Compléter vérification"
    btn.onclick = async () => {
      const res = await fetch("https://api.alasdia.com/stripe/login-link", {
        headers: { 
          Authorization: "Bearer " + token,
          "X-Workspace-Id": localStorage.getItem("workspace_id")
        }
      })
      const d = await res.json()
      if (!res.ok) {
        let message = d.detail || "Impossible d'accéder à Stripe";

        if (d.detail === "Permission insuffisante") {
          message = "Seul le propriétaire du compte peut effectuer cette vérification";
        }
        showToast(message, "error");
        return
      }
      window.location.href = d.url
    }
  }
  else if (data.future_requirements) {
    badge.innerText = "Opérationnel";
    badge.classList.add("status-pending");
    btn.innerText = "Compléter la vérification finale";
    btn.disabled = false;
    btn.onclick = async () => {
        const res = await fetch("https://api.alasdia.com/stripe/login-link", {
            headers: {
                Authorization: "Bearer " + token,
                "X-Workspace-Id": localStorage.getItem("workspace_id")
            }
        });
        const d = await res.json();
        if (!res.ok) {
          let message = d.detail || "Impossible d'accéder à Stripe";

          if (d.detail === "Permission insuffisante") {
            message = "Seul le propriétaire du compte peut effectuer cette vérification";
          }
          showToast(message, "error");
          return
        }
        window.location.href = d.url
    };
  }
  else {
    badge.innerText = "Entièrement vérifié";
    badge.classList.add("status-ok");

    btn.innerText = "Compte entièrement vérifié ✅";
    btn.disabled = true;
  }
}
function showCancelModal() {
  const modal = new bootstrap.Modal(document.getElementById("modalCancelSub"));
  modal.show();
}
async function confirmCancelSubscription() {
  const btn = document.getElementById("btn-confirm-cancel");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Résiliation...";
  }
  const token = localStorage.getItem("token");
  const workspaceId = localStorage.getItem("workspace_id");
  try {
    const res = await fetch("https://api.alasdia.com/me/plan/cancel", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": workspaceId
      }
    });
    const data = await res.json();
    const modalEl = document.getElementById("modalCancelSub");
    if (modalEl) {
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }
    if (res.ok) {
      showToast(data.message || "Abonnement résilié avec succès.", "warning");
      loadUser();
    } else {
      showToast(data.detail || "Échec de l'annulation", "error");
    }
  } catch (err) {
    console.error("Erreur annulation :", err);
    showToast("Erreur de connexion au serveur", "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Oui, résilier";
    }
  }
}
document.addEventListener('DOMContentLoaded', () => {
  const updateBtn = document.getElementById('update-card-btn');
  if (updateBtn) {
    updateBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      try {
        const token = localStorage.getItem("token");
        const workspaceId = localStorage.getItem("workspace_id");
        const res = await fetch('https://api.alasdia.com/me/create-portal-session', {
          method: 'POST',
          headers: {
            "Authorization": "Bearer " + token,
            "X-Workspace-Id": workspaceId
          }
        });
        const data = await res.json();
        if (res.ok && data.url) {
          window.location.href = data.url;
        } else {
          alert(data.detail || "Impossible d'accéder au portail de facturation.");
        }
      } catch (err) {
        console.error("Erreur redirection portail:", err);
      }
    });
  }
});
async function loadProfile() {
  const token = localStorage.getItem("token")
  if (!token) { window.location.href = "login.html"; return }
  try {
    const res = await fetch("https://api.alasdia.com/profile", {
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    const data = await res.json()
    console.log("PROFILE:", data)
    document.getElementById("profile-name").innerText = data.full_name || "—"
    document.getElementById("profile-email").innerText = data.email || "—"
    document.getElementById("profile-phone").innerText = data.phone || "—"
    document.getElementById("profile-account-id").innerText = data.account_id || "—"
    const phoneBadge = document.getElementById("phone-verified-badge")
    if (data.phone_verified) {
      phoneBadge.innerText = "Vérifié"
      phoneBadge.classList.remove("status-warn")
      phoneBadge.classList.add("status-ok")
    }
    const twoFaEl = document.getElementById("profile-2fa")
    twoFaEl.innerHTML = data.two_factor_enabled
      ? '<span class="status-badge status-ok">Activée</span>'
      : '<span class="status-badge status-warn">Désactivée</span>'
    document.getElementById("profile-last-login").innerText = data.last_login
      ? new Date(data.last_login).toLocaleString("fr-FR")
      : "—"
    document.getElementById("profile-plan-started").innerText = data.plan_started_at
      ? new Date(data.plan_started_at).toLocaleDateString("fr-FR")
      : "—"
    document.getElementById("profile-plan-expires").innerText = data.plan_expires_at
      ? new Date(data.plan_expires_at).toLocaleDateString("fr-FR") + (data.cancel_at_period_end ? " (résiliation prévue)" : "")
      : "—"
  } catch (err) {
    console.error("PROFILE ERROR:", err)
  }
}
document.addEventListener("DOMContentLoaded", () => {
  initStripe()
  loadPlanStatus()
  loadProfile()
})
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
  console.log("STATUS:", res.status);
  console.log("DATA:", data);
  if (!res.ok) {
    showToast(data.detail || "Erreur Stripe");
    return;
  }
  window.location.href = data.url;
}
function showUpgradeModal(feature = null) {
  const plan = localStorage.getItem("plan");
  updateUpgradeModal(plan, feature);
  const modal = new bootstrap.Modal(
    document.getElementById("modalUpgrade")
  );
  modal.show();
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
document.addEventListener("DOMContentLoaded", () => {
  const createCardBtn = document.getElementById("btn-create-card");
  if (createCardBtn) {
    createCardBtn.addEventListener("click", async () => {
      const form = document.getElementById("virtual-card-form");
      const formData = new FormData(form);
      const payload = {
        type: formData.get("type"),
        currency: formData.get("currency"),
        name: formData.get("name"),
        email: formData.get("email"),
        limit_amount: parseInt(formData.get("limit_amount") || 50000),
        address_line1: formData.get("address_line1"),
        city: formData.get("city"),
        state: formData.get("state"),
        postal_code: formData.get("postal_code"),
        country: "US"
      };
      createCardBtn.disabled = true;
      createCardBtn.innerText = "Création en cours...";
      try {
        const token = localStorage.getItem("token");
        const workspaceId = localStorage.getItem("workspace_id");
        const res = await fetch("https://api.alasdia.com/issuing/create-virtual-card", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
            "X-Workspace-Id": workspaceId
          },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
          showToast(`Carte créée avec succès ! ID: ${data.card_id}`, "success");
          form.reset();
        } else {
          showToast(data.detail || "Erreur lors de la création de la carte", "error");
        }
      } catch (err) {
        console.error("Erreur Issuing:", err);
        showToast("Erreur de connexion au serveur", "error");
      } finally {
        createCardBtn.disabled = false;
        createCardBtn.innerText = "Créer la carte virtuelle";
      }
    });
  }
});
