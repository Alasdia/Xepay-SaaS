// Tiroir "Paramètres" partagé — chargé une seule fois par le shell
// (persistant, jamais démonté, même pattern que modalUpgrade.js/sidebar.js),
// ouvert via l'icône ⚙️ du bandeau jaune (#top-banner, voir dashboard.html).
//
// Remplace les anciennes pages dédiées "Profil / KYC" (profil.js) et
// "Sécurité" (securite.js), retirées de la sidebar : leur contenu (déjà
// fonctionnel, pas de nouvelle logique) est repris ici tel quel, réparti en
// 2 sections — "Compte Xepay" (sécurité du compte) et "Compte Stripe"
// (profil/KYC Stripe) — au lieu de 2 pages séparées.
//
// CSS : profil.css/sécurité.css définissent déjà .card-epay/.status-badge/
// etc. utilisés ci-dessous, mais ce sont des CSS "de vue" (voir
// core/styleLoader.js) qui ne doivent PAS passer par setViewStyles ici : ce
// tiroir peut s'ouvrir par-dessus n'importe quelle vue active, et
// setViewStyles décharge tout le CSS de vue en cours à chaque appel. Les
// <link> sont donc gérés à la main, ajoutés à l'ouverture et retirés à la
// fermeture, sans jamais toucher au CSS de la vue affichée en dessous.

import { apiFetch } from "../core/apiClient.js";
import { showToast } from "./toast.js";
import { clearSession } from "../core/state.js";

const VIEW_CSS_HREFS = ["/profil.css", "/sécurité.css"];
const STYLE_ID = "xepay-settings-drawer-style";

const TEMPLATE = `
<div class="xepay-settings-backdrop" id="settings-drawer-backdrop">
  <div class="xepay-settings-panel">
    <div class="xepay-settings-header">
      <h5 class="mb-0 fw-bold text-muted"><i class="fa-solid fa-gear"></i> Paramètres</h5>
      <button type="button" class="xepay-settings-close" id="settings-drawer-close" aria-label="Fermer">×</button>
    </div>
    <div class="xepay-settings-body">

      <h6 class="xepay-settings-section-title"><i class="fa-solid fa-lock"></i> Compte Xepay</h6>
      <div class="d-flex flex-column gap-4 mb-5">
        <div class="card-epay p-4">
          <h6 class="fw-bold mb-4 text-muted">Changer le mot de passe</h6>
          <div class="mb-3">
            <label class="form-label">Mot de passe actuel</label>
            <div class="input-wrapper">
              <input type="password" id="set-pwd-actuel" class="form-control" placeholder="••••••••">
              <span class="toggle-eye" data-toggle-pwd="set-pwd-actuel"><i class="bi bi-eye-slash"></i></span>
            </div>
          </div>
          <div class="mb-3">
            <label class="form-label">Nouveau mot de passe</label>
            <div class="input-wrapper">
              <input type="password" id="set-pwd-nouveau" class="form-control" placeholder="••••••••">
              <span class="toggle-eye" data-toggle-pwd="set-pwd-nouveau"><i class="bi bi-eye-slash"></i></span>
            </div>
            <div class="mt-2">
              <div class="progress" style="height:4px;">
                <div id="set-pwd-strength-bar" class="progress-bar" style="width:0%; transition:all 0.3s;"></div>
              </div>
              <small id="set-pwd-strength-label" class="text-muted mt-1 d-block"></small>
            </div>
          </div>
          <div class="mb-4">
            <label class="form-label">Confirmer le mot de passe</label>
            <div class="input-wrapper">
              <input type="password" id="set-pwd-confirm" class="form-control" placeholder="••••••••">
              <span class="toggle-eye" data-toggle-pwd="set-pwd-confirm"><i class="bi bi-eye-slash"></i></span>
            </div>
          </div>
          <button type="button" class="btn btn-warning fw-bold w-100" id="set-btn-change-pwd">Mettre à jour le mot de passe</button>
        </div>

        <div class="card-epay p-4">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="fw-bold mb-0 text-muted">Authentification à deux facteurs</h6>
            <span id="set-twofa-status-badge" class="badge px-3 py-2" style="background:rgba(107,114,128,0.15); color:#6b7280;">Chargement...</span>
          </div>
          <p class="text-muted" style="font-size:0.85rem;">Sécurisez votre compte avec Google Authenticator.</p>
          <button type="button" id="set-twofa-toggle-btn" class="btn btn-warning fw-bold w-100">Chargement...</button>
        </div>

        <div class="card-epay p-4">
          <h6 class="fw-bold mb-4 text-muted">Alertes de sécurité</h6>
          <div class="d-flex justify-content-between align-items-center mb-3">
            <div>
              <div style="font-size:0.9rem;">Email à chaque connexion</div>
              <small class="text-muted">Soyez alerté de toute connexion</small>
            </div>
            <div class="form-check form-switch mb-0">
              <input id="set-alert-login" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
            </div>
          </div>
          <div class="d-flex justify-content-between align-items-center mb-3">
            <div>
              <div style="font-size:0.9rem;">Alerte nouveau paiement</div>
              <small class="text-muted">Notification à chaque paiement reçu</small>
            </div>
            <div class="form-check form-switch mb-0">
              <input id="set-alert-payment" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
            </div>
          </div>
          <div class="d-flex justify-content-between align-items-center">
            <div>
              <div style="font-size:0.9rem;">Alerte tentative suspecte</div>
              <small class="text-muted">Si quelqu'un tente d'accéder</small>
            </div>
            <div class="form-check form-switch mb-0">
              <input id="set-alert-suspect" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
            </div>
          </div>
        </div>

        <div class="card-epay p-4">
          <h6 class="fw-bold mb-4 text-muted">Sessions actives</h6>
          <div class="session-card">
            <div class="d-flex justify-content-between align-items-center">
              <div>
                <div class="fw-bold text-muted" id="set-session-device">Chargement...</div>
                <small id="set-session-location">Chargement...</small>
                <div class="session-email" id="set-session-email">Chargement...</div>
              </div>
              <span class="badge bg-success">Actuelle</span>
            </div>
          </div>
          <button type="button" class="btn btn-danger btn-sm w-100 mt-2 text-muted" id="set-btn-logout-others">Déconnecter toutes les autres sessions</button>
        </div>

        <div class="card-epay p-4" style="border:1px solid rgba(239,68,68,0.3) !important;">
          <h6 class="fw-bold mb-3" style="color:#ef4444;">⚠️ Zone dangereuse</h6>
          <p class="text-muted" style="font-size:0.85rem;">Ces actions sont irréversibles. Procédez avec précaution.</p>
          <button type="button" class="btn btn-outline-danger btn-sm w-100" id="set-btn-delete-account">Supprimer mon compte</button>
        </div>
      </div>

      <h6 class="xepay-settings-section-title"><i class="fa-brands fa-stripe"></i> Compte Stripe</h6>
      <div class="d-flex flex-column gap-4">
        <div id="set-main-kyc-alert"></div>
        <div class="card-epay p-4">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h6 class="fw-bold mb-0 text-muted">⚡ Compte Stripe</h6>
            <span id="set-stripe-status-badge" class="status-badge status-warn">Non configuré</span>
          </div>
          <div class="d-flex justify-content-between align-items-center mb-3">
            <small class="text-muted">Profil complété</small>
            <div class="d-flex align-items-center gap-2">
              <div class="progress" style="width:100px; height:6px;">
                <div id="set-kyc-progress-bar" class="progress-bar bg-warning" style="width:0%"></div>
              </div>
              <small id="set-kyc-progress-text" class="text-warning">0%</small>
            </div>
          </div>
          <p class="text-muted small mb-3">Configurez Stripe pour activer les paiements internationaux.</p>
          <button type="button" id="set-stripe-action-btn" class="btn btn-warning w-100 fw-bold text-muted mb-4">Configurer Stripe</button>
          <div id="set-payment-failed-alert" class="alert alert-warning d-none border-0 shadow-sm p-3 mb-4" style="border-radius: 8px;">
            <p class="mb-0 text-muted" style="font-size: 13px; line-height: 1.5;">
              ⚠️ Votre dernier paiement a échoué.
              <a href="javascript:void(0);" id="set-update-card-btn" class="fw-bold text-decoration-none hover-underline" style="color: #b45309; cursor: pointer;">
                Mettez à jour votre carte pour conserver votre accès Pro
              </a>
            </p>
          </div>
          <button type="button" id="set-btn-cancel-sub" class="btn btn-cancel-custom w-100 fw-bold text-muted">Résilier mon abonnement</button>
        </div>

        <div class="card-epay p-4">
          <h6 class="fw-bold mb-3 text-muted"><i class="fa-brands fa-stripe"></i> Informations du compte Stripe</h6>
          <div id="set-stripe-account-management"></div>
        </div>

        <div class="card-epay p-4">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h6 class="fw-bold mb-0 text-muted"><i class="fa-solid fa-credit-card"></i> Cartes Virtuelles (Issuing)</h6>
            <span id="set-issuing-status-badge" class="status-badge status-warn">Vérification...</span>
          </div>
          <p class="text-muted small mb-3">Générez et gérez des cartes virtuelles pour vos dépenses professionnelles ou celles de vos équipes.</p>
          <form id="set-virtual-card-form" class="d-flex flex-column gap-2 mb-3">
            <div class="row g-2">
              <div class="col-6">
                <label class="form-label text-dark fw-bold" style="font-size: 11px;">Type</label>
                <select name="type" class="form-select form-select-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;">
                  <option value="company">Entreprise (LLC)</option>
                  <option value="individual">Particulier</option>
                </select>
              </div>
              <div class="col-6">
                <label class="form-label text-dark fw-bold" style="font-size: 11px;">Devise</label>
                <select name="currency" class="form-select form-select-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;">
                  <option value="usd">USD ($)</option>
                  <option value="eur">EUR (€)</option>
                </select>
              </div>
            </div>
            <div>
              <label class="form-label text-dark fw-bold" style="font-size: 11px;">Nom du porteur / LLC</label>
              <input type="text" name="name" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" placeholder="Ex: Xepay LLC" required>
            </div>
            <div class="row g-2">
              <div class="col-6">
                <label class="form-label text-dark fw-bold" style="font-size: 11px;">Email</label>
                <input type="email" name="email" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" placeholder="email@domain.com" required>
              </div>
              <div class="col-6">
                <label class="form-label text-dark fw-bold" style="font-size: 11px;">Limite (en centimes)</label>
                <input type="number" name="limit_amount" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" value="50000" required>
              </div>
            </div>
            <div class="row g-2 mt-1">
              <div class="col-8">
                <input type="text" name="address_line1" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" placeholder="Adresse Ligne 1 (Street)" required>
              </div>
              <div class="col-4">
                <input type="text" name="postal_code" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" placeholder="Zip code" required>
              </div>
            </div>
            <div class="row g-2">
              <div class="col-6">
                <input type="text" name="city" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" placeholder="Ville" required>
              </div>
              <div class="col-6">
                <input type="text" name="state" class="form-control form-control-sm text-dark" style="background-color: #ffffff !important; color: #000000 !important; border: 1px solid #ced4da !important;" placeholder="État (ex: DE, WY)" required>
              </div>
            </div>
          </form>
          <button type="button" id="set-btn-create-card" class="btn btn-warning w-100 fw-bold text-dark">Créer la carte virtuelle</button>
        </div>

        <div class="card-epay p-4">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h6 class="fw-bold mb-0 text-muted"><i class="fa-solid fa-credit-card"></i> Retraits & Comptes US</h6>
            <span class="badge bg-warning text-dark" style="font-size: 11px;">Requis pour Stripe Connect</span>
          </div>
          <p class="text-muted small mb-2">Les fonds sont envoyés via Stripe vers des comptes bancaires internationaux (Europe / US).</p>
          <div class="text-warning small mb-3 text-muted">
            <i class="fa-solid fa-triangle-exclamation"></i> Les méthodes locales (Mobile Money, banques africaines) ne sont pas supportées actuellement.
          </div>
          <div class="p-3 mb-3" style="background: rgba(240, 180, 41, 0.08); border: 1px dashed rgba(240, 180, 41, 0.4); border-radius: 12px;">
            <small class="d-block fw-bold text-dark mb-1">🚀 Vous n'avez pas d'entreprise enregistrée aux US ?</small>
            <small class="text-muted d-block" style="font-size: 0.8rem; line-height: 1.3;">Créez votre LLC et obtenez votre compte bancaire professionnel en quelques jours pour activer vos retraits.</small>
          </div>
          <a href="https://get.firstbase.io/lzqmlclh3nr9" target="_blank" rel="noopener noreferrer" class="btn btn-warning w-100 fw-bold text-dark text-decoration-none d-flex align-items-center justify-content-center gap-2 text-muted">
            Créer ma LLC & Compte US <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.8rem;"></i>
          </a>
        </div>
      </div>

    </div>
  </div>
</div>
`;

// #modalCancelSub / #twoFaModal : ajoutés directement à <body> (pas dans le
// panneau ci-dessus) pour la même raison que l'ancien profil.js - le panneau
// a un contexte d'empilement propre qui enfermerait sinon le z-index du
// modal Bootstrap sous son propre .modal-backdrop.
const MODALS_HTML = `
<div class="modal fade" id="settingsCancelSubModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm">
    <div class="modal-content border-0 shadow-lg" style="border-radius: 14px;">
      <div class="modal-body p-3">
        <div class="d-flex align-items-center gap-2 mb-2 text-danger">
          <i class="fa-solid fa-circle-exclamation fs-5"></i>
          <h6 class="fw-bold text-dark mb-0">Confirmer la résiliation</h6>
        </div>
        <p class="text-secondary small mb-2" style="font-size: 0.85rem; line-height: 1.4;">
          Vous conserverez vos fonctionnalités payantes jusqu'à la fin de la période en cours. Aucun nouveau prélèvement ne sera effectué.
        </p>
        <p class="text-muted small mb-3" style="font-size: 0.8rem;">À la date d'échéance, votre compte repassera automatiquement sur le plan <strong>Free</strong>.</p>
        <div class="d-flex justify-content-end gap-2 pt-2 border-top">
          <button type="button" class="btn btn-light btn-sm fw-bold px-3 py-1" style="font-size: 0.8rem; border-radius: 6px;" data-bs-dismiss="modal">Annuler</button>
          <button type="button" class="btn btn-danger btn-sm fw-bold px-3 py-1" style="font-size: 0.8rem; border-radius: 6px;" id="set-btn-confirm-cancel">Résilier</button>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="modal fade" id="settingsTwoFaModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-dark text-dark">
      <div class="modal-header">
        <h5 class="modal-title"><i class="fa-solid fa-shield-halved"></i> Activer la 2FA</h5>
        <button class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="text-center">
          <p class="text-muted mb-3" style="font-size:0.85rem;">
            Scannez ce QR code avec Google Authenticator (ou toute app compatible TOTP), puis entrez le code affiché pour confirmer.
          </p>
          <img id="set-twofa-qr-img" src="" alt="QR Code 2FA" style="width:200px; height:200px; border-radius:12px; margin-bottom:16px; background:white; padding:8px;">
          <div class="mb-2" style="font-size:0.75rem; color:#6b7280;">Impossible de scanner ? Entrez ce code manuellement :</div>
          <div class="mb-3"><code id="set-twofa-secret-text" style="font-size:0.8rem; word-break:break-all;"></code></div>
          <label class="form-label">Code de vérification</label>
          <input type="text" id="set-twofa-code" class="form-control text-center" placeholder="123456" maxlength="6" inputmode="numeric">
          <button type="button" class="btn btn-success w-100 mt-3" id="set-btn-verify-2fa">Vérifier et activer</button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

function ensureChromeStyles() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .xepay-settings-backdrop {
      position: fixed; inset: 0; top: 5vh; z-index: 250;
      background: rgba(17, 24, 39, 0.45);
      display: none;
    }
    .xepay-settings-backdrop.open { display: block; }
    .xepay-settings-panel {
      position: absolute; top: 0; right: 0; height: 100%;
      width: min(560px, 100%);
      background: #f9fafb;
      box-shadow: -12px 0 40px rgba(0,0,0,.18);
      display: flex; flex-direction: column;
      animation: xepaySettingsSlideIn .25s ease;
    }
    @keyframes xepaySettingsSlideIn {
      from { transform: translateX(100%); }
      to { transform: translateX(0); }
    }
    .xepay-settings-header {
      flex-shrink: 0; display: flex; align-items: center; justify-content: space-between;
      padding: 18px 24px; border-bottom: 1px solid #e5e7eb; background: #ffffff;
    }
    .xepay-settings-close {
      background: none; border: none; font-size: 26px; line-height: 1; color: #6b7280;
      cursor: pointer; padding: 0 4px;
    }
    .xepay-settings-close:hover { color: #111827; }
    .xepay-settings-body { flex: 1 1 auto; overflow-y: auto; padding: 24px; }
    .xepay-settings-section-title {
      font-size: 13px; text-transform: uppercase; letter-spacing: .06em; font-weight: 700;
      color: #9ca3af; margin-bottom: 16px;
    }
    @media (max-width: 640px) {
      .xepay-settings-panel { width: 100%; }
    }
  `;
  document.head.appendChild(style);
}

let built = false;
let twoFaModalInstance = null;
let cancelSubModalInstance = null;
let twoFaCurrentlyEnabled = false;
let viewCssLinks = [];

function loadViewCss() {
  if (viewCssLinks.length) return;
  viewCssLinks = VIEW_CSS_HREFS.map((href) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
    return link;
  });
}

function unloadViewCss() {
  viewCssLinks.forEach((link) => link.remove());
  viewCssLinks = [];
}

function togglePwd(id) {
  const input = document.getElementById(id);
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

function checkStrength(password) {
  const bar = document.getElementById("set-pwd-strength-bar");
  const label = document.getElementById("set-pwd-strength-label");
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
  const current_password = document.getElementById("set-pwd-actuel").value;
  const new_password = document.getElementById("set-pwd-nouveau").value;
  const confirm_password = document.getElementById("set-pwd-confirm").value;
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
    document.getElementById("set-pwd-actuel").value = "";
    document.getElementById("set-pwd-nouveau").value = "";
    document.getElementById("set-pwd-confirm").value = "";
    document.getElementById("set-pwd-strength-bar").style.width = "0%";
    document.getElementById("set-pwd-strength-label").innerText = "";
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function chargerUtilisateurConnecte() {
  try {
    const response = await apiFetch("/me");
    const data = await response.json();
    document.getElementById("set-session-email").innerText = data.email || "Utilisateur inconnu";
    if (data.session) {
      document.getElementById("set-session-device").innerText = data.session.device || "Appareil inconnu";
      document.getElementById("set-session-location").innerText =
        (data.session.ip || "IP inconnue") + " - " + (data.session.last_seen || "Maintenant");
    }
  } catch (error) {
    console.error("Erreur user connecté :", error);
    document.getElementById("set-session-email").innerText = "Utilisateur inconnu";
  }
}

function deconnecterTout() {
  showToast("Toutes les autres sessions ont été déconnectées.");
}

async function chargerAlertes() {
  const res = await apiFetch("/security/alerts");
  const data = await res.json();
  document.getElementById("set-alert-login").checked = data.alert_login;
  document.getElementById("set-alert-payment").checked = data.alert_payment;
  document.getElementById("set-alert-suspect").checked = data.alert_suspect;
}

async function sauvegarderAlertes() {
  try {
    const res = await apiFetch("/security/alerts", {
      method: "POST",
      body: {
        alert_login: document.getElementById("set-alert-login").checked,
        alert_payment: document.getElementById("set-alert-payment").checked,
        alert_suspect: document.getElementById("set-alert-suspect").checked,
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
    clearSession();
    window.location.href = "/login";
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function loadTwoFaStatus() {
  const badge = document.getElementById("set-twofa-status-badge");
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
  const badge = document.getElementById("set-twofa-status-badge");
  const btn = document.getElementById("set-twofa-toggle-btn");
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
    document.getElementById("set-twofa-qr-img").src = data.qr_code_base64;
    document.getElementById("set-twofa-secret-text").innerText = data.secret;
    document.getElementById("set-twofa-code").value = "";
    if (!twoFaModalInstance) {
      twoFaModalInstance = new bootstrap.Modal(document.getElementById("settingsTwoFaModal"));
    }
    twoFaModalInstance.show();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function verify2FA() {
  const code = document.getElementById("set-twofa-code").value.trim();
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

async function loadPlanStatus() {
  try {
    const res = await apiFetch("/me/plan");
    const data = await res.json();
    const alertBox = document.getElementById("set-payment-failed-alert");
    if (alertBox) alertBox.classList.toggle("d-none", data.subscription_status !== "past_due");
    localStorage.setItem("plan", data.plan || "free");
  } catch (err) {
    console.error("Erreur chargement plan:", err);
  }
}

function setProgress(percent) {
  const bar = document.getElementById("set-kyc-progress-bar");
  const text = document.getElementById("set-kyc-progress-text");
  bar.style.width = percent + "%";
  text.innerText = percent + "%";
  bar.classList.remove("bg-danger", "bg-warning", "bg-success");
  text.classList.remove("text-danger", "text-warning", "text-success");
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

function updateKycProgress(data) {
  let percent = 0;
  if (data.stripe) {
    percent += 20;
    if (data.stripe.charges_enabled) percent += 20;
    if (data.stripe.payouts_enabled) percent += 20;
    if (!data.needs_kyc) percent += 20;
    if (!data.future_requirements) percent += 20;
  }
  setProgress(percent);
}

async function goToStripeLoginLink() {
  const res = await apiFetch("/stripe/login-link");
  const d = await res.json();
  if (!res.ok) {
    let message = d.detail || "Impossible d'accéder à Stripe";
    if (d.detail === "Permission insuffisante") message = "Seul le propriétaire du compte peut effectuer cette vérification";
    showToast(message, "error");
    return;
  }
  window.location.href = d.url;
}

async function initStripe() {
  const res = await apiFetch("/stripe/status");
  if (!res.ok) {
    let message = "Impossible de charger les informations Stripe";
    try {
      const errData = await res.json();
      if (errData.detail === "Permission insuffisante") message = "Seul le propriétaire du compte peut configurer Stripe";
      else if (errData.detail) message = errData.detail;
    } catch (e) {}
    showToast(message, "error");
    const badge = document.getElementById("set-stripe-status-badge");
    badge.innerText = "Accès restreint";
    badge.classList.remove("status-warn", "status-pending", "status-ok");
    badge.classList.add("status-warn");
    const btn = document.getElementById("set-stripe-action-btn");
    btn.innerText = "Réservé au propriétaire";
    btn.disabled = true;
    return;
  }
  const data = await res.json();
  updateKycProgress(data);
  const mainAlert = document.getElementById("set-main-kyc-alert");
  if (!data.connected) {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Configurez Stripe pour activer les paiements</div>`;
  } else if (data.needs_kyc) {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(255,193,7,0.15); border:1px solid rgba(255,193,7,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Vérification KYC requise pour continuer à recevoir des paiements</div>`;
  } else if (!data.future_requirements) {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(34,197,94,0.15); border:1px solid rgba(34,197,94,0.3); border-radius:12px;"><i class="fa-solid fa-circle-check"></i> Compte entièrement vérifié</div>`;
  } else {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(255,193,7,0.15); border:1px solid rgba(255,193,7,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Compte opérationnel, vérification finale incomplète</div>`;
  }
  const btn = document.getElementById("set-stripe-action-btn");
  const badge = document.getElementById("set-stripe-status-badge");
  btn.disabled = false;
  btn.classList.remove("btn-warning", "btn-success");
  btn.classList.add(!data.connected || data.needs_kyc || data.future_requirements ? "btn-warning" : "btn-success");
  badge.classList.remove("status-warn", "status-pending", "status-ok");
  if (!data.connected) {
    badge.innerText = "Non configuré";
    badge.classList.add("status-warn");
    btn.innerText = "Configurer Stripe";
    btn.onclick = async () => {
      btn.innerText = "Chargement...";
      btn.disabled = true;
      try {
        const res2 = await apiFetch("/onboarding", { method: "POST" });
        const d = await res2.json();
        if (!res2.ok) {
          let message = d.detail || "Erreur Stripe onboarding";
          if (d.detail === "Permission insuffisante") message = "Seul le propriétaire du compte peut configurer Stripe";
          showToast(message, "error");
          btn.innerText = "Configurer Stripe";
          btn.disabled = false;
          return;
        }
        window.location.href = d.url;
      } catch (e) {
        btn.innerText = "Erreur, réessayer";
        btn.disabled = false;
      }
    };
  } else if (data.needs_kyc) {
    badge.innerText = "Vérification requise";
    badge.classList.add("status-pending");
    btn.innerText = "Compléter vérification";
    btn.onclick = () => goToStripeLoginLink();
  } else if (data.future_requirements) {
    badge.innerText = "Opérationnel";
    badge.classList.add("status-pending");
    btn.innerText = "Compléter la vérification finale";
    btn.disabled = false;
    btn.onclick = () => goToStripeLoginLink();
  } else {
    badge.innerText = "Entièrement vérifié";
    badge.classList.add("status-ok");
    btn.innerText = "Compte entièrement vérifié ✅";
    btn.disabled = true;
  }
}

async function confirmCancelSubscription() {
  const btn = document.getElementById("set-btn-confirm-cancel");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Résiliation...";
  }
  try {
    const res = await apiFetch("/me/plan/cancel", { method: "POST" });
    const data = await res.json();
    if (cancelSubModalInstance) cancelSubModalInstance.hide();
    if (res.ok) {
      showToast(data.message || "Abonnement résilié avec succès.", "warning");
      await loadPlanStatus();
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

async function loadStripeAccountManagement() {
  const container = document.getElementById("set-stripe-account-management");
  container.innerHTML = "";
  const res = await apiFetch("/stripe/account-session", { method: "POST" });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Erreur Stripe");
  const stripeConnect = window.StripeConnect.init({
    publishableKey: window.STRIPE_PUBLISHABLE_KEY,
    fetchClientSecret: () => Promise.resolve(data.client_secret),
  });
  const component = stripeConnect.create("account-management");
  container.appendChild(component);
}

async function createVirtualCard() {
  const btn = document.getElementById("set-btn-create-card");
  const form = document.getElementById("set-virtual-card-form");
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
    country: "US",
  };
  btn.disabled = true;
  btn.innerText = "Création en cours...";
  try {
    const res = await apiFetch("/issuing/create-virtual-card", { method: "POST", body: payload });
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
    btn.disabled = false;
    btn.innerText = "Créer la carte virtuelle";
  }
}

function build() {
  if (built) return;
  built = true;
  ensureChromeStyles();
  document.body.insertAdjacentHTML("beforeend", TEMPLATE);
  document.body.insertAdjacentHTML("beforeend", MODALS_HTML);

  const backdrop = document.getElementById("settings-drawer-backdrop");
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeSettingsDrawer();
  });
  document.getElementById("settings-drawer-close").addEventListener("click", closeSettingsDrawer);

  document.querySelectorAll("[data-toggle-pwd]").forEach((el) => {
    el.addEventListener("click", () => togglePwd(el.dataset.togglePwd));
  });
  document.getElementById("set-pwd-nouveau").addEventListener("input", (e) => checkStrength(e.target.value));
  document.getElementById("set-btn-change-pwd").addEventListener("click", changeMotDePasse);
  document.getElementById("set-btn-logout-others").addEventListener("click", deconnecterTout);
  document.getElementById("set-btn-delete-account").addEventListener("click", supprimerCompte);
  document.getElementById("set-twofa-toggle-btn").addEventListener("click", handleTwoFaToggle);
  document.getElementById("set-btn-verify-2fa").addEventListener("click", verify2FA);
  ["set-alert-login", "set-alert-payment", "set-alert-suspect"].forEach((id) => {
    document.getElementById(id).addEventListener("change", sauvegarderAlertes);
  });

  document.getElementById("set-btn-cancel-sub").addEventListener("click", () => {
    cancelSubModalInstance = bootstrap.Modal.getOrCreateInstance(document.getElementById("settingsCancelSubModal"));
    cancelSubModalInstance.show();
  });
  document.getElementById("set-btn-confirm-cancel").addEventListener("click", confirmCancelSubscription);
  document.getElementById("set-update-card-btn").addEventListener("click", async (e) => {
    e.preventDefault();
    try {
      const res = await apiFetch("/me/create-portal-session", { method: "POST" });
      const data = await res.json();
      if (res.ok && data.url) window.location.href = data.url;
      else showToast(data.detail || "Impossible d'accéder au portail de facturation.", "error");
    } catch (err) {
      console.error("Erreur redirection portail:", err);
    }
  });
  document.getElementById("set-btn-create-card").addEventListener("click", createVirtualCard);
}

export function closeSettingsDrawer() {
  document.getElementById("settings-drawer-backdrop")?.classList.remove("open");
  unloadViewCss();
}

export function openSettingsDrawer() {
  build();
  loadViewCss();
  document.getElementById("settings-drawer-backdrop").classList.add("open");

  // Rechargé à chaque ouverture (statuts potentiellement changés depuis -
  // Stripe/2FA/plan en particulier) plutôt qu'une seule fois à la création.
  initStripe();
  loadPlanStatus();
  chargerUtilisateurConnecte();
  chargerAlertes();
  loadTwoFaStatus();
  loadStripeAccountManagement().catch(console.error);
}
