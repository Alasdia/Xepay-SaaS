// Vue "Mes liens de paiement" — port fidèle de liens.html + liens.js.
import { apiFetch } from "../core/apiClient.js";
import { isAuthenticated } from "../core/state.js";
import { setViewStyles } from "../core/styleLoader.js";
import { updateUpgradeModal } from "../shared/modalUpgrade.js";
import { initDetailsDrawer } from "../shared/detailsDrawer.js";

const TEMPLATE = `
<div id="links-lock" class="d-none">
  <div class="lock-card">
    <div class="lock-icon"><i class="fa-solid fa-lock"></i></div>
    <h2>Liens de paiement</h2>
    <p>Débloquez les liens de paiement internationaux avec le plan Pro.</p>
    <button class="btn btn-warning fw-bold" onclick="upgrade('pro')">⚡ Passer au Pro</button>
  </div>
</div>
<div id="main-content-inner" class="w-100">
  <div class="mb-4">
    <div class="d-flex justify-content-between align-items-center">
      <div>
        <h4 class="fw-bold mb-1">🔗 Mes liens de paiement</h4>
        <small class="text-muted">Créez et partagez vos liens pour recevoir des paiements internationaux</small>
      </div>
      <button class="btn btn-warning" data-bs-toggle="modal" data-bs-target="#modalCreationLien">+ Nouveau lien</button>
    </div>
  </div>
  <div class="card-epay p-3 mb-4">
    <div class="d-flex justify-content-between align-items-center">
      <span>Liens utilisés</span>
      <span id="compteur-liens" class="fw-bold">0 / 10</span>
    </div>
    <div class="progress mt-2" style="height: 6px;">
      <div id="barre-liens" class="progress-bar bg-warning" style="width: 0%"></div>
    </div>
    <small class="text-muted mt-1 d-block">
      Plan Free — <a href="#" class="text-warning" onclick="showUpgradeModal()">Upgrader pour plus de liens</a>
    </small>
  </div>
  <div id="liste-liens-container" style="height: 75vh; overflow-y: auto;">
    <div id="liste-liens"></div>
  </div>
  <div id="aucun-lien" class="text-center py-5 d-none">
    <p class="text-muted">Aucun lien de paiement créé</p>
    <button class="btn btn-warning fw-bold" data-bs-toggle="modal" data-bs-target="#modalCreationLien">+ Créer mon premier lien</button>
  </div>
</div>
<div class="customer-modal-overlay" id="lien-details-modal">
  <div class="customer-modal customer-details-modal">
    <div class="customer-modal-header">
      <div>
        <h3>Détails du lien</h3>
        <p id="lien-details-subtitle"></p>
      </div>
      <button type="button" class="customer-modal-close" id="close-lien-details">×</button>
    </div>
    <div id="lien-details-content"></div>
  </div>
</div>
<div class="modal fade" id="modalLienGenere" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-0" style="background:#0d1b6e; color:white;">
      <div class="modal-header border-0">
        <h5 class="modal-title fw-bold">✅ Lien créé avec succès !</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body text-center">
        <p class="text-muted mb-3">Partagez ce lien avec votre client</p>
        <div class="p-3 rounded mb-3" style="background:rgba(255,255,255,0.1);">
          <code id="lien-genere" class="text-warning" style="word-break:break-all; font-size:0.9rem;"></code>
        </div>
        <button class="btn btn-warning fw-bold w-100" onclick="copierLienGenere()">📋 Copier le lien</button>
      </div>
    </div>
  </div>
</div>
`;

// #modalCreationLien est rendu à part, injecté dans document.body (pas dans
// le TEMPLATE ci-dessus) : #main-content a position:relative + z-index:1
// (sidebar.css), ce qui crée un contexte d'empilement qui enfermait le
// z-index:1055 du modal en dessous du .modal-backdrop que Bootstrap ajoute
// directement dans body (z-index:1050) — rendant le modal visible mais non
// cliquable. En sortant le modal de #main-content, il rejoint le même
// contexte d'empilement que son propre backdrop, où son z-index reprend
// effet normalement.
const CREATION_LIEN_MODAL_HTML = `
<div class="modal fade" id="modalCreationLien" tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content border-0 p-4">
      <div class="modal-header border-0">
        <h5 class="modal-title fw-bold"><i class="fa-solid fa-link"></i> Créer un lien de paiement</h5>
        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="mb-3">
          <label class="form-label">Nom du lien</label>
          <input type="text" id="nom-lien" class="form-control bg-transparent text-muted border-secondary" placeholder="Ex: Freelance Design, Boutique...">
        </div>
        <div class="mb-4">
          <label class="form-label">Montant <small class="text-muted">(obligatoire)</small></label>
          <div class="input-group mt-2">
            <input type="number" id="montant-lien" class="form-control bg-transparent text-muted border-secondary" placeholder="0.00">
            <select id="devise-lien" class="form-select bg-dark text-w border-secondary" style="max-width:120px;">
              <option value="XOF" selected>XOF</option>
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
            </select>
          </div>
        </div>
      </div>
      <div id="success-msg" class="alert alert-success d-none"></div>
      <div class="modal-footer border-0">
        <button id="btn-creer-lien" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
        <button id="btn-generer-lien" class="btn btn-warning fw-bold" onclick="genererLien()">🚀 Générer le lien</button>
      </div>
      <div id="error-box" style="display:none; color:red;"></div>
    </div>
  </div>
</div>
`;

export async function mount(container) {
  await setViewStyles(["responsive.css", "liens.css", "commerce.css"]);
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", CREATION_LIEN_MODAL_HTML);

  let links = [];
  let offset = 0;
  const limit = 10;
  let isLoading = false;

  const detailsModal = container.querySelector("#lien-details-modal");
  initDetailsDrawer(detailsModal, detailsModal.querySelector(".customer-modal"));
  container.querySelector("#close-lien-details").addEventListener("click", () => {
    detailsModal.classList.remove("open");
  });
  detailsModal.addEventListener("click", (event) => {
    if (event.target === detailsModal) detailsModal.classList.remove("open");
  });

  async function checkPlanLock() {
    const res = await apiFetch("/me");
    const user = await res.json();
    if (user.plan === "free") {
      document.body.classList.add("locked-page");
      document.getElementById("links-lock").classList.remove("d-none");
      return true;
    }
    return false;
  }

  async function chargerLiens() {
    const listeLiens = document.getElementById("liste-liens");
    const compteur = document.getElementById("compteur-liens");
    const barre = document.getElementById("barre-liens");
    const aucun = document.getElementById("aucun-lien");
    if (!listeLiens || isLoading) return;
    isLoading = true;
    if (!isAuthenticated()) {
      window.location.href = "/login";
      return;
    }
    const res = await apiFetch(`/links?limit=${limit}&offset=${offset}`);
    if (!res.ok) {
      const error = await res.text();
      console.error("❌ Erreur API :", error);
      if (error.includes("Token expiré")) {
        window.location.href = "/login";
      }
      isLoading = false;
      return;
    }
    const liens = await res.json();
    const totalLiens = offset + liens.length;
    if (compteur) compteur.innerText = `${totalLiens}/${limit}`;
    if (barre) barre.style.width = `${(totalLiens / limit) * 100}%`;
    if (liens.length === 0 && offset === 0) {
      aucun.classList.remove("d-none");
      isLoading = false;
      return;
    } else {
      aucun.classList.add("d-none");
    }
    offset += liens.length;

    liens
      .filter((lien) => !lien.archived)
      .forEach((lien) => {
        const info = getStatusInfo(lien);
        const div = document.createElement("div");
        div.className = `lien-card lien-compact ${info.accent}`;
        div.setAttribute("data-id", lien.id);
        div.innerHTML = `
          <span class="lien-compact-dot"></span>
          <span class="lien-compact-url">${lien.url}</span>
          <div class="lien-compact-actions">${renderQuickActions(lien)}</div>
          <i class="fa-solid fa-chevron-right lien-compact-chevron"></i>
        `;
        div.addEventListener("click", () => showLienDetails(lien));
        const copyIcon = div.querySelector('[data-action="copy"]');
        if (copyIcon) copyIcon.addEventListener("click", (event) => { event.stopPropagation(); copier(lien.url); });
        const archiveIcon = div.querySelector('[data-action="archive"]');
        if (archiveIcon) archiveIcon.addEventListener("click", (event) => { event.stopPropagation(); archiverLien(lien.id); });
        const deleteIcon = div.querySelector('[data-action="delete"]');
        if (deleteIcon) deleteIcon.addEventListener("click", (event) => { event.stopPropagation(); supprimer(lien.id); });
        listeLiens.appendChild(div);
      });
    isLoading = false;
  }

  function getStatusInfo(lien) {
    if (lien.status === "paid") {
      return { key: "paid", label: "Payé", badge: "status-success", accent: "lien-accent-success", legacy: "status-paid" };
    }
    if (lien.status === "expired" || !lien.active) {
      return { key: "expired", label: "Expiré", badge: "status-danger", accent: "lien-accent-danger", legacy: "status-expired" };
    }
    return { key: "pending", label: "En attente", badge: "status-warning", accent: "lien-accent-warning", legacy: "status-pending" };
  }

  function renderQuickActions(lien) {
    const copyIcon =
      lien.status === "pending"
        ? `<button type="button" class="lien-icon-btn lien-icon-copy" data-action="copy" title="Copier"><i class="fa-solid fa-copy"></i></button>`
        : "";
    const secondaryIcon =
      lien.status === "paid"
        ? `<button type="button" class="lien-icon-btn lien-icon-archive" data-action="archive" title="Archiver"><i class="fa-solid fa-box-archive"></i></button>`
        : `<button type="button" class="lien-icon-btn lien-icon-delete${lien.status === "expired" ? " lien-icon-delete-danger" : ""}" data-action="delete" title="Supprimer"><i class="fa-solid fa-trash"></i></button>`;
    return `${copyIcon}${secondaryIcon}`;
  }

  function showLienDetails(lien) {
    const info = getStatusInfo(lien);
    const amount =
      typeof lien.amount === "number"
        ? `${new Intl.NumberFormat("fr-FR").format(lien.amount)} ${lien.currency}`
        : "Montant invalide";

    const exp = new Date(lien.expires_at);
    const now = new Date();
    const diff = exp - now;
    let expirationLabel;
    if (diff <= 0) {
      expirationLabel = "Expiré";
    } else {
      const minutes = Math.floor(diff / 60000);
      const seconds = Math.floor((diff % 60000) / 1000);
      const heure = exp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      expirationLabel = minutes === 0 ? `Expire dans ${seconds}s` : `Expire dans ${minutes} min (${heure})`;
    }

    container.querySelector("#lien-details-subtitle").textContent = lien.name || lien.id;
    container.querySelector("#lien-details-content").innerHTML = `
      <div class="customer-profile">
        <div class="customer-profile-avatar"><i class="fa-solid fa-link"></i></div>
        <div>
          <h4>${lien.name || "Lien de paiement"}</h4>
          <code>${lien.id}</code>
        </div>
      </div>
      <div class="customer-details-grid">
        <div class="customer-detail-item">
          <span>Montant</span>
          <strong>${amount}</strong>
        </div>
        <div class="customer-detail-item">
          <span>Statut</span>
          <strong><span class="status-badge ${info.badge}">${info.label}</span></strong>
        </div>
        <div class="customer-detail-item">
          <span>Expiration</span>
          <strong>${expirationLabel}</strong>
        </div>
        <div class="customer-detail-item">
          <span>Créé le</span>
          <strong>${lien.created_at ? new Date(lien.created_at).toLocaleString("fr-FR") : "—"}</strong>
        </div>
      </div>
      <div class="lien-url ${info.legacy}">${lien.url}</div>
    `;

    detailsModal.classList.add("open");
  }

  async function genererLien() {
    const name = document.getElementById("nom-lien").value || "Lien de paiement";
    const rawAmount = document.getElementById("montant-lien").value;
    const errorBox = document.getElementById("error-box");
    if (!rawAmount) {
      errorBox.innerText = "Le montant est obligatoire";
      errorBox.style.display = "block";
      return;
    }
    const amount = parseFloat(rawAmount);
    if (isNaN(amount)) alert("Montant invalide");
    const currency = document.getElementById("devise-lien").value;
    const payload = { amount, currency, source: "links" };
    if (name) payload.name = name;
    const res = await apiFetch("/links", { method: "POST", body: payload });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Impossible de créer le lien");
      return;
    }
    const successBox = document.getElementById("success-msg");
    successBox.innerText = "Lien créé avec succès ✅";
    successBox.style.display = "block";
    const modalEl = document.getElementById("modalCreationLien");
    if (modalEl) {
      const modal = bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }
    document.getElementById("nom-lien").value = "";
    document.getElementById("montant-lien").value = "";
    errorBox.style.display = "none";
    offset = 0;
    document.getElementById("liste-liens").innerHTML = "";
    await chargerLiens();
  }

  async function supprimer(id) {
    const carte = document.querySelector(`[data-id="${id}"]`);
    if (carte) carte.remove();
    try {
      await apiFetch(`/links/${id}`, { method: "DELETE" });
      chargerLiens();
    } catch (e) {
      if (carte) carte.style.opacity = "1";
      alert("Erreur suppression");
    }
  }

  function copier(url) {
    navigator.clipboard.writeText(url);
    alert("Lien copié !");
  }

  async function archiverLien(id) {
    const carte = document.querySelector(`[data-id="${id}"]`);
    if (carte) {
      carte.style.opacity = "0.4";
      carte.style.pointerEvents = "none";
    }
    try {
      const response = await apiFetch(`/archive/${id}`, { method: "POST" });
      if (!response.ok) throw new Error("Erreur archivage");
      if (carte) {
        carte.style.transition = "all 0.25s ease";
        carte.style.height = carte.offsetHeight + "px";
        requestAnimationFrame(() => {
          carte.style.opacity = "0";
          carte.style.height = "0";
          carte.style.margin = "0";
          carte.style.padding = "0";
          carte.style.overflow = "hidden";
        });
        setTimeout(() => carte.remove(), 250);
      }
    } catch (error) {
      if (carte) {
        carte.style.opacity = "1";
        carte.style.pointerEvents = "auto";
      }
      alert("Impossible d'archiver ce lien");
    }
  }

  function showUpgradeModal(feature = null) {
    const plan = window.GLOBAL_PLAN?.plan;
    updateUpgradeModal(plan, feature);
    const modal = new bootstrap.Modal(document.getElementById("modalUpgrade"));
    modal.show();
  }

  const onScroll = () => {
    const scrollBox = document.getElementById("liste-liens-container");
    if (!scrollBox) return;
    if (scrollBox.scrollTop + scrollBox.clientHeight >= scrollBox.scrollHeight - 50) {
      chargerLiens();
    }
  };
  const scrollBox = document.getElementById("liste-liens-container");
  scrollBox.addEventListener("scroll", onScroll);

  window.genererLien = genererLien;
  window.showUpgradeModal = showUpgradeModal;
  // window.upgrade est exposé globalement par app.js (modale partagée persistante)

  (async () => {
    const locked = await checkPlanLock();
    if (!locked) chargerLiens();
  })();

  return {
    unmount() {
      const creationLienModalEl = document.getElementById("modalCreationLien");
      const creationLienModalInstance = creationLienModalEl && bootstrap.Modal.getInstance(creationLienModalEl);
      if (creationLienModalInstance) {
        creationLienModalInstance.hide();
        creationLienModalInstance.dispose();
        document.body.classList.remove("modal-open");
        document.body.style.removeProperty("overflow");
        document.body.style.removeProperty("padding-right");
        document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
      }
      creationLienModalEl?.remove();
      document.body.classList.remove("locked-page");
      scrollBox.removeEventListener("scroll", onScroll);
      delete window.genererLien;
      delete window.showUpgradeModal;
    },
  };
}
