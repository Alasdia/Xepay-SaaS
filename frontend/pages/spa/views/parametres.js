// Vue "Paramètres" — remplace les anciennes pages dédiées Profil/KYC et
// Sécurité, retirées de la sidebar. Ouverte via l'icône ⚙️ du bandeau jaune
// (#top-banner, voir dashboard.html + spa/app.js).
//
// Page d'accueil (section absente) : 3 sections de "tuiles" cliquables, pas
// de donnée chargée ici (les tuiles sont un menu, pas des KPI en lecture).
// Chaque tuile navigue vers /parametres/:section, qui affiche le detail
// correspondant (contenu déjà fonctionnel, repris tel quel des anciennes
// vues profil.js/securite.js) avec un bouton Retour vers l'accueil.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";
import { clearSession } from "../core/state.js";
import { navigate } from "../core/router.js";

// Menu d'actions "..." des mini-tableaux (Clés d'accès) - même classes CSS
// que .row-menu/.row-menu-trigger/.row-menu-dropdown de commerce.js (voir
// parametres.css), mais déclaré ici au niveau module (une seule fois à
// l'import, jamais ré-enregistré à chaque montage de la vue) pour ne
// jamais dupliquer ce listener document au fil des navigations.
let openParamsRowMenu = null;

function closeParamsRowMenu() {
  if (!openParamsRowMenu) return;
  openParamsRowMenu.classList.remove("row-menu-dropdown-open");
  openParamsRowMenu.style.top = "";
  openParamsRowMenu.style.left = "";
  openParamsRowMenu.closest(".row-menu")?.classList.remove("open");
  openParamsRowMenu = null;
}

function toggleParamsRowMenu(trigger) {
  const row = trigger.closest(".row-menu");
  const dropdown = row.querySelector(".row-menu-dropdown");
  if (dropdown === openParamsRowMenu) {
    closeParamsRowMenu();
    return;
  }
  closeParamsRowMenu();
  dropdown.classList.add("row-menu-dropdown-open");
  row.classList.add("open");
  const rect = trigger.getBoundingClientRect();
  const menuRect = dropdown.getBoundingClientRect();
  let top = rect.bottom + 4;
  if (top + menuRect.height > window.innerHeight) top = rect.top - menuRect.height - 4;
  let left = rect.right - menuRect.width;
  if (left < 4) left = 4;
  dropdown.style.top = `${top}px`;
  dropdown.style.left = `${left}px`;
  openParamsRowMenu = dropdown;
}

document.addEventListener("click", (event) => {
  if (!openParamsRowMenu) return;
  if (event.target.closest(".row-menu-dropdown") || event.target.closest(".row-menu-trigger")) return;
  closeParamsRowMenu();
});

function tile(section, icon, title, sub, danger = false) {
  return `
    <button type="button" class="params-tile${danger ? " params-tile--danger" : ""}" data-section="${section}">
      <i class="${icon} params-tile-icon"></i>
      <div class="params-tile-text">
        <div class="params-tile-title">${title}</div>
        <div class="params-tile-sub">${sub}</div>
      </div>
    </button>
  `;
}

function sectionTitle(label) {
  return `<h6 class="params-section-title">${label}</h6>`;
}

function overviewTemplate() {
  return `
    <div class="params-page">
      <h4 class="fw-bold mb-4 text-muted"><i class="fa-solid fa-gear"></i> Paramètres</h4>

      <section class="params-section">
        ${sectionTitle("Paramètres personnels")}
        <div class="params-tiles-grid">
          ${tile("informations-personnelles", "fa-solid fa-id-card", "Informations personnelles", "Coordonnées (nom complet, email, téléphone) et vos sessions actives")}
          ${tile("authentification", "fa-solid fa-key", "Authentification", "Mot de passe, double authentification")}
          ${tile("notifications", "fa-solid fa-bell", "Paramètres de notifications", "Alertes de connexion, paiement, sécurité")}
        </div>
      </section>

      <section class="params-section">
        ${sectionTitle("Paramètres du compte")}
        <div class="params-tiles-grid">
          ${tile("stripe", "fa-brands fa-stripe", "Compte Stripe", "Vérification et paiements")}
          ${tile("abonnement", "fa-solid fa-crown", "Abonnement", "Plan et facturation")}
          ${tile("zone-dangereuse", "fa-solid fa-triangle-exclamation", "Zone dangereuse", "Suppression du compte", true)}
        </div>
      </section>

      <section class="params-section">
        ${sectionTitle("Paramètres produit")}
        <div class="params-tiles-grid">
          ${tile("cartes-virtuelles", "fa-solid fa-credit-card", "Cartes virtuelles", "Issuing")}
          ${tile("retraits", "fa-solid fa-building-columns", "Retraits & Comptes US", "LLC et comptes bancaires")}
          ${tile("infos-stripe", "fa-brands fa-stripe", "Infos compte Stripe", "Widget de gestion Stripe")}
        </div>
      </section>
    </div>
  `;
}

function detailHeader(title) {
  return `
    <div class="params-detail-header">
      <button type="button" class="params-back-btn" id="params-back"><i class="fa-solid fa-arrow-left"></i> Retour</button>
      <h5 class="mb-0 fw-bold text-muted">${title}</h5>
    </div>
  `;
}

const CANCEL_SUB_MODAL_HTML = `
<div class="modal fade" id="paramsCancelSubModal" tabindex="-1" aria-hidden="true">
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
          <button type="button" class="btn btn-danger btn-sm fw-bold px-3 py-1" style="font-size: 0.8rem; border-radius: 6px;" id="p-btn-confirm-cancel">Résilier</button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

const TWOFA_MODAL_HTML = `
<div class="modal fade" id="paramsTwoFaModal" tabindex="-1">
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
          <img id="p-twofa-qr-img" src="" alt="QR Code 2FA" style="width:200px; height:200px; border-radius:12px; margin-bottom:16px; background:white; padding:8px;">
          <div class="mb-2" style="font-size:0.75rem; color:#6b7280;">Impossible de scanner ? Entrez ce code manuellement :</div>
          <div class="mb-3"><code id="p-twofa-secret-text" style="font-size:0.8rem; word-break:break-all;"></code></div>
          <label class="form-label">Code de vérification</label>
          <input type="text" id="p-twofa-code" class="form-control text-center" placeholder="123456" maxlength="6" inputmode="numeric">
          <button type="button" class="btn btn-success w-100 mt-3" id="p-btn-verify-2fa">Vérifier et activer</button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

// --- Detail : Informations personnelles ---
function informationsPersonnellesTemplate() {
  return `
    ${detailHeader("Informations personnelles")}

    <h6 class="params-subsection-title">Coordonnées</h6>
    <div class="card-epay p-4 mb-5" style="max-width:560px;">
      <div class="params-info-row">
        <span>Nom complet</span>
        <div class="params-info-edit">
          <input type="text" id="p-name-input" class="form-control form-control-sm" placeholder="Votre nom complet">
          <button type="button" id="p-name-save-btn" class="create-client-btn">Ajouter votre nom</button>
        </div>
      </div>
      <div class="params-info-row">
        <span>Email</span>
        <strong id="p-profile-email">—</strong>
      </div>
      <div class="params-info-row">
        <span>Téléphone</span>
        <div class="params-info-edit">
          <input type="tel" id="p-phone-input" class="form-control form-control-sm" placeholder="Votre numéro de téléphone">
          <button type="button" id="p-phone-save-btn" class="create-client-btn">Ajouter votre téléphone</button>
        </div>
      </div>
    </div>

    <h6 class="params-subsection-title">Compte Google</h6>
    <p class="params-subsection-sub">Connectez-vous à Xepay à l'aide de votre compte Google.</p>
    <div class="card-epay p-4 mb-5" style="max-width:560px;">
      <div id="p-google-status" class="mb-3"></div>
      <button type="button" id="p-google-btn" class="create-client-btn">Connecter un compte Google</button>
    </div>

    <h6 class="params-subsection-title">Clés d'accès</h6>
    <p class="params-subsection-sub">Connectez-vous en toute sécurité à l'aide de vos données biométriques, du code PIN de votre appareil ou de votre clé de sécurité.</p>
    <button type="button" id="p-passkey-add-btn" class="create-client-btn mb-3">+ Ajouter une clé d'accès</button>
    <div class="table-wrap mb-5">
      <table class="table params-mini-table">
        <thead>
          <tr>
            <th>Nom de la clé</th>
            <th>Date d'ajout</th>
            <th>Dernière utilisation</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="p-passkeys-tbody">
          <tr><td colspan="4" class="text-muted">Chargement...</td></tr>
        </tbody>
      </table>
    </div>

    <h6 class="params-subsection-title">Sessions actives</h6>
    <p class="params-subsection-sub">Tous les lieux où vous êtes connecté à Xepay.</p>
    <button type="button" id="p-sessions-revoke-others-btn" class="create-client-btn mb-3">Se déconnecter de toutes les autres sessions</button>
    <div class="table-wrap">
      <table class="table params-mini-table">
        <thead>
          <tr>
            <th>Lieu</th>
            <th>Appareil</th>
            <th>Adresse IP</th>
            <th>Heure</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="p-sessions-tbody">
          <tr><td colspan="5" class="text-muted">Chargement...</td></tr>
        </tbody>
      </table>
    </div>
  `;
}

function formatSessionTime(value) {
  if (!value || isNaN(new Date(value))) return "—";
  return new Date(value).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function saveProfileField(field, value, btnId, emptyLabel) {
  const btn = document.getElementById(btnId);
  const previousLabel = btn.innerText;
  btn.disabled = true;
  btn.innerText = "Enregistrement...";
  try {
    const res = await apiFetch("/profile", { method: "PATCH", body: { [field]: value } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    showToast("Mis à jour");
    btn.innerText = value ? "Enregistrer" : emptyLabel;
  } catch (err) {
    showToast(err.message, "error");
    btn.innerText = previousLabel;
  } finally {
    btn.disabled = false;
  }
}

function updateGoogleStatus(linked, email) {
  const box = document.getElementById("p-google-status");
  const btn = document.getElementById("p-google-btn");
  if (linked) {
    box.innerHTML = `<div class="params-info-row" style="padding:0;"><span>Compte connecté</span><strong>${email || ""}</strong></div>`;
    btn.innerText = "Déconnecter le compte Google";
    btn.dataset.linked = "true";
  } else {
    box.innerHTML = `<p class="text-muted small mb-0">Aucun compte Google connecté.</p>`;
    btn.innerText = "Connecter un compte Google";
    btn.dataset.linked = "false";
  }
}

// Widget Google Identity Services (GIS), même pattern que login.js
// (initCodeClient, ux_mode:'popup') - le code obtenu est envoyé à
// /auth/google/link (authentifié) plutôt qu'à /auth/google/exchange
// (login) : ça associe le compte Google à l'utilisateur déjà connecté,
// sans jamais créer de nouvelle session.
const GOOGLE_CLIENT_ID = "366389455040-q0iie187c1ok621vbcl3vkuflib3fvgf.apps.googleusercontent.com";
let googleLinkCodeClient = null;

function getGoogleLinkCodeClient(onCode) {
  if (!window.google?.accounts?.oauth2) return null;
  googleLinkCodeClient = google.accounts.oauth2.initCodeClient({
    client_id: GOOGLE_CLIENT_ID,
    scope: "openid email profile",
    ux_mode: "popup",
    callback: onCode,
    error_callback: (err) => {
      if (err && err.type && err.type.indexOf("popup") === -1) {
        showToast("La connexion avec Google a échoué", "error");
      }
    },
  });
  return googleLinkCodeClient;
}

async function connectGoogle() {
  const client = getGoogleLinkCodeClient(async (response) => {
    if (response.error) {
      showToast("La connexion avec Google a échoué", "error");
      return;
    }
    try {
      const res = await apiFetch("/auth/google/link", {
        method: "POST",
        body: { code: response.code, redirect_uri: window.location.origin },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Erreur");
      showToast("Compte Google connecté");
      updateGoogleStatus(true, data.google_email);
    } catch (err) {
      showToast(err.message, "error");
    }
  });
  if (!client) {
    showToast("Le service Google n'a pas pu se charger, réessayez", "error");
    return;
  }
  client.requestCode();
}

async function disconnectGoogle() {
  try {
    const res = await apiFetch("/auth/google/unlink", { method: "POST" });
    if (!res.ok) throw new Error("Erreur");
    showToast("Compte Google déconnecté");
    updateGoogleStatus(false, null);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function handleGoogleBtnClick() {
  const btn = document.getElementById("p-google-btn");
  if (btn.dataset.linked === "true") disconnectGoogle();
  else connectGoogle();
}

// --- Clés d'accès (WebAuthn) ---
function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let str = "";
  for (const b of bytes) str += String.fromCharCode(b);
  return btoa(str).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64urlToBuffer(base64url) {
  const base64 = base64url.replace(/-/g, "+").replace(/_/g, "/");
  const pad = base64.length % 4 ? "=".repeat(4 - (base64.length % 4)) : "";
  const str = atob(base64 + pad);
  const bytes = new Uint8Array(str.length);
  for (let i = 0; i < str.length; i++) bytes[i] = str.charCodeAt(i);
  return bytes;
}

function passkeyRowMenuHtml(id) {
  return `
    <div class="row-menu" data-passkey-id="${id}">
      <button type="button" class="row-menu-trigger" aria-label="Actions" aria-haspopup="true">•••</button>
      <div class="row-menu-dropdown">
        <button type="button" class="row-menu-item" data-passkey-action="rename">Modifier</button>
        <button type="button" class="row-menu-item row-menu-item-danger" data-passkey-action="delete">Supprimer</button>
      </div>
    </div>
  `;
}

async function loadPasskeys() {
  const tbody = document.getElementById("p-passkeys-tbody");
  try {
    const res = await apiFetch("/passkeys");
    const list = await res.json();
    if (!res.ok) throw new Error("Erreur");
    tbody.innerHTML = list.length
      ? list.map((p) => `
          <tr>
            <td>${p.name}</td>
            <td>${formatSessionTime(p.created_at)}</td>
            <td>${p.last_used_at ? formatSessionTime(p.last_used_at) : "Jamais utilisée"}</td>
            <td>${passkeyRowMenuHtml(p.id)}</td>
          </tr>
        `).join("")
      : `<tr><td colspan="4" class="text-muted">Aucune clé d'accès enregistrée.</td></tr>`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-muted">Erreur de chargement.</td></tr>`;
  }
}

async function registerPasskey() {
  if (!window.PublicKeyCredential) {
    showToast("Les clés d'accès ne sont pas prises en charge par ce navigateur", "error");
    return;
  }
  const btn = document.getElementById("p-passkey-add-btn");
  btn.disabled = true;
  try {
    const startRes = await apiFetch("/passkeys/register/start", { method: "POST" });
    const options = await startRes.json();
    if (!startRes.ok) throw new Error(options.detail || "Erreur");

    const publicKey = {
      ...options,
      challenge: base64urlToBuffer(options.challenge),
      user: { ...options.user, id: base64urlToBuffer(options.user.id) },
      excludeCredentials: (options.excludeCredentials || []).map((c) => ({
        ...c,
        id: base64urlToBuffer(c.id),
      })),
    };

    const credential = await navigator.credentials.create({ publicKey });
    const credentialJson = {
      id: credential.id,
      rawId: bufferToBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
        attestationObject: bufferToBase64url(credential.response.attestationObject),
      },
      origin: window.location.origin,
    };

    const name = (window.prompt("Nom de cette clé d'accès (ex: iPhone de Jean)") || "").trim() || "Clé d'accès";
    const finishRes = await apiFetch("/passkeys/register/finish", {
      method: "POST",
      body: { credential: credentialJson, name },
    });
    const data = await finishRes.json();
    if (!finishRes.ok) throw new Error(data.detail || "Erreur");
    showToast("Clé d'accès ajoutée");
    loadPasskeys();
  } catch (err) {
    if (err.name !== "NotAllowedError") {
      showToast(err.message || "Erreur lors de l'ajout de la clé d'accès", "error");
    }
  } finally {
    btn.disabled = false;
  }
}

async function renamePasskey(id) {
  const name = (window.prompt("Nouveau nom de la clé d'accès :") || "").trim();
  if (!name) return;
  try {
    const res = await apiFetch(`/passkeys/${id}`, { method: "PATCH", body: { name } });
    if (!res.ok) throw new Error("Erreur");
    showToast("Clé d'accès renommée");
    loadPasskeys();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deletePasskey(id) {
  if (!confirm("Supprimer cette clé d'accès ?")) return;
  try {
    const res = await apiFetch(`/passkeys/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Erreur");
    showToast("Clé d'accès supprimée");
    loadPasskeys();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// --- Sessions actives ---
function sessionRowHtml(s) {
  const action = s.is_current
    ? `<span class="badge bg-success">Actuelle</span>`
    : `<button type="button" class="row-menu-item params-session-logout-btn" data-session-id="${s.id}">Déconnexion</button>`;
  return `
    <tr>
      <td>${s.location}</td>
      <td>${s.device}</td>
      <td>${s.ip}</td>
      <td>${formatSessionTime(s.created_at)}</td>
      <td>${action}</td>
    </tr>
  `;
}

async function loadSessions() {
  const tbody = document.getElementById("p-sessions-tbody");
  try {
    const res = await apiFetch("/sessions");
    const list = await res.json();
    if (!res.ok) throw new Error("Erreur");
    tbody.innerHTML = list.length
      ? list.map(sessionRowHtml).join("")
      : `<tr><td colspan="5" class="text-muted">Aucune session active.</td></tr>`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-muted">Erreur de chargement.</td></tr>`;
  }
}

async function revokeSession(id) {
  try {
    const res = await apiFetch(`/sessions/${id}/revoke`, { method: "POST" });
    if (!res.ok) throw new Error("Erreur");
    showToast("Session déconnectée");
    loadSessions();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function revokeOtherSessions() {
  if (!confirm("Déconnecter toutes les autres sessions ?")) return;
  try {
    const res = await apiFetch("/sessions/revoke-others", { method: "POST" });
    if (!res.ok) throw new Error("Erreur");
    showToast("Toutes les autres sessions ont été déconnectées");
    loadSessions();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function mountInformationsPersonnelles(on) {
  on(document.getElementById("p-name-save-btn"), "click", () =>
    saveProfileField("full_name", document.getElementById("p-name-input").value.trim(), "p-name-save-btn", "Ajouter votre nom")
  );
  on(document.getElementById("p-phone-save-btn"), "click", () =>
    saveProfileField("phone", document.getElementById("p-phone-input").value.trim(), "p-phone-save-btn", "Ajouter votre téléphone")
  );
  on(document.getElementById("p-google-btn"), "click", handleGoogleBtnClick);
  on(document.getElementById("p-passkey-add-btn"), "click", registerPasskey);
  on(document.getElementById("p-sessions-revoke-others-btn"), "click", revokeOtherSessions);

  on(document.getElementById("p-passkeys-tbody"), "click", (e) => {
    const trigger = e.target.closest(".row-menu-trigger");
    if (trigger) {
      toggleParamsRowMenu(trigger);
      return;
    }
    const actionBtn = e.target.closest("[data-passkey-action]");
    if (!actionBtn) return;
    const id = actionBtn.closest(".row-menu").dataset.passkeyId;
    closeParamsRowMenu();
    if (actionBtn.dataset.passkeyAction === "rename") renamePasskey(id);
    else if (actionBtn.dataset.passkeyAction === "delete") deletePasskey(id);
  });

  on(document.getElementById("p-sessions-tbody"), "click", (e) => {
    const logoutBtn = e.target.closest(".params-session-logout-btn");
    if (!logoutBtn) return;
    revokeSession(logoutBtn.dataset.sessionId);
  });

  (async () => {
    try {
      const res = await apiFetch("/profile");
      const data = await res.json();
      document.getElementById("p-profile-email").innerText = data.email || "—";
      const nameInput = document.getElementById("p-name-input");
      const nameBtn = document.getElementById("p-name-save-btn");
      nameInput.value = data.full_name || "";
      nameBtn.innerText = data.full_name ? "Enregistrer" : "Ajouter votre nom";
      const phoneInput = document.getElementById("p-phone-input");
      const phoneBtn = document.getElementById("p-phone-save-btn");
      phoneInput.value = data.phone || "";
      phoneBtn.innerText = data.phone ? "Enregistrer" : "Ajouter votre téléphone";
      updateGoogleStatus(data.google_linked, data.google_email);
    } catch (err) {
      console.error("Erreur chargement profil:", err);
    }
  })();

  loadPasskeys();
  loadSessions();
}

// --- Detail : Authentification (mot de passe + 2FA) ---
function authentificationTemplate() {
  return `
    ${detailHeader("Authentification")}
    <div class="d-flex flex-column gap-4" style="max-width:480px;">
      <div class="card-epay p-4">
        <h6 class="fw-bold mb-4 text-muted">Changer le mot de passe</h6>
        <div class="mb-3">
          <label class="form-label">Mot de passe actuel</label>
          <div class="input-wrapper">
            <input type="password" id="p-pwd-actuel" class="form-control" placeholder="••••••••">
            <span class="toggle-eye" data-toggle-pwd="p-pwd-actuel"><i class="bi bi-eye-slash"></i></span>
          </div>
        </div>
        <div class="mb-3">
          <label class="form-label">Nouveau mot de passe</label>
          <div class="input-wrapper">
            <input type="password" id="p-pwd-nouveau" class="form-control" placeholder="••••••••">
            <span class="toggle-eye" data-toggle-pwd="p-pwd-nouveau"><i class="bi bi-eye-slash"></i></span>
          </div>
          <div class="mt-2">
            <div class="progress" style="height:4px;">
              <div id="p-pwd-strength-bar" class="progress-bar" style="width:0%; transition:all 0.3s;"></div>
            </div>
            <small id="p-pwd-strength-label" class="text-muted mt-1 d-block"></small>
          </div>
        </div>
        <div class="mb-4">
          <label class="form-label">Confirmer le mot de passe</label>
          <div class="input-wrapper">
            <input type="password" id="p-pwd-confirm" class="form-control" placeholder="••••••••">
            <span class="toggle-eye" data-toggle-pwd="p-pwd-confirm"><i class="bi bi-eye-slash"></i></span>
          </div>
        </div>
        <button type="button" class="btn btn-warning fw-bold w-100" id="p-btn-change-pwd">Mettre à jour le mot de passe</button>
      </div>
      <div class="card-epay p-4">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="fw-bold mb-0 text-muted">Authentification à deux facteurs</h6>
          <span id="p-twofa-status-badge" class="badge px-3 py-2" style="background:rgba(107,114,128,0.15); color:#6b7280;">Chargement...</span>
        </div>
        <p class="text-muted" style="font-size:0.85rem;">Sécurisez votre compte avec Google Authenticator.</p>
        <button type="button" id="p-twofa-toggle-btn" class="btn btn-warning fw-bold w-100">Chargement...</button>
      </div>
    </div>
  `;
}

let twoFaModalInstance = null;
let twoFaCurrentlyEnabled = false;

function togglePwd(id) {
  const input = document.getElementById(id);
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

function checkStrength(password) {
  const bar = document.getElementById("p-pwd-strength-bar");
  const label = document.getElementById("p-pwd-strength-label");
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
  const current_password = document.getElementById("p-pwd-actuel").value;
  const new_password = document.getElementById("p-pwd-nouveau").value;
  const confirm_password = document.getElementById("p-pwd-confirm").value;
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
    document.getElementById("p-pwd-actuel").value = "";
    document.getElementById("p-pwd-nouveau").value = "";
    document.getElementById("p-pwd-confirm").value = "";
    document.getElementById("p-pwd-strength-bar").style.width = "0%";
    document.getElementById("p-pwd-strength-label").innerText = "";
  } catch (error) {
    showToast(error.message, "error");
  }
}

function updateTwoFaUI() {
  const badge = document.getElementById("p-twofa-status-badge");
  const btn = document.getElementById("p-twofa-toggle-btn");
  if (!badge || !btn) return;
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

async function loadTwoFaStatus() {
  try {
    const res = await apiFetch("/profile");
    const data = await res.json();
    twoFaCurrentlyEnabled = !!data.two_factor_enabled;
    updateTwoFaUI();
  } catch (error) {
    console.error("Erreur chargement statut 2FA :", error);
  }
}

async function setup2FA() {
  try {
    const res = await apiFetch("/2fa/setup", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    document.getElementById("p-twofa-qr-img").src = data.qr_code_base64;
    document.getElementById("p-twofa-secret-text").innerText = data.secret;
    document.getElementById("p-twofa-code").value = "";
    if (!twoFaModalInstance) {
      twoFaModalInstance = new bootstrap.Modal(document.getElementById("paramsTwoFaModal"));
    }
    twoFaModalInstance.show();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function verify2FA() {
  const code = document.getElementById("p-twofa-code").value.trim();
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

function handleTwoFaToggle() {
  if (twoFaCurrentlyEnabled) disable2FA();
  else setup2FA();
}

function mountAuthentification(on) {
  document.body.insertAdjacentHTML("beforeend", TWOFA_MODAL_HTML);
  document.querySelectorAll("[data-toggle-pwd]").forEach((el) => {
    on(el, "click", () => togglePwd(el.dataset.togglePwd));
  });
  on(document.getElementById("p-pwd-nouveau"), "input", (e) => checkStrength(e.target.value));
  on(document.getElementById("p-btn-change-pwd"), "click", changeMotDePasse);
  on(document.getElementById("p-twofa-toggle-btn"), "click", handleTwoFaToggle);
  on(document.getElementById("p-btn-verify-2fa"), "click", verify2FA);
  loadTwoFaStatus();
  return () => {
    const modalEl = document.getElementById("paramsTwoFaModal");
    const instance = modalEl && bootstrap.Modal.getInstance(modalEl);
    if (instance) {
      instance.hide();
      instance.dispose();
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("overflow");
      document.body.style.removeProperty("padding-right");
      document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    }
    modalEl?.remove();
    twoFaModalInstance = null;
  };
}

// --- Detail : Paramètres de notifications ---
function notificationsTemplate() {
  return `
    ${detailHeader("Paramètres de notifications")}
    <div class="card-epay p-4" style="max-width:480px;">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <div style="font-size:0.9rem;">Email à chaque connexion</div>
          <small class="text-muted">Soyez alerté de toute connexion</small>
        </div>
        <div class="form-check form-switch mb-0">
          <input id="p-alert-login" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
        </div>
      </div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <div style="font-size:0.9rem;">Alerte nouveau paiement</div>
          <small class="text-muted">Notification à chaque paiement reçu</small>
        </div>
        <div class="form-check form-switch mb-0">
          <input id="p-alert-payment" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
        </div>
      </div>
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <div style="font-size:0.9rem;">Alerte tentative suspecte</div>
          <small class="text-muted">Si quelqu'un tente d'accéder</small>
        </div>
        <div class="form-check form-switch mb-0">
          <input id="p-alert-suspect" class="form-check-input" type="checkbox" checked style="cursor:pointer; width:44px; height:22px;">
        </div>
      </div>
    </div>
  `;
}

async function sauvegarderAlertes() {
  try {
    const res = await apiFetch("/security/alerts", {
      method: "POST",
      body: {
        alert_login: document.getElementById("p-alert-login").checked,
        alert_payment: document.getElementById("p-alert-payment").checked,
        alert_suspect: document.getElementById("p-alert-suspect").checked,
      },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
  } catch (error) {
    console.error("Erreur sauvegarde alertes :", error);
  }
}

async function mountNotifications(on) {
  try {
    const res = await apiFetch("/security/alerts");
    const data = await res.json();
    document.getElementById("p-alert-login").checked = data.alert_login;
    document.getElementById("p-alert-payment").checked = data.alert_payment;
    document.getElementById("p-alert-suspect").checked = data.alert_suspect;
  } catch (err) {
    console.error("Erreur chargement alertes:", err);
  }
  ["p-alert-login", "p-alert-payment", "p-alert-suspect"].forEach((id) => {
    on(document.getElementById(id), "change", sauvegarderAlertes);
  });
}

// --- Detail : Compte Stripe (KYC) ---
function stripeTemplate() {
  return `
    ${detailHeader("Compte Stripe")}
    <div id="p-main-kyc-alert" style="max-width:480px;"></div>
    <div class="card-epay p-4 mt-3" style="max-width:480px;">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h6 class="fw-bold mb-0 text-muted">⚡ Vérification Stripe</h6>
        <span id="p-stripe-status-badge" class="status-badge status-warn">Non configuré</span>
      </div>
      <div class="d-flex justify-content-between align-items-center mb-3">
        <small class="text-muted">Profil complété</small>
        <div class="d-flex align-items-center gap-2">
          <div class="progress" style="width:100px; height:6px;">
            <div id="p-kyc-progress-bar" class="progress-bar bg-warning" style="width:0%"></div>
          </div>
          <small id="p-kyc-progress-text" class="text-warning">0%</small>
        </div>
      </div>
      <p class="text-muted small mb-3">Configurez Stripe pour activer les paiements internationaux.</p>
      <button type="button" id="p-stripe-action-btn" class="btn btn-warning w-100 fw-bold text-muted">Configurer Stripe</button>
    </div>
  `;
}

function setProgress(percent) {
  const bar = document.getElementById("p-kyc-progress-bar");
  const text = document.getElementById("p-kyc-progress-text");
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

async function mountStripe() {
  const res = await apiFetch("/stripe/status");
  if (!res.ok) {
    let message = "Impossible de charger les informations Stripe";
    try {
      const errData = await res.json();
      if (errData.detail === "Permission insuffisante") message = "Seul le propriétaire du compte peut configurer Stripe";
      else if (errData.detail) message = errData.detail;
    } catch (e) {}
    showToast(message, "error");
    const badge = document.getElementById("p-stripe-status-badge");
    badge.innerText = "Accès restreint";
    const btn = document.getElementById("p-stripe-action-btn");
    btn.innerText = "Réservé au propriétaire";
    btn.disabled = true;
    return;
  }
  const data = await res.json();
  updateKycProgress(data);
  const mainAlert = document.getElementById("p-main-kyc-alert");
  if (!data.connected) {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Configurez Stripe pour activer les paiements</div>`;
  } else if (data.needs_kyc) {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(255,193,7,0.15); border:1px solid rgba(255,193,7,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Vérification KYC requise pour continuer à recevoir des paiements</div>`;
  } else if (!data.future_requirements) {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(34,197,94,0.15); border:1px solid rgba(34,197,94,0.3); border-radius:12px;"><i class="fa-solid fa-circle-check"></i> Compte entièrement vérifié</div>`;
  } else {
    mainAlert.innerHTML = `<div class="alert mb-0" style="background:rgba(255,193,7,0.15); border:1px solid rgba(255,193,7,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Compte opérationnel, vérification finale incomplète</div>`;
  }
  const btn = document.getElementById("p-stripe-action-btn");
  const badge = document.getElementById("p-stripe-status-badge");
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

// --- Detail : Abonnement ---
function abonnementTemplate() {
  return `
    ${detailHeader("Abonnement")}
    <div class="card-epay p-4" style="max-width:480px;">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h6 class="fw-bold mb-0 text-muted">Plan actuel</h6>
        <span id="p-plan-badge" class="badge bg-warning text-dark px-3 py-2">—</span>
      </div>
      <div id="p-payment-failed-alert" class="alert alert-warning d-none border-0 shadow-sm p-3 mb-3" style="border-radius: 8px;">
        <p class="mb-0 text-muted" style="font-size: 13px; line-height: 1.5;">
          ⚠️ Votre dernier paiement a échoué.
          <a href="javascript:void(0);" id="p-update-card-btn" class="fw-bold text-decoration-none hover-underline" style="color: #b45309; cursor: pointer;">
            Mettez à jour votre carte pour conserver votre accès Pro
          </a>
        </p>
      </div>
      <button type="button" id="p-btn-cancel-sub" class="btn btn-cancel-custom w-100 fw-bold text-muted">Résilier mon abonnement</button>
    </div>
  `;
}

async function confirmCancelSubscription(cancelSubModalInstance) {
  const btn = document.getElementById("p-btn-confirm-cancel");
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
      await mountAbonnementData();
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

async function mountAbonnementData() {
  try {
    const res = await apiFetch("/me/plan");
    const data = await res.json();
    const alertBox = document.getElementById("p-payment-failed-alert");
    if (alertBox) alertBox.classList.toggle("d-none", data.subscription_status !== "past_due");
    const planBadge = document.getElementById("p-plan-badge");
    if (planBadge) planBadge.innerText = (data.plan || "free").toUpperCase();
    localStorage.setItem("plan", data.plan || "free");
  } catch (err) {
    console.error("Erreur chargement plan:", err);
  }
}

function mountAbonnement(on) {
  document.body.insertAdjacentHTML("beforeend", CANCEL_SUB_MODAL_HTML);
  let cancelSubModalInstance = null;
  on(document.getElementById("p-update-card-btn"), "click", async (e) => {
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
  on(document.getElementById("p-btn-cancel-sub"), "click", () => {
    cancelSubModalInstance = bootstrap.Modal.getOrCreateInstance(document.getElementById("paramsCancelSubModal"));
    cancelSubModalInstance.show();
  });
  on(document.getElementById("p-btn-confirm-cancel"), "click", () => confirmCancelSubscription(cancelSubModalInstance));
  mountAbonnementData();
  return () => {
    const modalEl = document.getElementById("paramsCancelSubModal");
    const instance = modalEl && bootstrap.Modal.getInstance(modalEl);
    if (instance) {
      instance.hide();
      instance.dispose();
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("overflow");
      document.body.style.removeProperty("padding-right");
      document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    }
    modalEl?.remove();
  };
}

// --- Detail : Sessions actives ---
// --- Detail : Zone dangereuse ---
function zoneDangereuseTemplate() {
  return `
    ${detailHeader("Zone dangereuse")}
    <div class="card-epay p-4" style="max-width:480px; border:1px solid rgba(239,68,68,0.3) !important;">
      <h6 class="fw-bold mb-3" style="color:#ef4444;">⚠️ Supprimer mon compte</h6>
      <p class="text-muted" style="font-size:0.85rem;">Cette action est irréversible. Procédez avec précaution.</p>
      <button type="button" class="btn btn-outline-danger btn-sm w-100" id="p-btn-delete-account">Supprimer mon compte</button>
    </div>
  `;
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

function mountZoneDangereuse(on) {
  on(document.getElementById("p-btn-delete-account"), "click", supprimerCompte);
}

// --- Detail : Cartes virtuelles (Issuing) ---
function cartesVirtuellesTemplate() {
  return `
    ${detailHeader("Cartes virtuelles")}
    <div class="card-epay p-4" style="max-width:480px;">
      <p class="text-muted small mb-3">Générez et gérez des cartes virtuelles pour vos dépenses professionnelles ou celles de vos équipes.</p>
      <form id="p-virtual-card-form" class="d-flex flex-column gap-2 mb-3">
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
      <button type="button" id="p-btn-create-card" class="btn btn-warning w-100 fw-bold text-dark">Créer la carte virtuelle</button>
    </div>
  `;
}

function mountCartesVirtuelles(on) {
  on(document.getElementById("p-btn-create-card"), "click", async () => {
    const btn = document.getElementById("p-btn-create-card");
    const form = document.getElementById("p-virtual-card-form");
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
  });
}

// --- Detail : Retraits & Comptes US ---
function retraitsTemplate() {
  return `
    ${detailHeader("Retraits & Comptes US")}
    <div class="card-epay p-4" style="max-width:480px;">
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
  `;
}

// --- Detail : Infos compte Stripe (widget embarqué) ---
function infosStripeTemplate() {
  return `
    ${detailHeader("Infos compte Stripe")}
    <div class="card-epay p-4">
      <div id="p-stripe-account-management"></div>
    </div>
  `;
}

async function mountInfosStripe() {
  const res = await apiFetch("/stripe/account-session", { method: "POST" });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Erreur Stripe");
  const stripeConnect = window.StripeConnect.init({
    publishableKey: window.STRIPE_PUBLISHABLE_KEY,
    fetchClientSecret: () => Promise.resolve(data.client_secret),
  });
  const component = stripeConnect.create("account-management");
  document.getElementById("p-stripe-account-management").appendChild(component);
}

const SECTIONS = {
  "informations-personnelles": { title: "Informations personnelles", template: informationsPersonnellesTemplate, mount: (on) => mountInformationsPersonnelles(on) },
  "authentification": { title: "Authentification", template: authentificationTemplate, mount: (on) => mountAuthentification(on) },
  "notifications": { title: "Paramètres de notifications", template: notificationsTemplate, mount: (on) => mountNotifications(on) },
  "stripe": { title: "Compte Stripe", template: stripeTemplate, mount: (on) => mountStripe() },
  "abonnement": { title: "Abonnement", template: abonnementTemplate, mount: (on) => mountAbonnement(on) },
  "zone-dangereuse": { title: "Zone dangereuse", template: zoneDangereuseTemplate, mount: (on) => mountZoneDangereuse(on) },
  "cartes-virtuelles": { title: "Cartes virtuelles", template: cartesVirtuellesTemplate, mount: (on) => mountCartesVirtuelles(on) },
  "retraits": { title: "Retraits & Comptes US", template: retraitsTemplate, mount: (on) => {} },
  "infos-stripe": { title: "Infos compte Stripe", template: infosStripeTemplate, mount: (on) => mountInfosStripe().catch(console.error) },
};

export async function mount(container, params = {}) {
  await setViewStyles(["responsive.css", "parametres.css", "profil.css", "sécurité.css"]);

  const boundListeners = [];
  function on(target, type, fn) {
    if (!target) return;
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  const workspaceId = params.workspaceId;
  const section = params.section;
  let extraCleanup = null;

  if (section && SECTIONS[section]) {
    const def = SECTIONS[section];
    container.innerHTML = def.template();
    on(document.getElementById("params-back"), "click", () => {
      navigate(`/dash/workspace/${encodeURIComponent(workspaceId)}/parametres`);
    });
    const result = def.mount(on);
    if (typeof result === "function") extraCleanup = result;
  } else {
    container.innerHTML = overviewTemplate();
    container.querySelectorAll("[data-section]").forEach((el) => {
      on(el, "click", () => {
        navigate(`/dash/workspace/${encodeURIComponent(workspaceId)}/parametres/${el.dataset.section}`);
      });
    });
  }

  return {
    unmount() {
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      if (extraCleanup) extraCleanup();
    },
  };
}
