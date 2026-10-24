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
import { clearSession, getWorkspaceId, setWorkspaceId } from "../core/state.js";
import { navigate } from "../core/router.js";
import { refreshPlanBadge } from "../sidebar.js";

// Les routes réelles sont /dash/workspace/:workspaceId/parametres(/:section)
// (voir app.js) - jamais /parametres/:section seul, qui ne correspond à
// aucune route enregistrée et laisse navigate() ne rien faire (silencieux,
// aucune erreur). "me" reprend le même repli que app.js quand aucun
// workspace n'est encore mémorisé.
function navigateToSection(section, focus) {
  const query = focus ? `?focus=${encodeURIComponent(focus)}` : "";
  navigate(`/dash/workspace/${encodeURIComponent(getWorkspaceId() || "me")}/parametres/${section}${query}`);
}

// Boutons "Gérer" (Équipe et sécurité) : l'explication de l'action est
// montrée AVANT le clic, en infobulle au survol (voir .params-tooltip-btn),
// pas après coup en toast une fois arrivé sur la vue cible. "focus" (lu
// dans mount() ci-dessous) se contente de scroller vers la bonne
// sous-section et de la surligner brièvement.
const SECURITY_FOCUS_MESSAGES = {
  "2fa": "Activez l'authentification à deux facteurs pour renforcer la sécurité de votre compte.",
  "passkeys": "Ajoutez une clé d'accès (WebAuthn) pour vous connecter sans mot de passe.",
  "sessions": "Retrouvez ici toutes vos sessions actives et déconnectez celles que vous ne reconnaissez pas.",
};

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
          ${tile("informations-personnelles", "fa-solid fa-id-card", "Informations personnelles", "Nom, email, téléphone, mot de passe, sessions actives et workspaces")}
          ${tile("authentification", "fa-solid fa-key", "Authentification", "Compte Google, double authentification (2FA) avec code de sauvegarde, et clés d'accès (WebAuthn)")}
          ${tile("notifications", "fa-solid fa-bell", "Paramètres de notifications", "Email, SMS et Push pour chaque catégorie : compte, paiements, virements, solde, abonnements, clients et mises à jour Xepay")}
        </div>
      </section>

      <section class="params-section">
        ${sectionTitle("Paramètres du compte")}
        <div class="params-tiles-grid">
          ${tile("stripe", "fa-brands fa-stripe", "Compte Stripe Connect", "Informations du compte et état exact de la vérification Connect")}
          ${tile("plans-et-frais", "fa-solid fa-crown", "Plans et frais", "Plan actuel, consommation du mois et frais Xepay sur vos paiements")}
          ${tile("equipe", "fa-solid fa-users", "Équipe et sécurité", "Membres et rôles, et historique de sécurité de votre compte")}
          ${tile("entreprise", "fa-solid fa-building", "Entreprise", "Détails d'entreprise et représentant légal, via Stripe")}
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

    <div class="params-subsection-header">
      <h6 class="params-subsection-title mb-0">Coordonnées</h6>
      <button type="button" id="p-coordonnees-edit-btn" class="params-edit-btn">Modifier</button>
    </div>
    <div class="params-row-list mb-5">
      <div class="params-info-row">
        <span>Nom complet</span>
        <div class="params-row-right" id="p-field-right-full_name"></div>
      </div>
      <div class="params-info-row">
        <span>Email</span>
        <strong id="p-profile-email">—</strong>
      </div>
      <div class="params-info-row">
        <span>Téléphone</span>
        <div class="params-row-right" id="p-field-right-phone"></div>
      </div>
      <div class="params-info-row">
        <span>Mot de passe</span>
        <div class="params-row-right" id="p-field-right-password"></div>
      </div>
    </div>

    <div class="params-subsection-header" id="params-focus-sessions">
      <h6 class="params-subsection-title">Sessions actives</h6>
      <button type="button" id="p-sessions-revoke-others-btn" class="create-client-btn">Se déconnecter de toutes les autres sessions</button>
    </div>
    <p class="params-subsection-sub">Tous les lieux où vous êtes connecté à Xepay.</p>
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

    <h6 class="params-subsection-title mt-5">Workspaces</h6>
    <p class="params-subsection-sub">La liste des workspaces dont vous êtes membre.</p>
    <div class="table-wrap">
      <table class="table params-mini-table">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Id</th>
            <th>Propriétaire</th>
            <th>Rôle</th>
            <th>Date</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="p-workspaces-tbody">
          <tr><td colspan="6" class="text-muted">Chargement...</td></tr>
        </tbody>
      </table>
    </div>
  `;
}

const FIELD_LABELS = { full_name: "Votre nom complet", phone: "Votre numéro de téléphone" };
const profileFieldValues = { full_name: "", phone: "" };
let coordonneesEditing = false;

// Lecture : valeur simple, sans bouton par champ — le seul bouton
// "Modifier" est celui de l'en-tête de la section Coordonnées (voir
// toggleCoordonneesEdit), qui débloque les deux champs à la fois.
function renderCoordonneesDisplay() {
  for (const field of ["full_name", "phone"]) {
    const container = document.getElementById(`p-field-right-${field}`);
    const value = profileFieldValues[field];
    container.innerHTML = value ? `<strong>${value}</strong>` : `<span class="text-muted">Non renseigné</span>`;
  }
}

function renderCoordonneesEdit() {
  for (const field of ["full_name", "phone"]) {
    const container = document.getElementById(`p-field-right-${field}`);
    container.innerHTML = `<input type="${field === "phone" ? "tel" : "text"}" class="form-control form-control-sm" id="p-field-input-${field}" value="${profileFieldValues[field] || ""}" placeholder="${FIELD_LABELS[field]}">`;
  }
}

// Bouton unique "Modifier" de la section Coordonnées : bascule Nom
// complet + Téléphone en inputs, puis devient "Enregistrer" pour
// sauvegarder les deux en un seul appel PATCH /profile.
async function toggleCoordonneesEdit() {
  const btn = document.getElementById("p-coordonnees-edit-btn");
  if (!coordonneesEditing) {
    renderCoordonneesEdit();
    btn.innerText = "Enregistrer";
    coordonneesEditing = true;
    return;
  }

  const full_name = document.getElementById("p-field-input-full_name").value.trim();
  const phone = document.getElementById("p-field-input-phone").value.trim();
  btn.disabled = true;
  btn.innerText = "Enregistrement...";
  try {
    const res = await apiFetch("/profile", { method: "PATCH", body: { full_name, phone } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    profileFieldValues.full_name = full_name;
    profileFieldValues.phone = phone;
    showToast("Mis à jour");
    renderCoordonneesDisplay();
    btn.innerText = "Modifier";
    coordonneesEditing = false;
  } catch (err) {
    showToast(err.message, "error");
    btn.innerText = "Enregistrer";
  } finally {
    btn.disabled = false;
  }
}

// Mot de passe : jamais de valeur affichée (masqué), juste un bouton
// "Modifier" qui révèle le même petit formulaire que l'ancienne carte
// Authentification (togglePwd/checkStrength/changeMotDePasse, inchangés).
function renderPasswordDisplay() {
  const container = document.getElementById("p-field-right-password");
  container.innerHTML = `
    <strong>••••••••</strong>
    <button type="button" class="params-edit-btn" id="p-password-edit-btn">Modifier le mot de passe</button>
  `;
  document.getElementById("p-password-edit-btn").addEventListener("click", renderPasswordEdit);
}

function renderPasswordEdit() {
  const container = document.getElementById("p-field-right-password");
  container.innerHTML = `
    <div class="params-pwd-edit">
      <div class="input-wrapper">
        <input type="password" id="p-pwd-actuel" class="form-control form-control-sm" placeholder="Mot de passe actuel">
        <span class="toggle-eye" data-toggle-pwd="p-pwd-actuel"><i class="bi bi-eye-slash"></i></span>
      </div>
      <div class="input-wrapper">
        <input type="password" id="p-pwd-nouveau" class="form-control form-control-sm" placeholder="Nouveau mot de passe">
        <span class="toggle-eye" data-toggle-pwd="p-pwd-nouveau"><i class="bi bi-eye-slash"></i></span>
      </div>
      <div class="progress" style="height:4px;">
        <div id="p-pwd-strength-bar" class="progress-bar" style="width:0%; transition:all .3s;"></div>
      </div>
      <small id="p-pwd-strength-label" class="text-muted d-block"></small>
      <div class="input-wrapper">
        <input type="password" id="p-pwd-confirm" class="form-control form-control-sm" placeholder="Confirmer le mot de passe">
        <span class="toggle-eye" data-toggle-pwd="p-pwd-confirm"><i class="bi bi-eye-slash"></i></span>
      </div>
      <button type="button" class="create-client-btn" id="p-btn-change-pwd">Enregistrer</button>
    </div>
  `;
  container.querySelectorAll("[data-toggle-pwd]").forEach((el) => {
    el.addEventListener("click", () => togglePwd(el.dataset.togglePwd));
  });
  document.getElementById("p-pwd-nouveau").addEventListener("input", (e) => checkStrength(e.target.value));
  document.getElementById("p-btn-change-pwd").addEventListener("click", async () => {
    const ok = await changeMotDePasse();
    if (ok) renderPasswordDisplay();
  });
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

function updateGoogleStatus(linked) {
  const btn = document.getElementById("p-google-btn");
  btn.innerText = linked ? "Déconnecter le compte Google" : "Connecter un compte Google";
  btn.dataset.linked = linked ? "true" : "false";
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
    ? `Actuelle`
    : `<button type="button" class="params-session-logout-btn" data-session-id="${s.id}">Déconnexion</button>`;
  return `
    <tr>
      <td>${s.location}</td>
      <td>${s.device}</td>
      <td>${s.ip}</td>
      <td>${formatSessionTime(s.created_at)}</td>
      <td class="text-end">${action}</td>
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

// --- Workspaces ---
function workspaceRowMenuHtml(id, isOwn) {
  // Pas d'option "Quitter" sur son propre workspace (celui où il est
  // owner) - voir le refus côté backend (POST /workspaces/{id}/leave).
  const leaveItem = isOwn
    ? ""
    : `<button type="button" class="row-menu-item row-menu-item-danger" data-workspace-action="leave">Quitter le workspace</button>`;
  return `
    <div class="row-menu" data-workspace-id="${id}">
      <button type="button" class="row-menu-trigger" aria-label="Actions" aria-haspopup="true">•••</button>
      <div class="row-menu-dropdown">
        ${leaveItem || `<span class="row-menu-item" style="cursor:default; color:#9ca3af;">Votre workspace</span>`}
      </div>
    </div>
  `;
}

async function loadWorkspaces() {
  const tbody = document.getElementById("p-workspaces-tbody");
  try {
    const res = await apiFetch("/workspaces/me");
    const list = await res.json();
    if (!res.ok) throw new Error("Erreur");
    tbody.innerHTML = list.length
      ? list.map((w) => `
          <tr>
            <td>${w.name}</td>
            <td>${w.id}</td>
            <td>${w.owner_email}</td>
            <td>${w.role}</td>
            <td>${formatSessionTime(w.created_at)}</td>
            <td class="text-end">${workspaceRowMenuHtml(w.id, w.is_own_workspace)}</td>
          </tr>
        `).join("")
      : `<tr><td colspan="6" class="text-muted">Aucun workspace.</td></tr>`;
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-muted">Erreur de chargement.</td></tr>`;
  }
}

async function leaveWorkspace(id) {
  if (!confirm("Quitter ce workspace ?")) return;
  try {
    const res = await apiFetch(`/workspaces/${id}/leave`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    showToast("Vous avez quitté le workspace");
    loadWorkspaces();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function mountInformationsPersonnelles(on) {
  coordonneesEditing = false;
  on(document.getElementById("p-sessions-revoke-others-btn"), "click", revokeOtherSessions);

  on(document.getElementById("p-sessions-tbody"), "click", (e) => {
    const logoutBtn = e.target.closest(".params-session-logout-btn");
    if (!logoutBtn) return;
    revokeSession(logoutBtn.dataset.sessionId);
  });

  on(document.getElementById("p-workspaces-tbody"), "click", (e) => {
    const trigger = e.target.closest(".row-menu-trigger");
    if (trigger) {
      toggleParamsRowMenu(trigger);
      return;
    }
    const actionBtn = e.target.closest("[data-workspace-action]");
    if (!actionBtn) return;
    const id = actionBtn.closest(".row-menu").dataset.workspaceId;
    closeParamsRowMenu();
    if (actionBtn.dataset.workspaceAction === "leave") leaveWorkspace(id);
  });

  on(document.getElementById("p-coordonnees-edit-btn"), "click", toggleCoordonneesEdit);
  renderPasswordDisplay();

  (async () => {
    try {
      const res = await apiFetch("/profile");
      const data = await res.json();
      document.getElementById("p-profile-email").innerText = data.email || "—";
      profileFieldValues.full_name = data.full_name || "";
      profileFieldValues.phone = data.phone || "";
      renderCoordonneesDisplay();
    } catch (err) {
      console.error("Erreur chargement profil:", err);
    }
  })();

  loadSessions();
  loadWorkspaces();
}

// --- Detail : Authentification (Compte Google, 2FA, Clés d'accès) ---
function authentificationTemplate() {
  return `
    ${detailHeader("Authentification")}

    <div class="params-subsection-header">
      <h6 class="params-subsection-title">Compte Google</h6>
      <button type="button" id="p-google-btn" class="create-client-btn">Connecter un compte Google</button>
    </div>
    <p class="params-subsection-sub">Connectez-vous à Xepay à l'aide de votre compte Google.</p>

    <div class="params-subsection-header" id="params-focus-2fa">
      <h6 class="params-subsection-title">Authentification à deux facteurs</h6>
      <button type="button" id="p-twofa-toggle-btn" class="create-client-btn">Activer la 2FA</button>
    </div>
    <p class="params-subsection-sub">Renforcez la sécurité de votre compte en utilisant plusieurs méthodes d'authentification pour vérifier votre identité. Vérifiez que vous avez bien votre code de sauvegarde à 24 caractères. Vous pouvez générer un nouveau code de sauvegarde et invalider l'ancien si vous ne l'avez plus.</p>
    <div class="params-row-list mb-5">
      <div class="params-info-row">
        <span>Code de sauvegarde</span>
        <div class="params-row-right" id="p-backup-code-right"></div>
      </div>
    </div>

    <div class="params-subsection-header" id="params-focus-passkeys">
      <h6 class="params-subsection-title">Clés d'accès</h6>
      <button type="button" id="p-passkey-add-btn" class="create-client-btn">+ Ajouter une clé d'accès</button>
    </div>
    <p class="params-subsection-sub">Connectez-vous en toute sécurité à l'aide de vos données biométriques, du code PIN de votre appareil ou de votre clé de sécurité.</p>
    <div class="table-wrap">
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
    return true;
  } catch (error) {
    showToast(error.message, "error");
    return false;
  }
}

function updateTwoFaUI() {
  const btn = document.getElementById("p-twofa-toggle-btn");
  if (!btn) return;
  btn.innerText = twoFaCurrentlyEnabled ? "Désactiver la 2FA" : "Activer la 2FA";
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

// --- Code de sauvegarde 2FA ---
let backupCodeGeneratedAt = null;

function renderBackupCodeDisplay() {
  const container = document.getElementById("p-backup-code-right");
  if (!container) return;
  container.innerHTML = `
    <strong>${backupCodeGeneratedAt ? `Généré le ${formatSessionTime(backupCodeGeneratedAt)}` : "Non généré"}</strong>
    <button type="button" class="create-client-btn" id="p-backup-code-generate-btn">${backupCodeGeneratedAt ? "Générer un nouveau code" : "Générer un code de sauvegarde"}</button>
  `;
  document.getElementById("p-backup-code-generate-btn").addEventListener("click", generateBackupCode);
}

function renderBackupCodeReveal(code) {
  const container = document.getElementById("p-backup-code-right");
  container.innerHTML = `
    <div class="params-backup-code-reveal">
      <code>${code}</code>
      <button type="button" class="params-edit-btn" id="p-backup-code-copy-btn">Copier</button>
      <small class="text-muted d-block mt-1">Notez ce code, il ne sera plus jamais affiché.</small>
      <button type="button" class="create-client-btn mt-2" id="p-backup-code-done-btn">J'ai noté mon code</button>
    </div>
  `;
  document.getElementById("p-backup-code-copy-btn").addEventListener("click", () => {
    navigator.clipboard.writeText(code);
    showToast("Code copié");
  });
  document.getElementById("p-backup-code-done-btn").addEventListener("click", renderBackupCodeDisplay);
}

async function generateBackupCode() {
  if (!twoFaCurrentlyEnabled) {
    showToast("Activez d'abord la 2FA", "error");
    return;
  }
  if (backupCodeGeneratedAt && !confirm("Générer un nouveau code invalidera l'ancien. Continuer ?")) return;
  try {
    const res = await apiFetch("/2fa/backup-code/generate", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    backupCodeGeneratedAt = data.generated_at;
    renderBackupCodeReveal(data.backup_code);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function mountAuthentification(on) {
  document.body.insertAdjacentHTML("beforeend", TWOFA_MODAL_HTML);
  on(document.getElementById("p-google-btn"), "click", handleGoogleBtnClick);
  on(document.getElementById("p-twofa-toggle-btn"), "click", handleTwoFaToggle);
  on(document.getElementById("p-btn-verify-2fa"), "click", verify2FA);
  on(document.getElementById("p-passkey-add-btn"), "click", registerPasskey);

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

  (async () => {
    try {
      const res = await apiFetch("/profile");
      const data = await res.json();
      updateGoogleStatus(data.google_linked);
      backupCodeGeneratedAt = data.two_factor_backup_code_generated_at || null;
      renderBackupCodeDisplay();
    } catch (err) {
      console.error("Erreur chargement profil:", err);
    }
  })();

  loadTwoFaStatus();
  loadPasskeys();
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
// Clé de préférence = "<categorie>.<evenement>" (voir
// UserDB.notification_prefs / is_notification_enabled côté backend).
// SMS/Push : aucune infra (pas de Twilio/Firebase) - colonnes affichées
// mais désactivées, "bientôt disponible", jamais de case qui prétend
// fonctionner sans rien faire derrière.
const NOTIFICATION_CATEGORIES = [
  {
    key: "compte",
    label: "Compte",
    events: [
      { key: "new_device_login", label: "Connexion depuis un nouvel appareil" },
      { key: "account_updated", label: "Modification des informations du compte" },
      { key: "suspicious_activity", label: "Activité suspecte détectée" },
    ],
  },
  {
    key: "paiements",
    label: "Paiements",
    events: [
      { key: "payment_received", label: "Paiement reçu" },
      { key: "payment_failed", label: "Paiement échoué" },
      { key: "payment_refunded", label: "Paiement remboursé" },
    ],
  },
  {
    key: "virement",
    label: "Virement",
    events: [
      { key: "payout_success", label: "Virement réussi" },
      { key: "payout_failed", label: "Virement échoué" },
    ],
  },
  {
    key: "solde",
    label: "Solde",
    events: [
      { key: "balance_updated", label: "Solde mis à jour" },
    ],
  },
  {
    key: "produits",
    label: "Produits",
    events: [
      { key: "subscription_created", label: "Abonnement créé" },
      { key: "subscription_updated", label: "Abonnement mis à jour" },
      { key: "subscription_canceled", label: "Abonnement annulé" },
      { key: "subscription_payment_failed", label: "Paiement d'abonnement échoué" },
      { key: "invoice_paid", label: "Facture payée" },
      { key: "invoice_overdue", label: "Facture en retard" },
    ],
  },
  {
    key: "client",
    label: "Client",
    events: [
      { key: "new_client", label: "Nouveau client" },
    ],
  },
  {
    key: "mises_a_jour_xepay",
    label: "Mises à jour de Xepay",
    events: [
      { key: "product_updates", label: "Nouvelles fonctionnalités" },
    ],
  },
];

function notificationsTemplate() {
  return `
    ${detailHeader("Paramètres de notifications")}
    <p class="params-subsection-sub">Choisissez une catégorie, puis comment être notifié pour chacun de ses événements. SMS et Push arrivent bientôt.</p>
    <div class="notif-layout">
      <div class="notif-tabs">
        ${NOTIFICATION_CATEGORIES.map((cat, i) => `
          <button type="button" class="notif-tab${i === 0 ? " notif-tab--active" : ""}" data-category="${cat.key}">${cat.label}</button>
        `).join("")}
      </div>
      <div class="notif-event-list" id="p-notif-event-list"></div>
    </div>
  `;
}

function notifEventListHtml(categoryKey, prefs) {
  const category = NOTIFICATION_CATEGORIES.find((c) => c.key === categoryKey);
  const rows = category.events.map((ev) => {
    const fullKey = `${category.key}.${ev.key}`;
    const emailEnabled = prefs[fullKey] !== false;
    return `
      <tr data-event-key="${fullKey}">
        <td>${ev.label}</td>
        <td class="text-center notif-channel-col"><input type="checkbox" data-channel="email" ${emailEnabled ? "checked" : ""}></td>
        <td class="text-center notif-channel-col"><input type="checkbox" data-channel="sms" disabled title="Bientôt disponible"></td>
        <td class="text-center notif-channel-col"><input type="checkbox" data-channel="push" disabled title="Bientôt disponible"></td>
      </tr>
    `;
  }).join("");
  return `
    <table class="notif-table">
      <thead>
        <tr>
          <th></th>
          <th class="text-center notif-channel-col">Email</th>
          <th class="text-center notif-channel-col">SMS</th>
          <th class="text-center notif-channel-col">Push</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function mountNotifications(on) {
  let prefs = {};
  try {
    const res = await apiFetch("/notification-preferences");
    prefs = await res.json();
  } catch (err) {
    console.error("Erreur chargement préférences de notifications:", err);
  }

  const listEl = document.getElementById("p-notif-event-list");
  listEl.innerHTML = notifEventListHtml(NOTIFICATION_CATEGORIES[0].key, prefs);

  on(document.querySelector(".notif-tabs"), "click", (e) => {
    const tab = e.target.closest(".notif-tab");
    if (!tab) return;
    document.querySelectorAll(".notif-tab").forEach((t) => t.classList.remove("notif-tab--active"));
    tab.classList.add("notif-tab--active");
    listEl.innerHTML = notifEventListHtml(tab.dataset.category, prefs);
  });

  on(listEl, "change", async (e) => {
    const checkbox = e.target.closest('input[data-channel="email"]');
    if (!checkbox || checkbox.disabled) return;
    const row = checkbox.closest("tr");
    const key = row.dataset.eventKey;
    const newValue = checkbox.checked;
    prefs[key] = newValue;
    try {
      const res = await apiFetch("/notification-preferences", {
        method: "POST",
        body: { prefs: { [key]: newValue } },
      });
      if (!res.ok) throw new Error("Erreur");
    } catch (err) {
      checkbox.checked = !newValue;
      prefs[key] = !newValue;
      showToast("Erreur lors de la sauvegarde", "error");
    }
  });
}

// --- Detail : Compte Stripe (KYC) ---
// Colonnes cliquables (même pattern que Paramètres de notifications) :
// Informations du compte (identité) et État du compte (vérification
// Connect + action) - déplacées ici depuis Entreprise, qui ne garde que
// le widget Stripe.
const STRIPE_TABS = [
  { key: "account", label: "Informations du compte" },
  { key: "etat", label: "État du compte" },
];

function stripeTemplate() {
  return `
    ${detailHeader("Compte Stripe Connect")}
    <p class="params-subsection-sub">Données synchronisées depuis votre compte Stripe Connect.</p>
    <div id="p-stripe-body"><p class="text-muted">Chargement...</p></div>
  `;
}

function infoRowsHtml(rows) {
  if (!rows || !rows.length) return `<p class="text-muted">Aucune information disponible.</p>`;
  return `
    <div class="params-row-list">
      ${rows.map(([label, value]) => `<div class="params-info-row"><span>${label}</span><strong style="margin-left:auto;">${value || "—"}</strong></div>`).join("")}
    </div>
  `;
}

const STRIPE_ACCOUNT_TYPE_LABELS = { standard: "Standard", express: "Express", full: "Dashboard complet", custom: "Custom" };
const STRIPE_BUSINESS_TYPE_LABELS = { company: "Société", individual: "Particulier", non_profit: "Association", government_entity: "Organisme public" };

function stripeAccountRows(businessData, statusData) {
  if (!businessData && !statusData) return null;
  const a = (businessData && businessData.account) || {};
  const s = (statusData && statusData.stripe) || {};
  return [
    ["Nom du compte", a.name],
    ["Identifiant du compte", a.id],
    ["Type de compte", STRIPE_ACCOUNT_TYPE_LABELS[a.type] || a.type],
    ["Type d'entreprise", STRIPE_BUSINESS_TYPE_LABELS[a.business_type] || a.business_type],
    ["Adresse de l'entreprise", a.address],
    ["Nom de l'entreprise (Stripe)", s.business_name],
    ["Pays", s.country],
    ["Compte créé le", s.created ? formatSessionTime(s.created) : null],
  ];
}

// Traduit les codes d'exigence Stripe (business_profile.mcc,
// representative.dob.day, tos_acceptance.ip...) en libellés clairs - les
// codes bruts (jargon technique Stripe) ne veulent rien dire pour un
// marchand. Plusieurs codes bruts peuvent partager le même libellé (ex: les
// 3 champs de date de naissance) - dédupliqué à l'affichage.
const STRIPE_REQUIREMENT_LABELS = {
  "business_profile.mcc": "Secteur d'activité",
  "business_profile.url": "Site web de l'entreprise",
  "business_profile.product_description": "Description du produit ou service",
  "business_profile.support_phone": "Téléphone du service client",
  "business_profile.support_email": "Email du service client",
  "business_profile.support_address": "Adresse du service client",
  "business_type": "Type d'entreprise (société, particulier...)",
  "external_account": "Coordonnées bancaires pour recevoir les virements",
  "tos_acceptance.date": "Acceptation des conditions Stripe",
  "tos_acceptance.ip": "Acceptation des conditions Stripe",
  "settings.payments.statement_descriptor": "Libellé affiché sur les relevés bancaires de vos clients",
  "company.name": "Raison sociale de l'entreprise",
  "company.tax_id": "Numéro fiscal (SIRET/TVA) de l'entreprise",
  "company.phone": "Téléphone de l'entreprise",
  "company.address.line1": "Adresse de l'entreprise",
  "company.address.postal_code": "Adresse de l'entreprise",
  "company.address.city": "Adresse de l'entreprise",
  "company.verification.document": "Document d'immatriculation de l'entreprise",
};
for (const field of ["dob.day", "dob.month", "dob.year"]) {
  STRIPE_REQUIREMENT_LABELS[`representative.${field}`] = "Date de naissance du représentant légal";
  STRIPE_REQUIREMENT_LABELS[`individual.${field}`] = "Date de naissance";
}
for (const [key, label] of [
  ["first_name", "Prénom"],
  ["last_name", "Nom"],
  ["email", "Email"],
  ["phone", "Numéro de téléphone"],
  ["id_number", "Numéro d'identité"],
  ["verification.document", "Pièce d'identité"],
  ["address.line1", "Adresse"],
  ["address.postal_code", "Adresse"],
  ["address.city", "Adresse"],
]) {
  STRIPE_REQUIREMENT_LABELS[`representative.${key}`] = `${label} du représentant légal`;
  STRIPE_REQUIREMENT_LABELS[`individual.${key}`] = label;
}

function formatStripeRequirement(code) {
  if (STRIPE_REQUIREMENT_LABELS[code]) return STRIPE_REQUIREMENT_LABELS[code];
  // Repli pour un code non mappé : rendre au moins lisible plutôt que
  // d'afficher le jargon technique Stripe brut.
  return code.replace(/[._]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatStripeRequirementList(codes) {
  const seen = new Set();
  const labels = [];
  for (const code of codes) {
    const label = formatStripeRequirement(code);
    if (!seen.has(label)) {
      seen.add(label);
      labels.push(label);
    }
  }
  return labels;
}

function stripeStatusLabel(data) {
  if (!data || !data.stripe || !data.stripe.details_submitted) return "Non configuré";
  if (data.needs_kyc) return "Vérification requise";
  if (data.future_requirements) return "Opérationnel (vérification finale en attente)";
  return "Entièrement vérifié";
}

function stripeEtatPanelHtml() {
  const data = stripeStatusData;
  const s = (data && data.stripe) || {};
  const req = s.requirements || {};

  const enabledLabels = [];
  const suspendedLabels = [];
  (s.charges_enabled ? enabledLabels : suspendedLabels).push("Paiements");
  (s.payouts_enabled ? enabledLabels : suspendedLabels).push("Virements");

  const currentlyDue = req.currently_due || [];
  // Stripe renvoie eventually_due comme un sur-ensemble de currently_due
  // (tout ce qui est requis maintenant l'est aussi "éventuellement") - pour
  // un compte neuf, les deux listes sont donc souvent identiques. On
  // n'affiche ici que ce qui s'ajoute EN PLUS de "Requis actuellement",
  // plus utile qu'une liste dupliquée.
  const eventuallyDue = (req.eventually_due || []).filter((code) => !currentlyDue.includes(code));

  return `
    <div class="params-subsection-header">
      <h6 class="params-subsection-title mb-0">Vérification</h6>
      <button type="button" id="p-stripe-action-btn" class="create-client-btn">Configurer Stripe</button>
    </div>
    <div class="params-status-blocks">
      <div class="params-status-box">
        <h6>Statut du compte</h6>
        <div class="params-status-value">${stripeStatusLabel(data)}</div>
      </div>
      <div class="params-status-box">
        <h6>Fonctionnalités</h6>
        <ul class="params-feature-list">
          ${enabledLabels.map((l) => `<li class="params-feature-ok"><i class="fa-solid fa-circle-check"></i> ${l} activés</li>`).join("")}
          ${suspendedLabels.map((l) => `<li class="params-feature-off"><i class="fa-solid fa-circle-xmark"></i> ${l} suspendus</li>`).join("")}
        </ul>
      </div>
    </div>
    <h6 class="params-subsection-title">Éléments requis</h6>
    <p class="params-subsection-sub">Documents ou informations à fournir à Stripe pour continuer à traiter des paiements.</p>
    <div class="params-required-groups">
      <div class="params-required-group">
        <div class="params-required-label">Requis actuellement</div>
        ${currentlyDue.length ? `<ul class="params-required-list">${formatStripeRequirementList(currentlyDue).map((x) => `<li>${x}</li>`).join("")}</ul>` : `<p class="text-muted" style="font-size:13.5px;">Aucun</p>`}
      </div>
      <div class="params-required-group">
        <div class="params-required-label">Requis à terme</div>
        ${eventuallyDue.length ? `<ul class="params-required-list">${formatStripeRequirementList(eventuallyDue).map((x) => `<li>${x}</li>`).join("")}</ul>` : `<p class="text-muted" style="font-size:13.5px;">Rien de plus que ce qui est déjà requis actuellement</p>`}
      </div>
    </div>
  `;
}

function stripeAccountPanelHtml() {
  const infoHtml = (!stripeBusinessData && stripeBusinessError)
    ? `<p class="text-muted">${stripeBusinessError}</p>`
    : infoRowsHtml(stripeAccountRows(stripeBusinessData, stripeStatusData));
  return `
    ${infoHtml}
    <div class="params-subsection-header mt-5">
      <h6 class="params-subsection-title mb-0">Zone dangereuse</h6>
      <button type="button" class="params-danger-btn" id="p-stripe-delete-account-btn">Supprimer mon compte</button>
    </div>
    <p class="params-subsection-sub">
      Cette action désactive définitivement votre compte Xepay : vous ne pourrez plus vous connecter ni créer ou recevoir
      de paiements. L'accès de Xepay à votre compte Stripe Connect est coupé en même temps, qui ne pourra donc plus non
      plus être utilisé via Xepay. Aucune donnée (paiements, factures, clients, liens...) n'est pour autant supprimée :
      tout est conservé pour vos obligations comptables et légales. Votre compte Stripe reste par ailleurs entièrement
      sous votre contrôle, directement depuis votre propre Dashboard Stripe.
    </p>
  `;
}

function stripeTabContentHtml(key) {
  if (key === "account") return stripeAccountPanelHtml();
  if (key === "etat") return stripeEtatPanelHtml();
  return "";
}

function stripeTabsHtml() {
  return `
    <div class="notif-layout">
      <div class="notif-tabs">
        ${STRIPE_TABS.map((t) => `<button type="button" class="notif-tab${t.key === stripeActiveTab ? " notif-tab--active" : ""}" data-stripe-tab="${t.key}">${t.label}</button>`).join("")}
      </div>
      <div class="notif-event-list">
        ${STRIPE_TABS.map((t) => `<div data-stripe-panel="${t.key}" style="${t.key === stripeActiveTab ? "" : "display:none;"}">${stripeTabContentHtml(t.key)}</div>`).join("")}
      </div>
    </div>
  `;
}

let stripeBusinessData = null;
let stripeBusinessError = null;
let stripeStatusData = null;
let stripeActiveTab = "account";

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

function wireStripeActionButton() {
  const btn = document.getElementById("p-stripe-action-btn");
  if (!btn) return;
  const data = stripeStatusData;
  btn.disabled = false;
  if (!data.stripe || !data.stripe.details_submitted) {
    // Compte Stripe pas encore (ou pas du tout) onboardé : passe par
    // /onboarding (AccountLink type=account_onboarding), le vrai flux de
    // première inscription. stripe.Account.create_login_link (branche
    // "Compléter la vérification" ci-dessous) échoue pour un compte
    // n'ayant encore rien soumis - Stripe exige un onboarding au moins
    // entamé avant d'émettre un Login Link vers l'Express Dashboard.
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
    btn.innerText = "Compléter la vérification";
    btn.onclick = () => goToStripeLoginLink();
  } else if (data.future_requirements) {
    btn.innerText = "Compléter la vérification finale";
    btn.onclick = () => goToStripeLoginLink();
  } else {
    btn.innerText = "Compte entièrement vérifié";
    btn.disabled = true;
  }
}

async function loadStripeDetails() {
  const body = document.getElementById("p-stripe-body");
  stripeBusinessData = null;
  stripeBusinessError = null;
  stripeStatusData = null;
  stripeActiveTab = "account";
  try {
    const [bizRes, statusRes] = await Promise.all([
      apiFetch("/stripe/business-details"),
      apiFetch("/stripe/status"),
    ]);
    if (bizRes.ok) {
      stripeBusinessData = await bizRes.json();
    } else {
      try {
        const errData = await bizRes.json();
        stripeBusinessError = errData.detail ? `${errData.detail} (HTTP ${bizRes.status})` : `Erreur HTTP ${bizRes.status}`;
      } catch (e) {
        stripeBusinessError = `Erreur HTTP ${bizRes.status}`;
      }
    }
    if (statusRes.ok) {
      stripeStatusData = await statusRes.json();
    } else {
      let message = "Impossible de charger les informations Stripe";
      try {
        const errData = await statusRes.json();
        if (errData.detail === "Permission insuffisante") message = "Seul le propriétaire du compte peut configurer Stripe";
        else if (errData.detail) message = errData.detail;
      } catch (e) {}
      body.innerHTML = `<p class="text-muted">${message}</p>`;
      return;
    }
    body.innerHTML = stripeTabsHtml();
    wireStripeActionButton();
  } catch (err) {
    body.innerHTML = `<p class="text-muted">Erreur de chargement.</p>`;
  }
}

function mountStripe(on) {
  on(document.getElementById("p-stripe-body"), "click", (e) => {
    if (e.target.closest("#p-stripe-delete-account-btn")) {
      supprimerCompte();
      return;
    }
    const tabBtn = e.target.closest("[data-stripe-tab]");
    if (!tabBtn) return;
    stripeActiveTab = tabBtn.dataset.stripeTab;
    document.querySelectorAll("[data-stripe-tab]").forEach((b) => b.classList.toggle("notif-tab--active", b.dataset.stripeTab === stripeActiveTab));
    document.querySelectorAll("[data-stripe-panel]").forEach((p) => { p.style.display = p.dataset.stripePanel === stripeActiveTab ? "" : "none"; });
  });
  loadStripeDetails();
}

// --- Detail : Plans et frais ---
function plansEtFraisTemplate() {
  return `
    ${detailHeader("Plans et frais")}
    <div class="params-subsection-header">
      <h6 class="params-subsection-title mb-0">Plan actuel</h6>
      <button type="button" id="p-btn-manage-billing" class="params-edit-btn">Gérer la facturation</button>
    </div>
    <p id="p-payment-failed-alert" class="params-subsection-sub text-danger d-none mb-2">Votre dernier paiement a échoué — mettez à jour votre carte pour conserver votre accès.</p>
    <div class="params-row-list mb-5" style="max-width:560px;">
      <div class="params-info-row"><span>Plan</span><strong id="p-plan-row-name">—</strong></div>
      <div class="params-info-row"><span>Paiements reçus ce mois</span><strong id="p-plan-row-paid">—</strong></div>
      <div class="params-info-row"><span>Liens créés ce mois</span><strong id="p-plan-row-links">—</strong></div>
    </div>

    <div class="params-subsection-header">
      <h6 class="params-subsection-title mb-0">Résiliation</h6>
      <button type="button" id="p-btn-cancel-sub" class="params-danger-btn">Résilier mon abonnement</button>
    </div>
    <p class="params-subsection-sub mb-5">Résilie votre abonnement payant. Vous conservez l'accès à vos fonctionnalités actuelles jusqu'à la fin de la période déjà payée, puis votre compte repasse automatiquement au plan Free. Aucune donnée n'est supprimée.</p>

    <h6 class="params-subsection-title">Frais Xepay</h6>
    <p class="params-subsection-sub">Les 6% correspondent à la commission globale prélevée par Xepay sur chaque paiement reçu. Ils sont déduits automatiquement du montant transféré sur votre compte Stripe Connect, quel que soit le type de paiement (lien, abonnement ou facture) — vous n'avez rien à calculer ni à reverser vous-même.</p>
    <div class="params-row-list" style="max-width:560px;">
      <div class="params-info-row"><span>Frais Xepay sur chaque paiement reçu</span><strong>6% du montant</strong></div>
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
      await mountPlansEtFraisData();
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

async function mountPlansEtFraisData() {
  try {
    const res = await apiFetch("/me/plan");
    const data = await res.json();
    const alertBox = document.getElementById("p-payment-failed-alert");
    if (alertBox) alertBox.classList.toggle("d-none", data.subscription_status !== "past_due");
    const planName = (data.plan || "free");
    document.getElementById("p-plan-row-name").innerText = planName.charAt(0).toUpperCase() + planName.slice(1);
    const paidLimit = data.usage?.paid_limit;
    document.getElementById("p-plan-row-paid").innerText = `${data.usage?.paid_count ?? 0}${paidLimit != null ? " / " + paidLimit : " (illimité)"}`;
    const linksLimit = data.usage?.links_limit;
    document.getElementById("p-plan-row-links").innerText = `${data.usage?.links_used ?? 0}${linksLimit != null ? " / " + linksLimit : " (illimité)"}`;
    localStorage.setItem("plan", data.plan || "free");
  } catch (err) {
    console.error("Erreur chargement plan:", err);
  }
}

function mountPlansEtFrais(on) {
  document.body.insertAdjacentHTML("beforeend", CANCEL_SUB_MODAL_HTML);
  let cancelSubModalInstance = null;
  on(document.getElementById("p-btn-manage-billing"), "click", async () => {
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
  mountPlansEtFraisData();
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
// Zone dangereuse (suppression du compte) : déplacée dans l'onglet
// Informations du compte de Compte Stripe Connect (stripeTabContentHtml),
// plus de vue/tuile dédiée - supprimerCompte reste la même fonction,
// juste appelée depuis mountStripe désormais.
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

// --- Detail : Équipe et sécurité ---
const TEAM_ROLES = ["admin", "manager", "membre", "lecteur"];
const TEAM_ROLE_LABELS = { owner: "Propriétaire", admin: "Admin", manager: "Manager", membre: "Membre", lecteur: "Lecteur" };

const TEAM_INVITE_MODAL_HTML = `
<div class="modal fade" id="paramsInviteModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm">
    <div class="modal-content border-0 shadow-lg" style="border-radius: 14px;">
      <div class="modal-body p-3">
        <h6 class="fw-bold text-dark mb-3">Inviter un membre</h6>
        <input type="email" id="p-invite-email" class="form-control form-control-sm mb-2" placeholder="email@entreprise.com">
        <select id="p-invite-role" class="form-select form-select-sm mb-3">
          <option value="admin">Admin</option>
          <option value="manager" selected>Manager</option>
          <option value="membre">Membre</option>
          <option value="lecteur">Lecteur</option>
        </select>
        <div class="d-flex justify-content-end gap-2 pt-2 border-top">
          <button type="button" class="btn btn-light btn-sm fw-bold px-3 py-1" style="font-size: 0.8rem; border-radius: 6px;" data-bs-dismiss="modal">Annuler</button>
          <button type="button" class="btn btn-dark btn-sm fw-bold px-3 py-1" style="font-size: 0.8rem; border-radius: 6px;" id="p-invite-send-btn">Envoyer l'invitation</button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

// Colonnes cliquables (même pattern que Paramètres de notifications/
// Entreprise/Compte Stripe Connect) : Équipe (invitation, tableau des
// membres, KPI) et Historique de sécurité (statut 2FA/clés/sessions +
// journal des événements). Les 2 panneaux restent dans le DOM
// (display:none) pour ne jamais perdre l'état d'un onglet à l'autre.
const EQUIPE_TABS = [
  { key: "equipe", label: "Équipe" },
  { key: "historique", label: "Historique de sécurité" },
];

function equipeTemplate() {
  return `
    ${detailHeader("Équipe et sécurité")}
    <div class="notif-layout">
      <div class="notif-tabs" id="p-equipe-tabs">
        ${EQUIPE_TABS.map((t, i) => `<button type="button" class="notif-tab${i === 0 ? " notif-tab--active" : ""}" data-equipe-tab="${t.key}">${t.label}</button>`).join("")}
      </div>
      <div class="notif-event-list">
        <div data-equipe-panel="equipe">
          <div class="params-subsection-header">
            <h6 class="params-subsection-title mb-0">Membres de l'équipe</h6>
            <div class="d-flex align-items-center gap-2">
              <select id="p-team-workspace-switcher" class="form-select form-select-sm" style="width:auto;" aria-label="Changer de workspace"></select>
              <button type="button" id="p-team-invite-btn" class="create-client-btn">+ Inviter un membre</button>
            </div>
          </div>
          <p class="params-subsection-sub">Les personnes ayant accès à votre espace Xepay et leur rôle.</p>
          <div id="p-team-body"><p class="text-muted">Chargement...</p></div>
        </div>
        <div data-equipe-panel="historique" style="display:none;">
          <h6 class="params-subsection-title">Sécurité du compte</h6>
          <p class="params-subsection-sub">Aperçu des protections actives sur votre compte.</p>
          <div class="params-row-list mb-5">
            <div class="params-info-row">
              <span>Authentification à deux facteurs</span>
              <div class="params-row-right"><strong id="p-sec-2fa-status">—</strong><button type="button" class="params-edit-btn params-tooltip-btn" data-tooltip="${SECURITY_FOCUS_MESSAGES["2fa"]}" id="p-sec-nav-2fa">Gérer</button></div>
            </div>
            <div class="params-info-row">
              <span>Clés d'accès (WebAuthn)</span>
              <div class="params-row-right"><strong id="p-sec-passkeys-count">—</strong><button type="button" class="params-edit-btn params-tooltip-btn" data-tooltip="${SECURITY_FOCUS_MESSAGES["passkeys"]}" id="p-sec-nav-passkeys">Gérer</button></div>
            </div>
            <div class="params-info-row">
              <span>Sessions actives</span>
              <div class="params-row-right"><strong id="p-sec-sessions-count">—</strong><button type="button" class="params-edit-btn params-tooltip-btn" data-tooltip="${SECURITY_FOCUS_MESSAGES["sessions"]}" id="p-sec-nav-sessions">Gérer</button></div>
            </div>
          </div>

          <h6 class="params-subsection-title">Journal d'activité</h6>
          <p class="params-subsection-sub">Historique des actions de sécurité sur votre compte (connexions, mot de passe, 2FA, clés d'accès, équipe).</p>
          <div id="p-security-history-body"><p class="text-muted">Chargement...</p></div>
        </div>
      </div>
    </div>
  `;
}

function teamLockedHtml() {
  return `<p class="text-muted">La gestion d'équipe est réservée au plan Business. <a href="javascript:void(0)" id="p-team-upgrade-link">Voir les plans et frais</a></p>`;
}

function teamMemberRowHtml(u) {
  const roleLabel = TEAM_ROLE_LABELS[u.role] || u.role;
  const statusLabel = u.status === "suspended" ? "Suspendu" : "Actif";
  const menu = u.role === "owner"
    ? ""
    : `
      <div class="row-menu" data-user-id="${u.id}">
        <button type="button" class="row-menu-trigger" aria-label="Actions" aria-haspopup="true">•••</button>
        <div class="row-menu-dropdown">
          <button type="button" class="row-menu-item" data-team-action="role">Changer le rôle</button>
          <button type="button" class="row-menu-item" data-team-action="toggle">${u.status === "suspended" ? "Réactiver" : "Suspendre"}</button>
          <button type="button" class="row-menu-item row-menu-item-danger" data-team-action="delete">Supprimer</button>
        </div>
      </div>`;
  return `
    <tr>
      <td>${u.name}</td>
      <td>${u.email}</td>
      <td>${roleLabel}</td>
      <td>${statusLabel}</td>
      <td>${formatSessionTime(u.last)}</td>
      <td class="text-end">${menu}</td>
    </tr>
  `;
}

function teamInviteRowHtml(inv) {
  return `<tr><td>${inv.email}</td><td>${TEAM_ROLE_LABELS[inv.role] || inv.role}</td><td>${inv.days_remaining} j</td></tr>`;
}

// KPI cliquables (même .commerce-kpi que le reste de l'app, voir
// parametres.css) : "Membres actifs"/"Administrateurs" filtrent le tableau
// des membres, "Invitations en attente" fait défiler jusqu'à la table des
// invitations (ce n'est pas un attribut d'une ligne membre, rien à
// filtrer). Re-cliquer le filtre actif le désactive (retour à "Tous").
function teamKpiHtml(users, invites, activeFilter) {
  const kpis = [
    { filter: "active", label: "Membres actifs", count: users.filter((u) => u.status !== "suspended").length },
    { filter: "invites", label: "Invitations en attente", count: invites.length },
    { filter: "admin", label: "Administrateurs", count: users.filter((u) => u.role === "admin" || u.role === "owner").length },
  ];
  return `
    <div class="commerce-kpi-filters">
      ${kpis.map((k) => `
        <button type="button" class="commerce-kpi${k.filter === activeFilter ? " active" : ""}" data-team-filter="${k.filter}">
          <span class="commerce-kpi-label">${k.label}</span>
          <strong class="commerce-kpi-value">${k.count}</strong>
        </button>
      `).join("")}
    </div>
  `;
}

function filterTeamUsers(users, activeFilter) {
  if (activeFilter === "active") return users.filter((u) => u.status !== "suspended");
  if (activeFilter === "admin") return users.filter((u) => u.role === "admin" || u.role === "owner");
  return users;
}

function teamContentHtml(users, invites, activeFilter) {
  const filtered = filterTeamUsers(users, activeFilter);
  return `
    ${teamKpiHtml(users, invites, activeFilter)}
    <div class="params-table-well">
      <div class="table-wrap params-table-scroll">
        <table class="table params-mini-table">
          <thead><tr><th>Nom</th><th>Email</th><th>Rôle</th><th>Statut</th><th>Dernière connexion</th><th></th></tr></thead>
          <tbody>${filtered.length ? filtered.map(teamMemberRowHtml).join("") : `<tr><td colspan="6" class="text-muted">Aucun membre pour ce filtre.</td></tr>`}</tbody>
        </table>
      </div>
    </div>
    ${invites.length ? `
      <h6 class="params-subsection-title mt-5" id="p-team-invites-anchor">Invitations en attente</h6>
      <p class="params-subsection-sub">Invitations envoyées, pas encore acceptées.</p>
      <div class="table-wrap">
        <table class="table params-mini-table">
          <thead><tr><th>Email</th><th>Rôle</th><th>Expire dans</th></tr></thead>
          <tbody>${invites.map(teamInviteRowHtml).join("")}</tbody>
        </table>
      </div>
    ` : ""}
  `;
}

let teamUsers = [];
let teamInvites = [];
let teamActiveFilter = null;

// Sélecteur de workspace (Équipe) - même logique que multiUsers.js :
// liste les workspaces dont on est membre, présélectionne celui déjà
// mémorisé (repli sur son propre workspace sinon), et un changement
// recharge la liste des membres pour le workspace nouvellement actif.
async function loadTeamWorkspaces() {
  const select = document.getElementById("p-team-workspace-switcher");
  if (!select) return;
  try {
    const res = await apiFetch("/workspaces/me");
    const workspaces = await res.json();
    if (!res.ok || !Array.isArray(workspaces)) return;
    select.innerHTML = workspaces.map((w) => `<option value="${w.id}">${w.name}</option>`).join("");
    const saved = getWorkspaceId();
    if (saved && workspaces.some((w) => String(w.id) === saved)) {
      select.value = saved;
    } else if (workspaces.length) {
      const ownWorkspace = workspaces.find((w) => w.role === "owner") || workspaces[0];
      select.value = ownWorkspace.id;
      setWorkspaceId(ownWorkspace.id);
    }
  } catch (err) {
    console.error("Erreur chargement workspaces:", err);
  }
}

async function switchTeamWorkspace(workspaceId) {
  setWorkspaceId(workspaceId);
  await refreshPlanBadge();
  // navigate() (plutôt que loadTeam() seul) remet aussi l'URL en cohérence
  // avec le workspace actif : le routeur resynchronise workspace_id depuis
  // le segment d'URL à chaque navigation (voir app.js, onRouteChange) - si
  // seul le localStorage change, un simple rafraîchissement ou un clic
  // sidebar annule silencieusement le changement en revenant à l'ancien
  // workspace_id toujours présent dans l'URL.
  navigate(`/dash/workspace/${encodeURIComponent(workspaceId)}/parametres/equipe`, { replace: true });
}

async function loadTeam() {
  const body = document.getElementById("p-team-body");
  try {
    const res = await apiFetch("/users");
    if (res.status === 403) {
      const data = await res.json().catch(() => ({}));
      body.innerHTML = data.detail === "Fonctionnalité réservée à un plan supérieur"
        ? teamLockedHtml()
        : `<p class="text-muted">Accès à l'équipe non autorisé.</p>`;
      return;
    }
    if (!res.ok) throw new Error("Erreur");
    teamUsers = await res.json();
    teamInvites = [];
    try {
      const invRes = await apiFetch("/invites");
      if (invRes.ok) teamInvites = await invRes.json();
    } catch (e) {}
    teamActiveFilter = null;
    renderTeamContent();
  } catch (err) {
    body.innerHTML = `<p class="text-muted">Erreur de chargement.</p>`;
  }
}

function renderTeamContent() {
  const body = document.getElementById("p-team-body");
  if (body) body.innerHTML = teamContentHtml(teamUsers, teamInvites, teamActiveFilter);
}

async function changeTeamMemberRole(u) {
  const current = TEAM_ROLES.includes(u.role) ? u.role : "membre";
  const next = TEAM_ROLES[(TEAM_ROLES.indexOf(current) + 1) % TEAM_ROLES.length];
  try {
    const res = await apiFetch(`/users/${u.id}/role`, { method: "PUT", body: { role: next } });
    if (!res.ok) throw new Error("Erreur");
    showToast(`Rôle mis à jour : ${TEAM_ROLE_LABELS[next]}`);
    loadTeam();
  } catch (err) {
    showToast("Impossible de modifier ce rôle", "error");
  }
}

async function toggleTeamMember(u) {
  try {
    const res = await apiFetch(`/users/${u.id}/toggle`, { method: "POST" });
    if (!res.ok) throw new Error("Erreur");
    loadTeam();
  } catch (err) {
    showToast("Impossible de modifier ce statut", "error");
  }
}

async function deleteTeamMember(u) {
  if (!confirm(`Supprimer ${u.name} de l'équipe ?`)) return;
  try {
    const res = await apiFetch(`/users/${u.id}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Erreur");
    showToast("Membre supprimé");
    loadTeam();
  } catch (err) {
    showToast("Impossible de supprimer ce membre", "error");
  }
}

async function sendTeamInvite() {
  const email = document.getElementById("p-invite-email").value.trim();
  const role = document.getElementById("p-invite-role").value;
  if (!email) return;
  const btn = document.getElementById("p-invite-send-btn");
  btn.disabled = true;
  try {
    const res = await apiFetch("/invites", { method: "POST", body: { email, role } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");
    showToast("Invitation envoyée");
    bootstrap.Modal.getInstance(document.getElementById("paramsInviteModal"))?.hide();
    document.getElementById("p-invite-email").value = "";
    loadTeam();
  } catch (err) {
    showToast(err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function loadAccountSecuritySummary() {
  try {
    const res = await apiFetch("/profile");
    const data = await res.json();
    document.getElementById("p-sec-2fa-status").innerText = data.two_factor_enabled ? "Activée" : "Désactivée";
  } catch (err) {}
  try {
    const res = await apiFetch("/sessions");
    const list = await res.json();
    document.getElementById("p-sec-sessions-count").innerText = res.ok ? `${list.length} active${list.length > 1 ? "s" : ""}` : "—";
  } catch (err) {}
  try {
    const res = await apiFetch("/passkeys");
    const list = await res.json();
    document.getElementById("p-sec-passkeys-count").innerText = res.ok ? `${list.length}` : "—";
  } catch (err) {}
}

function securityEventRowHtml(e) {
  return `<tr><td>${e.description}</td><td>${e.ip || "—"}</td><td>${formatSessionTime(e.created_at)}</td></tr>`;
}

async function loadSecurityHistory() {
  const body = document.getElementById("p-security-history-body");
  try {
    const res = await apiFetch("/security/events");
    if (!res.ok) throw new Error("Erreur");
    const events = await res.json();
    body.innerHTML = events.length
      ? `
        <div class="table-wrap">
          <table class="table params-mini-table">
            <thead><tr><th>Événement</th><th>Adresse IP</th><th>Date</th></tr></thead>
            <tbody>${events.map(securityEventRowHtml).join("")}</tbody>
          </table>
        </div>
      `
      : `<p class="text-muted">Aucun événement enregistré pour le moment.</p>`;
  } catch (err) {
    body.innerHTML = `<p class="text-muted">Erreur de chargement.</p>`;
  }
}

function mountEquipe(on) {
  document.body.insertAdjacentHTML("beforeend", TEAM_INVITE_MODAL_HTML);

  on(document.getElementById("p-equipe-tabs"), "click", (e) => {
    const tabBtn = e.target.closest("[data-equipe-tab]");
    if (!tabBtn) return;
    document.querySelectorAll("[data-equipe-tab]").forEach((b) => b.classList.toggle("notif-tab--active", b === tabBtn));
    document.querySelectorAll("[data-equipe-panel]").forEach((p) => { p.style.display = p.dataset.equipePanel === tabBtn.dataset.equipeTab ? "" : "none"; });
  });

  on(document.getElementById("p-team-invite-btn"), "click", () => {
    bootstrap.Modal.getOrCreateInstance(document.getElementById("paramsInviteModal")).show();
  });
  on(document.getElementById("p-invite-send-btn"), "click", sendTeamInvite);
  on(document.getElementById("p-team-workspace-switcher"), "change", (e) => switchTeamWorkspace(e.target.value));

  on(document.getElementById("p-team-body"), "click", (e) => {
    const kpiBtn = e.target.closest("[data-team-filter]");
    if (kpiBtn) {
      const filter = kpiBtn.dataset.teamFilter;
      if (filter === "invites") {
        const anchor = document.getElementById("p-team-invites-anchor");
        if (anchor) anchor.scrollIntoView({ behavior: "smooth", block: "start" });
        else showToast("Aucune invitation en attente");
        return;
      }
      teamActiveFilter = teamActiveFilter === filter ? null : filter;
      renderTeamContent();
      return;
    }
    const trigger = e.target.closest(".row-menu-trigger");
    if (trigger) {
      toggleParamsRowMenu(trigger);
      return;
    }
    if (e.target.closest("#p-team-upgrade-link")) {
      navigateToSection("plans-et-frais");
      return;
    }
    const actionBtn = e.target.closest("[data-team-action]");
    if (!actionBtn) return;
    const userId = actionBtn.closest(".row-menu").dataset.userId;
    const u = teamUsers.find((x) => x.id === userId);
    closeParamsRowMenu();
    if (!u) return;
    if (actionBtn.dataset.teamAction === "role") changeTeamMemberRole(u);
    else if (actionBtn.dataset.teamAction === "toggle") toggleTeamMember(u);
    else if (actionBtn.dataset.teamAction === "delete") deleteTeamMember(u);
  });

  on(document.getElementById("p-sec-nav-2fa"), "click", () => navigateToSection("authentification", "2fa"));
  on(document.getElementById("p-sec-nav-passkeys"), "click", () => navigateToSection("authentification", "passkeys"));
  on(document.getElementById("p-sec-nav-sessions"), "click", () => navigateToSection("informations-personnelles", "sessions"));

  loadTeamWorkspaces();
  loadTeam();
  loadAccountSecuritySummary();
  loadSecurityHistory();

  return () => {
    const modalEl = document.getElementById("paramsInviteModal");
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

// --- Detail : Entreprise ---
// Un seul bloc (plus de colonnes "Informations du compte"/"État du
// compte" - déplacées dans Compte Stripe Connect) : juste le widget
// Stripe account_management, chargé à la demande via "Se connecter".
function entrepriseTemplate() {
  return `
    ${detailHeader("Entreprise")}
    <div class="params-subsection-header">
      <h6 class="params-subsection-title mb-0">Informations sur votre entreprise</h6>
      <button type="button" id="p-company-widget-btn" class="create-client-btn">Se connecter</button>
    </div>
    <p class="params-subsection-sub">Détails d'entreprise, représentant légal et documents, gérés directement via Stripe.</p>
    <div id="p-company-widget-container"></div>
  `;
}

let companyWidgetLoaded = false;

async function loadCompanyWidget() {
  const btn = document.getElementById("p-company-widget-btn");
  const container = document.getElementById("p-company-widget-container");
  if (!btn || companyWidgetLoaded) return;
  btn.disabled = true;
  btn.innerText = "Connexion...";
  try {
    const res = await apiFetch("/stripe/account-session", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur Stripe");
    const stripeConnect = window.StripeConnect.init({
      publishableKey: window.STRIPE_PUBLISHABLE_KEY,
      fetchClientSecret: () => Promise.resolve(data.client_secret),
    });
    const component = stripeConnect.create("account-management");
    container.appendChild(component);
    btn.classList.add("d-none");
    companyWidgetLoaded = true;
  } catch (err) {
    showToast(err.message || "Impossible de charger les informations", "error");
    btn.disabled = false;
    btn.innerText = "Se connecter";
  }
}

function mountEntreprise(on) {
  companyWidgetLoaded = false;
  on(document.getElementById("p-company-widget-btn"), "click", loadCompanyWidget);
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
  "stripe": { title: "Compte Stripe Connect", template: stripeTemplate, mount: (on) => mountStripe(on) },
  "plans-et-frais": { title: "Plans et frais", template: plansEtFraisTemplate, mount: (on) => mountPlansEtFrais(on) },
  "equipe": { title: "Équipe et sécurité", template: equipeTemplate, mount: (on) => mountEquipe(on) },
  "entreprise": { title: "Entreprise", template: entrepriseTemplate, mount: (on) => mountEntreprise(on) },
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

    const focusId = new URLSearchParams(location.search).get("focus");
    if (focusId) {
      const target = document.getElementById(`params-focus-${focusId}`);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("params-focus-highlight");
        setTimeout(() => target.classList.remove("params-focus-highlight"), 2200);
      }
      history.replaceState({}, "", location.pathname);
    }
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
