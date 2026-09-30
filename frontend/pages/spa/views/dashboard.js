// Vue "Dashboard" (accueil) — port fidèle de dashboard.html + dashboard.js.
// La consommation du token OAuth Google (ancien code en tête de
// dashboard.js) est traitée une seule fois au niveau du shell (spa/app.js),
// avant le démarrage du router — elle ne concerne pas le rendu de cette vue.
import { apiFetch } from "../core/apiClient.js";
import { getWorkspaceId, setWorkspaceId, getPlan, setPlan } from "../core/state.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";
import { showUpgradeModal, upgrade } from "../shared/modalUpgrade.js";
import { navigate } from "../core/router.js";
import { refreshPlanBadge } from "../sidebar.js";

const TEMPLATE = `
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h4 class="fw-bold mb-1 text-muted" id="welcomeText">Bienvenu</h4>
    <small class="text-muted d-block">
      Plan <span id="plan-label" class="text-success fw-bold">Free</span> 10 paiements par mois
    </small>
    <small class="text-muted d-block mt-1">
      Commencez à recevoir vos paiements facilement.
      Passez au plan Pro pour plus de volume et de fonctionnalités.
    </small>
  </div>
  <div id="export-actions" style="display: flex; align-items: center; gap: 16px; flex-shrink: 0;">
    <select id="workspaceSwitcher" style="margin-right: 16px;"></select>
    <button class="btn btn-warning fw-bold px-4 upgrade-btn" style="white-space: nowrap;">⚡ Passer au Pro</button>
  </div>
</div>
<div class="p-3 mb-4 d-flex justify-content-between align-items-center"
     style="background:rgba(245,158,11,0.15); border:1px solid rgba(245,158,11,0.3); border-radius:12px;">
  <span>🚀 <strong>10/10 Paiements </strong> réussi — Passez au Pro pour ne plus être limité.</span>
  <button class="btn btn-warning btn-sm fw-bold ms-3 upgrade-btn">Upgrader →</button>
</div>
<div class="row g-3 mb-3">
  <div class="col-md-4">
    <div class="wallet-hover-wrapper position-relative">
      <div class="card-epay p-3">
        <div class="d-flex justify-content-between align-items-start">
          <div>
            <small class="text-muted"> Total Solde</small>
            <h4 id="wallet-balance" class="fw-bold mt-1 text-dark text-muted">0 XOF</h4>
          </div>
          <button id="withdrawBtn" class="btn btn-outline-light">Retirer</button>
        </div>
        <small class="text-muted d-block mt-1">Disponible maintenant</small>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card-epay p-3">
      <small class="text-muted">Montant verrouillé</small>
      <h4 id="locked-amount" class="fw-bold mt-1 text-dark tex text-muted">0 XOF</h4>
      <small id="nextAvailableText" class="text-muted d-block mt-1"></small>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card-epay p-3">
      <small class="text-muted">Total reçu</small>
      <h4 id="total-xof" class="fw-bold mt-1 text-muted">0 XOF</h4>
    </div>
  </div>
</div>
<div class="card-epay p-3 mb-4">
  <div class="d-flex justify-content-between mb-2">
    <span>Transactions ce mois</span>
    <span id="plan-usage" class="fw-bold">0 / 0</span>
  </div>
  <div class="progress" style="height:8px;">
    <div class="progress-bar bg-warning progress-bar-custom" style="width:30%"></div>
  </div>
  <small class="text-muted mt-2 d-block">Plan Free — <a href="#" class="text-warning" onclick="showUpgradeModal()">Upgrader</a></small>
</div>
<div class="card-epay p-4 mt-4 text-center">
  <h5 class="mb-3">Créer un paiement</h5>
  <p class="text-muted mb-3">Générez un lien et recevez de l'argent instantanément</p>
  <button class="btn-create-link w-100" data-bs-toggle="modal" data-bs-target="#createLinkModal">🚀 Recevoir un paiement</button>
</div>
<div id="links-container" class="mt-4" style="width:100%; padding: 0 20px;"></div>
<p class="text-muted mb-2">Recevez de l'argent en USD, EUR et converti automatiquement en XOF</p>
<div class="card-epay p-5 text-center mt-4">
  <div style="font-size:3rem;">🚀</div>
  <h4 class="fw-bold mt-3 text-muted">Débloquez plus de fonctionnalités</h4>
  <p class="text-muted mb-4">Passez au plan Pro pour accéder aux graphiques avancés, aux exports CSV/PDF et à plus de transactions.</p>
  <button class="btn btn-warning px-4 fw-bold" onclick="showUpgradeModal()">Voir les offres</button>
</div>
<div id="toast" class="custom-toast">✅ Retrait envoyé</div>
`;

// #createLinkModal est rendu à part, injecté dans document.body — même
// raison que #withdrawModal ci-dessous : #main-content a position:relative
// + z-index:1, ce qui enfermait le z-index:1055 du modal en dessous du
// .modal-backdrop ajouté par Bootstrap directement dans body (z-index:1050).
const CREATE_LINK_MODAL_HTML = `
<div class="modal fade" id="createLinkModal" tabindex="-1">
  <div class="modal-dialog modal-xl">
    <div class="modal-content">
      <div class="modal-header"><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body p-4">
        <h5 class="mb-4 text-muted">Créer un lien de paiement</h5>
        <div class="mb-3">
          <label class="form-label text-light">Nom du lien</label>
          <input class="form-control" placeholder="Ex: Prestation Design">
        </div>
        <div class="mb-4">
          <label class="form-label text-light">Montant <span class="text-secondary">(obligatoire)</span></label>
          <div class="d-flex gap-2">
            <input id="amount" type="number" class="form-control" placeholder="0.00">
            <select id="currency" class="form-select" style="max-width: 110px;">
              <option value="USD">USD</option>
              <option value="EUR">EUR</option>
            </select>
          </div>
        </div>
      </div>
      <div class="modal-footer border-0 d-flex justify-content-end gap-2 px-4 pb-4">
        <button class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
        <button id="createBtn" class="btn btn-warning fw-bold">🚀 Créer</button>
      </div>
    </div>
  </div>
</div>
`;

// #withdrawModal est rendu à part, injecté dans document.body (pas dans le
// TEMPLATE ci-dessus) : #main-content a position:relative + z-index:1
// (sidebar.css), ce qui crée un contexte d'empilement qui enfermait le
// z-index:1055 du modal en dessous du .modal-backdrop que Bootstrap ajoute
// directement dans body (z-index:1050) — rendant le modal visible mais non
// cliquable. En sortant le modal de #main-content, il rejoint le même
// contexte d'empilement que son propre backdrop, où son z-index reprend
// effet normalement.
const WITHDRAW_MODAL_HTML = `
<div class="modal fade" id="withdrawModal" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content bg-dark text-muted">
      <div class="modal-header border-0">
        <h5 class="modal-title">Retirer de l'argent</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="mb-3">
          <label class="form-label">Montant</label>
          <input type="number" id="withdrawAmount" class="form-control" placeholder="Ex: 5000">
        </div>
      </div>
      <div class="modal-footer border-0">
        <button class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
        <button id="confirmWithdrawBtn" class="btn btn-success" onclick="submitWithdraw()">Confirmer</button>
      </div>
    </div>
  </div>
</div>
`;

export async function mount(container) {
  await setViewStyles(["dashboard.css"]);
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", CREATE_LINK_MODAL_HTML);
  document.body.insertAdjacentHTML("beforeend", WITHDRAW_MODAL_HTML);

  let lockedCountdownTimer = null;
  const boundListeners = [];
  function on(target, type, fn) {
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  async function loadProfileHeader() {
    try {
      const res = await apiFetch("/profile");
      if (res.status === 401 || !res.ok) return;
      const user = await res.json();
      const name = user.full_name?.split(" ")[0] || user.email || "Utilisateur";
      document.getElementById("welcomeText").innerText = "Bonjour, " + name + " 👋";
    } catch (err) {
      console.error(err);
      document.getElementById("welcomeText").innerText = "Bonjour 👋";
    }
  }

  function handleFreeLimit(data) {
    const createBtn = document.getElementById("createBtn");
    if (!createBtn) return;
    createBtn.onclick = (e) => {
      e.preventDefault();
      if (data.plan === "free" && data.paid_count >= 10) {
        const createModal = bootstrap.Modal.getInstance(document.getElementById("createLinkModal"));
        createModal.hide();
        const upgradeModal = bootstrap.Modal.getOrCreateInstance(document.getElementById("modalUpgrade"));
        upgradeModal.show();
      } else {
        createLink();
      }
    };
  }

  async function loadPlan() {
    try {
      const res = await apiFetch("/me/plan");
      const data = await res.json();
      // Resynchronise le cache partagé (localStorage "plan") avec la donnée
      // fraîche de CETTE visite : sidebar.js ne l'écrit qu'une fois au
      // démarrage de la session (loadUser), jamais rafraîchie ensuite — sans
      // ça, #withdrawBtn pouvait lire un plan périmé ("free" mis en cache
      // avant un upgrade, ou après un changement de workspace) et ouvrir
      // #modalUpgrade au lieu de #withdrawModal.
      setPlan(data.plan);
      const planLabel = document.getElementById("plan-label");
      if (planLabel) planLabel.innerText = data.plan.charAt(0).toUpperCase() + data.plan.slice(1);
      handleFreeLimit(data);
    } catch (error) {
      console.error("Erreur chargement plan :", error);
    }
  }

  async function loadKPI() {
    try {
      const res = await apiFetch("/stats");
      const data = await res.json();
      document.getElementById("total-xof").innerText = (data.total_received || 0).toLocaleString("fr-FR") + " XOF";
      const visibleLinks = document.querySelectorAll("#links-container > div");
      const displayUsed = visibleLinks.length;
      const displayLimit = 10;
      const percent = (displayUsed / displayLimit) * 100;
      const bar = document.querySelector(".progress-bar-custom");
      if (bar) bar.style.width = percent + "%";
      const usage = document.getElementById("plan-usage");
      if (usage) usage.innerText = `${displayUsed} / ${displayLimit}`;
    } catch (err) {
      console.error("Erreur KPI:", err);
    }
  }

  async function chargerWallet() {
    try {
      const res = await apiFetch("/wallet/me");
      const data = await res.json();
      document.getElementById("wallet-balance").innerText =
        Number(data.available || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " XOF";
      const lockedEl = document.getElementById("locked-amount");
      if (lockedEl) {
        lockedEl.innerText =
          Number(data.locked_amount || 0).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " XOF";
      }
      if (lockedCountdownTimer) {
        clearInterval(lockedCountdownTimer);
        lockedCountdownTimer = null;
      }
      if (data.next_available_at) {
        startCountdown(data.next_available_at);
      } else {
        const el = document.getElementById("nextAvailableText");
        if (el) el.innerText = "Aucun montant verrouillé";
      }
    } catch (err) {
      console.error("Erreur wallet:", err);
    }
  }

  function startCountdown(nextAvailableAt) {
    const el = document.getElementById("nextAvailableText");
    const btn = document.getElementById("withdrawBtn");
    function update() {
      const now = new Date();
      const future = new Date(nextAvailableAt);
      const diff = future - now;
      if (diff <= 0) {
        if (el) el.innerText = "✅ Disponible maintenant";
        if (btn) btn.disabled = false;
        if (lockedCountdownTimer) {
          clearInterval(lockedCountdownTimer);
          lockedCountdownTimer = null;
        }
        return;
      }
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor(diff / (1000 * 60 * 60)) % 24;
      const minutes = Math.floor(diff / (1000 * 60)) % 60;
      const seconds = Math.floor(diff / 1000) % 60;
      let text = "";
      if (days > 0) text += `${days}j `;
      if (hours > 0 || days > 0) text += `${hours}h `;
      if (minutes > 0 || hours > 0) text += `${minutes}min `;
      text += `${seconds}s`;
      if (el) el.innerText = "Disponible dans " + text;
    }
    lockedCountdownTimer = setInterval(update, 1000);
    update();
  }

  async function createLink() {
    const amount = document.getElementById("amount").value;
    const currency = document.getElementById("currency").value;
    const res = await apiFetch("/links", { method: "POST", body: { amount, currency, source: "dashboard" } });
    const data = await res.json();
    if (!res.ok) {
      if (data.detail && data.detail.upgrade === true) {
        const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById("modalUpgrade"));
        modal.show();
        return;
      }
      alert(data.detail || data.message || "Erreur lors de la création");
      return;
    }
    loadLinks();
    const modalEl = document.getElementById("createLinkModal");
    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
    modal.hide();
  }

  function getLinkHTML(link, paymentUrl) {
    const status = link.status;
    let urlColor, copyBtn, archiveBtn;
    if (status === "paid") {
      urlColor = "#4ade80";
      copyBtn = "";
      archiveBtn = `<button style="background:rgba(74,222,128,0.15);border:none;color:rgba(255,255,255,0.4);font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="archivedLink('${link.id}')">Archiver</button>`;
    } else if (status === "pending") {
      urlColor = "#facc15";
      copyBtn = `<button style="background:rgba(74,222,128,0.15);border:none;color:#4ade80;font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="copierLien('${paymentUrl}')" data-url="${paymentUrl}">Copier</button>`;
      archiveBtn = `<button style="background:rgba(248,113,113,0.15);border:none;color:#f87171;font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="deleteLink('${link.id}')">Supprimer</button>`;
    } else if (status === "expired") {
      urlColor = "#f87171";
      copyBtn = "";
      archiveBtn = `<button style="background:rgba(248,113,113,0.15);border:none;color:#f87171;font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="deleteLink('${link.id}')">Supprimer</button>`;
    } else {
      urlColor = "rgba(255,255,255,0.6)";
      copyBtn = "";
      archiveBtn = "";
    }
    return `
      <div id="link-${link.id}" style="width:100%;display:flex;align-items:center;gap:12px;padding:10px 14px;margin-bottom:8px;background:rgba(255,255,255,0.07);border-radius:10px;border:1px solid rgba(255,255,255,0.1);">
        <span style="color:${urlColor};font-size:0.78rem;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:monospace;">${paymentUrl}</span>
        ${copyBtn}
        ${archiveBtn}
      </div>
    `;
  }

  function loadLinks() {
    const container = document.getElementById("links-container");
    if (!container) return;
    apiFetch("/links/dashboard")
      .then((res) => res.json())
      .then((data) => {
        const progressText = document.getElementById("progress-text");
        if (progressText) progressText.innerText = `${data.paid_this_month}/10`;
        container.innerHTML = "";
        if (!data.links || data.links.length == 0) {
          container.innerHTML = `<p class="text-muted">Aucun lien pour le moment</p>`;
          return;
        }
        data.links.forEach((link) => {
          container.innerHTML += getLinkHTML(link, link.url);
        });
      });
  }

  async function archivedLink(id) {
    try {
      const res = await apiFetch(`/archive/${id}`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "Erreur");
        return;
      }
      showToast("Lien archivé ✅");
      const el = document.getElementById(`link-${id}`);
      if (el) el.remove();
    } catch (err) {
      console.error(err);
      alert("Erreur serveur");
    }
  }

  async function deleteLink(id) {
    try {
      const res = await apiFetch(`/links/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Erreur suppression");
      loadLinks();
    } catch (e) {
      alert("Erreur suppression");
    }
  }

  function copierLien(url) {
    navigator.clipboard.writeText(url);
    alert("Lien copié !");
  }

  async function submitWithdraw() {
    const btn = document.getElementById("confirmWithdrawBtn");
    btn.innerText = "Envoi...";
    btn.disabled = true;
    try {
      const res = await apiFetch("/withdraw", {
        method: "POST",
        body: { amount: parseFloat(document.getElementById("withdrawAmount").value) },
      });
      const data = await res.json();
      if (!res.ok) {
        let message = "Impossible d'effectuer ce retrait";
        if (data.detail === "Permission insuffisante") {
          message = "Seul le propriétaire du compte peut effectuer un retrait";
        } else if (typeof data.detail === "string") {
          message = data.detail;
        }
        if (data.detail?.next_available_at) {
          const date = new Date(data.detail.next_available_at);
          message += `\n⏳ Disponible le ${date.toLocaleDateString("fr-FR")}`;
        }
        showToast(message, "error");
        btn.innerText = "Confirmer";
        btn.disabled = false;
        return;
      }
      if (!data.id) {
        showToast("Erreur: ID retrait manquant");
        btn.innerText = "Confirmer";
        btn.disabled = false;
        return;
      }
      const res2 = await apiFetch(`/withdraw/${data.id}/process`, { method: "POST" });
      const data2 = await res2.json();
      if (!res2.ok) {
        showToast(data2.detail || "Erreur process");
        return;
      }
      showToast("Retrait envoyé !");
      const modalEl = document.getElementById("withdrawModal");
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      modal.hide();
      btn.innerText = "Confirmer";
      btn.disabled = false;
    } catch (err) {
      console.error(err);
      showToast("Erreur serveur");
      btn.innerText = "Confirmer";
      btn.disabled = false;
    }
  }

  async function loadWorkspaces() {
    try {
      const res = await apiFetch("/workspaces/me");
      const workspaces = await res.json();
      const select = document.getElementById("workspaceSwitcher");
      select.innerHTML = workspaces.map((w) => `<option value="${w.id}">${w.name}</option>`).join("");
      const savedWorkspace = getWorkspaceId();
      if (savedWorkspace && workspaces.some((w) => String(w.id) === savedWorkspace)) {
        select.value = savedWorkspace;
      } else if (workspaces.length > 0) {
        select.value = workspaces[0].id;
        setWorkspaceId(workspaces[0].id);
      }
      on(select, "change", async () => {
        const workspaceId = select.value;
        setWorkspaceId(workspaceId);
        navigate(`/dash/workspace/${workspaceId}/`, { replace: true });
        await Promise.all([loadProfileHeader(), loadPlan(), loadKPI(), chargerWallet(), refreshPlanBadge()]);
        loadLinks();
      });
    } catch (err) {
      console.error("Erreur loadWorkspaces:", err);
    }
  }

  const withdrawBtn = document.getElementById("withdrawBtn");
  on(withdrawBtn, "click", (e) => {
    e.preventDefault();
    if (getPlan() === "free") {
      bootstrap.Modal.getOrCreateInstance(document.getElementById("modalUpgrade")).show();
    } else {
      bootstrap.Modal.getOrCreateInstance(document.getElementById("withdrawModal")).show();
    }
  });

  container.querySelectorAll(".upgrade-btn").forEach((btn) => on(btn, "click", () => showUpgradeModal()));

  window.showUpgradeModal = showUpgradeModal;
  window.submitWithdraw = submitWithdraw;
  window.archivedLink = archivedLink;
  window.copierLien = copierLien;
  window.deleteLink = deleteLink;
  // window.upgrade est exposé globalement par app.js (modale partagée persistante)

  const mq = window.matchMedia("(max-width: 768px)");
  const exportActions = document.getElementById("export-actions");
  const originalParent = withdrawBtn.parentElement;
  const originalNextSibling = withdrawBtn.nextSibling;
  function placeButton(query) {
    if (query.matches) {
      exportActions.prepend(withdrawBtn);
    } else if (originalNextSibling) {
      originalParent.insertBefore(withdrawBtn, originalNextSibling);
    } else {
      originalParent.appendChild(withdrawBtn);
    }
  }
  placeButton(mq);
  mq.addEventListener("change", placeButton);

  loadProfileHeader();
  loadPlan();
  loadKPI();
  chargerWallet();
  loadLinks();
  loadWorkspaces();

  const params = new URLSearchParams(window.location.search);
  if (params.get("upgrade") === "1") upgrade("pro");

  return {
    unmount() {
      const createLinkModalEl = document.getElementById("createLinkModal");
      const createLinkModalInstance = createLinkModalEl && bootstrap.Modal.getInstance(createLinkModalEl);
      if (createLinkModalInstance) {
        createLinkModalInstance.hide();
        createLinkModalInstance.dispose();
        document.body.classList.remove("modal-open");
        document.body.style.removeProperty("overflow");
        document.body.style.removeProperty("padding-right");
        document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
      }
      createLinkModalEl?.remove();
      const withdrawModalEl = document.getElementById("withdrawModal");
      const withdrawModalInstance = withdrawModalEl && bootstrap.Modal.getInstance(withdrawModalEl);
      if (withdrawModalInstance) {
        withdrawModalInstance.hide();
        withdrawModalInstance.dispose();
        document.body.classList.remove("modal-open");
        document.body.style.removeProperty("overflow");
        document.body.style.removeProperty("padding-right");
        document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
      }
      withdrawModalEl?.remove();
      if (lockedCountdownTimer) clearInterval(lockedCountdownTimer);
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      mq.removeEventListener("change", placeButton);
      delete window.showUpgradeModal;
      delete window.submitWithdraw;
      delete window.archivedLink;
      delete window.copierLien;
      delete window.deleteLink;
    },
  };
}
