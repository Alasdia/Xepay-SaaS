function togglePwd(id) {
  const input = document.getElementById(id);
  input.type = input.type === "password" ? "text" : "password";
}
function checkStrength(password) {
  const bar = document.getElementById("pwd-strength-bar");
  const label = document.getElementById("pwd-strength-label");
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  const colors = ["danger", "warning", "info", "success"];
  const texts = ["Faible", "Moyen", "Correct", "Fort"];
  if (password.length === 0) {
    bar.style.width = "0%";
    label.innerText = "";
    return;
  }
  bar.style.width = ((score / 4) * 100) + "%";
  bar.className = "progress-bar bg-" + colors[Math.max(score - 1, 0)];
  label.innerText = "Force : " + texts[Math.max(score - 1, 0)];
}
async function changeMotDePasse() {
  const current_password = document.getElementById("pwd-actuel").value;
  const new_password = document.getElementById("pwd-nouveau").value;
  const confirm_password = document.getElementById("pwd-confirm").value;
  const token = localStorage.getItem("token");
  try {
    const response = await fetch("https://api.alasdia.com/change-password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      },
      body: JSON.stringify({
        current_password,
        new_password,
        confirm_password
      })
    });
    const data = await response.json();
    console.log("Réponse backend :", data);
    if (!response.ok) {
      let message = data.detail || "Erreur";
      if (data.detail?.includes("Permission insuffisante")) {
        message = "Seul le propriétaire du compte peut modifier le mot de passe";
      }
      throw new Error(message);
    }
    showToast("Mot de passe mis à jour");
    document.getElementById("pwd-actuel").value = "";
    document.getElementById("pwd-nouveau").value = "";
    document.getElementById("pwd-confirm").value = "";
    document.getElementById("pwd-strength-bar").style.width = "0%";
    document.getElementById("pwd-strength-label").innerText = "";
  } catch (error) {
    showToast(error.message, "error");
  }
}
async function chargerUtilisateurConnecte() {
  try {
    const token = localStorage.getItem("token");
    if (!token) return;
    const response = await fetch("https://api.alasdia.com/me", {
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await response.json();
    document.getElementById("session-email").innerText =
        data.email || "Utilisateur inconnu";
    if (data.session) {
        document.getElementById("session-device").innerText =
            data.session.device || "Appareil inconnu";
        document.getElementById("session-location").innerText =
            (data.session.ip || "IP inconnue") + " - " +
            (data.session.last_seen || "Maintenant");
    }
  } catch (error) {
    console.error("Erreur user connecté :", error);
    document.getElementById("session-email").innerText =
        "Utilisateur inconnu";
  }
}
function deconnecterTout() {
  showToast("Toutes les autres sessions ont été déconnectées.");
}
chargerUtilisateurConnecte();
async function chargerAlertes() {
  const token = localStorage.getItem("token");
  const res = await fetch(
    "https://api.alasdia.com/security/alerts",
    {
      headers: {
        "Authorization": "Bearer " + token
      }
    }
  );
  const data = await res.json();
  document.getElementById("alert-login").checked =
    data.alert_login;
  document.getElementById("alert-payment").checked =
    data.alert_payment;
  document.getElementById("alert-suspect").checked =
    data.alert_suspect;
  document.getElementById("alert-login")
    .addEventListener("change", sauvegarderAlertes);
    document.getElementById("alert-payment")
    .addEventListener("change", sauvegarderAlertes);
  document.getElementById("alert-suspect")
    .addEventListener("change", sauvegarderAlertes);
}
chargerAlertes();
async function sauvegarderAlertes() {
  const token = localStorage.getItem("token");
  try { 
    const res = await fetch("https://api.alasdia.com/security/alerts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
      },
      body: JSON.stringify({
        alert_login: document.getElementById("alert-login").checked,
        alert_payment: document.getElementById("alert-payment").checked,
        alert_suspect: document.getElementById("alert-suspect").checked
      })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Erreur");
    }
    console.log("Alertes sauvegardées :", data);
  } catch (error) {
    console.error("Erreur sauvegarde alertes :", error);
  }
}
async function supprimerCompte() {
  const confirmation = confirm("Voulez-vous vraiment supprimer votre compte ?");
  if (!confirmation) return;
  const token = localStorage.getItem("token");
  try {
    const response = await fetch("https://api.alasdia.com/delete-account", {
      method: "DELETE",
      headers: {
        "Authorization": "Bearer " + token
      }
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Erreur suppression");
    }
    showToast("Compte supprimé avec succès");
    localStorage.removeItem("token");
    window.location.href = "login.html";
  } catch (error) {
    showToast(error.message, "error");
  }
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
    if (plan === "pro" || plan === "business") {
        return;
    }
    sessionStorage.setItem("openApiUpgrade", "true");
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
let twoFaModalInstance = null;
let twoFaCurrentlyEnabled = false;
async function loadTwoFaStatus() {
  const token = localStorage.getItem("token");
  const badge = document.getElementById("twofa-status-badge");
  const btn = document.getElementById("twofa-toggle-btn");
  try {
    const res = await fetch("https://api.alasdia.com/profile", {
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await res.json();
    twoFaCurrentlyEnabled = !!data.two_factor_enabled;
    updateTwoFaUI();
  } catch (error) {
    console.error("Erreur chargement statut 2FA :", error);
    badge.innerText = "Erreur";
  }
}
function updateTwoFaUI() {
  const badge = document.getElementById("twofa-status-badge");
  const btn = document.getElementById("twofa-toggle-btn");
  if (twoFaCurrentlyEnabled) {
    badge.innerText = "Activée";
    badge.style.background = "rgba(16,185,129,0.15)";
    badge.style.color = "#10b981";
    btn.innerText = "Désactiver la 2FA";
    btn.className = "btn btn-outline-danger fw-bold w-100";
  } else {
    badge.innerText = "Désactivée";
    badge.style.background = "rgba(239,68,68,0.15)";
    badge.style.color = "#ef4444";
    btn.innerText = "Activer la 2FA";
    btn.className = "btn btn-warning fw-bold w-100";
  }
}
function handleTwoFaToggle() {
  if (twoFaCurrentlyEnabled) {
    disable2FA();
  } else {
    setup2FA();
  }
}
async function setup2FA() {
  const token = localStorage.getItem("token");
  try {
    const res = await fetch("https://api.alasdia.com/2fa/setup", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    document.getElementById("twofa-qr-img").src = data.qr_code_base64;
    document.getElementById("twofa-secret-text").innerText = data.secret;
    document.getElementById("twofa-code").value = "";
    if (!twoFaModalInstance) {
      twoFaModalInstance = new bootstrap.Modal(document.getElementById("twoFaModal"));
    }
    twoFaModalInstance.show();
  } catch (error) {
    showToast(error.message, "error");
  }
}
async function verify2FA() {
  const token = localStorage.getItem("token");
  const code = document.getElementById("twofa-code").value.trim();
  if (!code || code.length !== 6) {
    showToast("Entrez un code à 6 chiffres", "error");
    return;
  }
  try {
    const res = await fetch("https://api.alasdia.com/2fa/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token
      },
      body: JSON.stringify({ code })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Code incorrect");
    showToast("2FA activée avec succès");
    twoFaCurrentlyEnabled = true;
    updateTwoFaUI();
    twoFaModalInstance.hide();
  } catch (error) {
    showToast(error.message, "error");
  }
}
async function disable2FA() {
  const confirmation = confirm("Voulez-vous vraiment désactiver la 2FA ?");
  if (!confirmation) return;
  const token = localStorage.getItem("token");
  try {
    const res = await fetch("https://api.alasdia.com/2fa/disable", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token }
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    showToast("2FA désactivée");
    twoFaCurrentlyEnabled = false;
    updateTwoFaUI();
  } catch (error) {
    showToast(error.message, "error");
  }
}
loadTwoFaStatus();