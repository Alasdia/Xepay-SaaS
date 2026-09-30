// Vue "Sécurité" — port fidèle de sécurité.html + sécurité.js.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";

const TEMPLATE = `
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h4 class="fw-bold mb-1 text-muted"><i class="fa-solid fa-lock"></i> Sécurité</h4>
    <small class="text-muted">Gérez la sécurité de votre compte Xepay</small>
  </div>
  <span class="badge px-3 py-2" style="background:rgba(16,185,129,0.2); color:#10b981;">✅ Compte sécurisé</span>
</div>
<div class="row g-4" style="align-items: stretch;">
  <div class="col-md-6 d-flex flex-column gap-4 h-100">
    <div class="card-epay p-4">
      <h6 class="fw-bold mb-4 text-muted">Changer le mot de passe</h6>
      <div class="mb-3">
        <label class="form-label">Mot de passe actuel</label>
        <div class="input-wrapper">
          <input type="password" id="pwd-actuel" class="form-control" placeholder="••••••••">
          <span class="toggle-eye" onclick="togglePwd('pwd-actuel')"><i class="bi bi-eye-slash"></i></span>
        </div>
      </div>
      <div class="mb-3">
        <label class="form-label">Nouveau mot de passe</label>
        <div class="input-wrapper">
          <input type="password" id="pwd-nouveau" class="form-control" placeholder="••••••••">
          <span class="toggle-eye" onclick="togglePwd('pwd-nouveau')"><i class="bi bi-eye-slash"></i></span>
        </div>
        <div class="mt-2">
          <div class="progress" style="height:4px;">
            <div id="pwd-strength-bar" class="progress-bar" style="width:0%; transition:all 0.3s;"></div>
          </div>
          <small id="pwd-strength-label" class="text-muted mt-1 d-block"></small>
        </div>
      </div>
      <div class="mb-4">
        <label class="form-label">Confirmer le mot de passe</label>
        <div class="input-wrapper">
          <input type="password" id="pwd-confirm" class="form-control" placeholder="••••••••">
          <span class="toggle-eye" onclick="togglePwd('pwd-confirm')"><i class="bi bi-eye-slash"></i></span>
        </div>
      </div>
      <button class="btn btn-warning fw-bold w-100" onclick="changeMotDePasse()">Mettre à jour le mot de passe</button>
    </div>
    <div class="card-epay p-4">
      <h6 class="fw-bold mb-4 text-muted">Sessions actives</h6>
      <div class="session-card">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="fw-bold text-muted" id="session-device">Chargement...</div>
            <small id="session-location">Chargement...</small>
            <div class="session-email" id="session-email">Chargement...</div>
          </div>
          <span class="badge bg-success">Actuelle</span>
        </div>
      </div>
      <button class="btn btn-danger btn-sm w-100 mt-2 text-muted" onclick="deconnecterTout()">Déconnecter toutes les autres sessions</button>
    </div>
  </div>
  <div class="col-md-6 d-flex flex-column gap-4 h-100">
    <div class="card-epay p-4">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h6 class="fw-bold mb-0 text-muted">Authentification à deux facteurs</h6>
        <span id="twofa-status-badge" class="badge px-3 py-2" style="background:rgba(107,114,128,0.15); color:#6b7280;">Chargement...</span>
      </div>
      <p class="text-muted" style="font-size:0.85rem;">Sécurisez votre compte avec Google Authenticator.</p>
      <button id="twofa-toggle-btn" class="btn btn-warning fw-bold w-100" onclick="handleTwoFaToggle()">Chargement...</button>
    </div>
    <div class="card-epay p-4">
      <h6 class="fw-bold mb-4 text-muted">Alertes de sécurité</h6>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <div style="font-size:0.9rem;">Email à chaque connexion</div>
          <small class="text-muted">Soyez alerté de toute connexion</small>
        </div>
        <div class="form-check form-switch mb-0">
          <input id="alert-login" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
        </div>
      </div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <div style="font-size:0.9rem;">Alerte nouveau paiement</div>
          <small class="text-muted">Notification à chaque paiement reçu</small>
        </div>
        <div class="form-check form-switch mb-0">
          <input id="alert-payment" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
        </div>
      </div>
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <div style="font-size:0.9rem;">Alerte tentative suspecte</div>
          <small class="text-muted">Si quelqu'un tente d'accéder</small>
        </div>
        <div class="form-check form-switch mb-0">
          <input id="alert-suspect" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
        </div>
      </div>
    </div>
    <div class="card-epay p-4" style="border:1px solid rgba(239,68,68,0.3) !important;">
      <h6 class="fw-bold mb-3" style="color:#ef4444;">⚠️ Zone dangereuse</h6>
      <p class="text-muted" style="font-size:0.85rem;">Ces actions sont irréversibles. Procédez avec précaution.</p>
      <button class="btn btn-outline-danger btn-sm w-100" onclick="supprimerCompte()">Supprimer mon compte</button>
    </div>
  </div>
</div>
<div class="modal fade" id="twoFaModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-dark text-dark">
      <div class="modal-header">
        <h5 class="modal-title"><i class="fa-solid fa-shield-halved"></i> Activer la 2FA</h5>
        <button class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div id="step-qr" class="text-center">
          <p class="text-muted mb-3" style="font-size:0.85rem;">
            Scannez ce QR code avec Google Authenticator (ou toute app compatible TOTP), puis entrez le code affiché pour confirmer.
          </p>
          <img id="twofa-qr-img" src="" alt="QR Code 2FA" style="width:200px; height:200px; border-radius:12px; margin-bottom:16px; background:white; padding:8px;">
          <div class="mb-2" style="font-size:0.75rem; color:#6b7280;">Impossible de scanner ? Entrez ce code manuellement :</div>
          <div class="mb-3"><code id="twofa-secret-text" style="font-size:0.8rem; word-break:break-all;"></code></div>
          <label class="form-label">Code de vérification</label>
          <input type="text" id="twofa-code" class="form-control text-center" placeholder="123456" maxlength="6" inputmode="numeric">
          <button class="btn btn-success w-100 mt-3" onclick="verify2FA()">Vérifier et activer</button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

export async function mount(container) {
  await setViewStyles(["responsive.css", "sécurité.css"]);
  container.innerHTML = TEMPLATE;

  let twoFaModalInstance = null;
  let twoFaCurrentlyEnabled = false;
  const boundListeners = [];

  function on(target, type, fn) {
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

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
    bar.style.width = (score / 4) * 100 + "%";
    bar.className = "progress-bar bg-" + colors[Math.max(score - 1, 0)];
    label.innerText = "Force : " + texts[Math.max(score - 1, 0)];
  }

  async function changeMotDePasse() {
    const current_password = document.getElementById("pwd-actuel").value;
    const new_password = document.getElementById("pwd-nouveau").value;
    const confirm_password = document.getElementById("pwd-confirm").value;
    try {
      const response = await apiFetch("/change-password", {
        method: "POST",
        body: { current_password, new_password, confirm_password },
      });
      const data = await response.json();
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
      const response = await apiFetch("/me");
      const data = await response.json();
      document.getElementById("session-email").innerText = data.email || "Utilisateur inconnu";
      if (data.session) {
        document.getElementById("session-device").innerText = data.session.device || "Appareil inconnu";
        document.getElementById("session-location").innerText =
          (data.session.ip || "IP inconnue") + " - " + (data.session.last_seen || "Maintenant");
      }
    } catch (error) {
      console.error("Erreur user connecté :", error);
      document.getElementById("session-email").innerText = "Utilisateur inconnu";
    }
  }

  function deconnecterTout() {
    showToast("Toutes les autres sessions ont été déconnectées.");
  }

  async function chargerAlertes() {
    const res = await apiFetch("/security/alerts");
    const data = await res.json();
    document.getElementById("alert-login").checked = data.alert_login;
    document.getElementById("alert-payment").checked = data.alert_payment;
    document.getElementById("alert-suspect").checked = data.alert_suspect;
    on(document.getElementById("alert-login"), "change", sauvegarderAlertes);
    on(document.getElementById("alert-payment"), "change", sauvegarderAlertes);
    on(document.getElementById("alert-suspect"), "change", sauvegarderAlertes);
  }

  async function sauvegarderAlertes() {
    try {
      const res = await apiFetch("/security/alerts", {
        method: "POST",
        body: {
          alert_login: document.getElementById("alert-login").checked,
          alert_payment: document.getElementById("alert-payment").checked,
          alert_suspect: document.getElementById("alert-suspect").checked,
        },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur");
    } catch (error) {
      console.error("Erreur sauvegarde alertes :", error);
    }
  }

  async function supprimerCompte() {
    if (!confirm("Voulez-vous vraiment supprimer votre compte ?")) return;
    try {
      const response = await apiFetch("/delete-account", { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Erreur suppression");
      showToast("Compte supprimé avec succès");
      localStorage.removeItem("token");
      window.location.href = "/login.html";
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  async function loadTwoFaStatus() {
    const badge = document.getElementById("twofa-status-badge");
    try {
      const res = await apiFetch("/profile");
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
    if (twoFaCurrentlyEnabled) disable2FA();
    else setup2FA();
  }

  async function setup2FA() {
    try {
      const res = await apiFetch("/2fa/setup", { method: "POST" });
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
    const code = document.getElementById("twofa-code").value.trim();
    if (!code || code.length !== 6) {
      showToast("Entrez un code à 6 chiffres", "error");
      return;
    }
    try {
      const res = await apiFetch("/2fa/verify", { method: "POST", body: { code } });
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
    if (!confirm("Voulez-vous vraiment désactiver la 2FA ?")) return;
    try {
      const res = await apiFetch("/2fa/disable", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur");
      showToast("2FA désactivée");
      twoFaCurrentlyEnabled = false;
      updateTwoFaUI();
    } catch (error) {
      showToast(error.message, "error");
    }
  }

  window.togglePwd = togglePwd;
  window.changeMotDePasse = changeMotDePasse;
  window.deconnecterTout = deconnecterTout;
  window.supprimerCompte = supprimerCompte;
  window.handleTwoFaToggle = handleTwoFaToggle;
  window.verify2FA = verify2FA;

  chargerUtilisateurConnecte();
  chargerAlertes();
  loadTwoFaStatus();

  return {
    unmount() {
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      delete window.togglePwd;
      delete window.changeMotDePasse;
      delete window.deconnecterTout;
      delete window.supprimerCompte;
      delete window.handleTwoFaToggle;
      delete window.verify2FA;
    },
  };
}
