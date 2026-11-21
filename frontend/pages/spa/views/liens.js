// Vue "Mes liens de paiement" — port fidèle de liens.html + liens.js.
import { apiFetch } from "../core/apiClient.js";
import { isAuthenticated } from "../core/state.js";
import { setViewStyles } from "../core/styleLoader.js";
import { initDetailsDrawer } from "../shared/detailsDrawer.js";
import { renderMetadataSection } from "./commerce.js";

const TEMPLATE = `
<div id="main-content-inner" class="w-100">
  <div class="mb-4">
    <div class="d-flex justify-content-between align-items-center">
      <div>
        <h4 class="fw-bold mb-1">🔗 Mes liens de paiement</h4>
        <small class="text-muted">Créez et partagez vos liens pour recevoir des paiements internationaux</small>
      </div>
      <button class="create-client-btn open-lien-modal">+ Nouveau lien</button>
    </div>
  </div>
  <div id="liste-liens-container" style="height: 75vh; overflow-y: auto;">
    <div id="liste-liens"></div>
  </div>
  <div id="aucun-lien" class="text-center py-5 d-none">
    <p class="text-muted">Aucun lien de paiement créé</p>
    <button class="create-client-btn open-lien-modal">+ Créer mon premier lien</button>
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
<div class="customer-modal-overlay" id="modalCreationLien">
  <div class="customer-modal">
    <div class="customer-modal-header">
      <div>
        <h3><i class="fa-solid fa-link"></i> Créer un lien de paiement</h3>
      </div>
      <button type="button" class="customer-modal-close" id="close-create-lien">×</button>
    </div>
    <form id="create-lien-form">
      <div class="form-group">
        <label for="nom-lien">Nom du lien</label>
        <input type="text" id="nom-lien" placeholder="Ex: Freelance Design, Boutique...">
      </div>
      <div class="form-group">
        <label for="type-lien">Type de lien</label>
        <select id="type-lien">
          <option value="unique" selected>Usage unique</option>
          <option value="multi_fixe">Usage multiple, montant fixe</option>
          <option value="multi_flexible">Usage multiple, montant libre</option>
        </select>
      </div>
      <div class="form-group d-none" id="quota-group">
        <label for="quota-lien">Limiter à un nombre de paiements <small>(optionnel, illimité si vide)</small></label>
        <input type="number" id="quota-lien" min="1" placeholder="Illimité">
      </div>
      <div class="form-group" id="montant-fixe-group">
        <label for="montant-lien">Montant <small>(obligatoire)</small></label>
        <input type="number" id="montant-lien" placeholder="0.00">
      </div>
      <div class="form-group d-none" id="montant-flexible-group">
        <label>Bornes <small>(optionnelles - le client choisit le montant)</small></label>
        <div style="display:flex; gap:8px;">
          <input type="number" id="montant-min-lien" placeholder="Min (optionnel)" style="flex:1;">
          <input type="number" id="montant-max-lien" placeholder="Max (optionnel)" style="flex:1;">
        </div>
      </div>
      <div class="form-group">
        <label for="devise-lien">Devise</label>
        <select id="devise-lien">
          <option value="EUR" selected>EUR</option>
          <option value="USD">USD</option>
        </select>
      </div>
      <div id="success-msg" class="alert alert-success d-none"></div>
      <div id="error-box" style="display:none; color:red;"></div>
      <div class="customer-modal-actions">
        <button type="button" class="modal-cancel-btn" id="cancel-create-lien">Annuler</button>
        <button type="button" id="btn-generer-lien" class="modal-submit-btn" onclick="genererLien()">🚀 Générer le lien</button>
      </div>
    </form>
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

export async function mount(container) {
  await setViewStyles(["responsive.css", "liens.css", "commerce.css"]);
  container.innerHTML = TEMPLATE;

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

  // Modal de création de lien : même style/comportement que les modals de
  // création Client/Produit/Abonnement/Facture (commerce.js) — overlay
  // .customer-modal-overlay avec classList "open", pas l'API Bootstrap.
  const creationModal = container.querySelector("#modalCreationLien");
  container.querySelectorAll(".open-lien-modal").forEach((btn) => {
    btn.addEventListener("click", () => creationModal.classList.add("open"));
  });
  container.querySelector("#close-create-lien").addEventListener("click", () => {
    creationModal.classList.remove("open");
  });
  container.querySelector("#cancel-create-lien").addEventListener("click", () => {
    creationModal.classList.remove("open");
  });
  creationModal.addEventListener("click", (event) => {
    if (event.target === creationModal) creationModal.classList.remove("open");
  });

  // Bascule les champs du formulaire de création selon le type choisi :
  // quota (nombre de paiements) uniquement pour les types multi-usage,
  // bornes min/max uniquement pour le montant libre (qui masque alors le
  // champ "Montant" fixe, le client le choisira lui-même au paiement).
  const typeLienSelect = container.querySelector("#type-lien");
  function updateLienFormVisibility() {
    const type = typeLienSelect.value;
    const isFlexible = type === "multi_flexible";
    const isMultiUse = type !== "unique";
    container.querySelector("#quota-group").classList.toggle("d-none", !isMultiUse);
    container.querySelector("#montant-fixe-group").classList.toggle("d-none", isFlexible);
    container.querySelector("#montant-flexible-group").classList.toggle("d-none", !isFlexible);
  }
  typeLienSelect.addEventListener("change", updateLienFormVisibility);
  updateLienFormVisibility();

  async function chargerLiens() {
    const listeLiens = document.getElementById("liste-liens");
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
    if (lien.status === "exhausted") {
      return { key: "exhausted", label: "Épuisé", badge: "status-success", accent: "lien-accent-success", legacy: "status-paid" };
    }
    if (lien.status === "expired" || !lien.active) {
      return { key: "expired", label: "Expiré", badge: "status-danger", accent: "lien-accent-danger", legacy: "status-expired" };
    }
    return { key: "pending", label: "En attente", badge: "status-warning", accent: "lien-accent-warning", legacy: "status-pending" };
  }

  // Montant à afficher pour un lien : celui du dernier paiement reçu s'il y
  // en a un, sinon le montant fixe du lien, sinon (lien à montant libre
  // jamais encore payé) ses bornes min/max.
  function formatLienAmount(lien) {
    if (typeof lien.amount === "number") {
      return `${new Intl.NumberFormat("fr-FR").format(lien.amount)} ${lien.currency}`;
    }
    const min = lien.min_amount != null ? new Intl.NumberFormat("fr-FR").format(lien.min_amount) : null;
    const max = lien.max_amount != null ? new Intl.NumberFormat("fr-FR").format(lien.max_amount) : null;
    if (min && max) return `Libre (${min}–${max} ${lien.currency})`;
    if (min) return `Libre (min ${min} ${lien.currency})`;
    if (max) return `Libre (max ${max} ${lien.currency})`;
    return `Libre (${lien.currency})`;
  }

  // Type d'usage à afficher : usage unique, quota (X/N payés) ou illimité
  // (X paiements reçus jusqu'ici) - voir Link.max_uses/successful_payments_count.
  function formatLienUsage(lien) {
    const count = lien.successful_payments_count ?? 0;
    if (lien.max_uses === 1) return "Usage unique";
    if (lien.max_uses) return `${count}/${lien.max_uses} paiements`;
    return `Illimité (${count} paiement${count > 1 ? "s" : ""})`;
  }

  function formatLienExpiration(lien) {
    if (!lien.expires_at) return "Jamais";
    const exp = new Date(lien.expires_at);
    const now = new Date();
    const diff = exp - now;
    if (diff <= 0) return "Expiré";
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    const heure = exp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return minutes === 0 ? `Expire dans ${seconds}s` : `Expire dans ${minutes} min (${heure})`;
  }

  function renderQuickActions(lien) {
    const copyIcon =
      lien.status === "pending"
        ? `<button type="button" class="lien-icon-btn lien-icon-copy" data-action="copy" title="Copier"><i class="fa-solid fa-copy"></i></button>`
        : "";
    const secondaryIcon =
      lien.status === "paid" || lien.status === "exhausted"
        ? `<button type="button" class="lien-icon-btn lien-icon-archive" data-action="archive" title="Archiver"><i class="fa-solid fa-box-archive"></i></button>`
        : `<button type="button" class="lien-icon-btn lien-icon-delete${lien.status === "expired" ? " lien-icon-delete-danger" : ""}" data-action="delete" title="Supprimer"><i class="fa-solid fa-trash"></i></button>`;
    return `${copyIcon}${secondaryIcon}`;
  }

  function showLienDetails(lien) {
    const info = getStatusInfo(lien);

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
          <strong>${formatLienAmount(lien)}</strong>
        </div>
        <div class="customer-detail-item">
          <span>Statut</span>
          <strong><span class="status-badge ${info.badge}">${info.label}</span></strong>
        </div>
        <div class="customer-detail-item">
          <span>Usage</span>
          <strong>${formatLienUsage(lien)}</strong>
        </div>
        <div class="customer-detail-item">
          <span>Expiration</span>
          <strong>${formatLienExpiration(lien)}</strong>
        </div>
        <div class="customer-detail-item">
          <span>Créé le</span>
          <strong>${lien.created_at ? new Date(lien.created_at).toLocaleString("fr-FR") : "—"}</strong>
        </div>
      </div>
      <div class="lien-url ${info.legacy}">${lien.url}</div>

      ${renderMetadataSection(lien.metadata, "Lien")}
    `;

    detailsModal.classList.add("open");
  }

  async function genererLien() {
    const name = document.getElementById("nom-lien").value || "Lien de paiement";
    const type = document.getElementById("type-lien").value;
    const currency = document.getElementById("devise-lien").value;
    const errorBox = document.getElementById("error-box");
    errorBox.style.display = "none";

    const payload = { currency, source: "links" };
    if (name) payload.name = name;

    if (type === "multi_flexible") {
      const rawMin = document.getElementById("montant-min-lien").value;
      const rawMax = document.getElementById("montant-max-lien").value;
      if (rawMin) payload.min_amount = parseFloat(rawMin);
      if (rawMax) payload.max_amount = parseFloat(rawMax);
      if (payload.min_amount != null && payload.max_amount != null && payload.min_amount > payload.max_amount) {
        errorBox.innerText = "Le montant minimum doit être inférieur au maximum";
        errorBox.style.display = "block";
        return;
      }
    } else {
      const rawAmount = document.getElementById("montant-lien").value;
      if (!rawAmount) {
        errorBox.innerText = "Le montant est obligatoire";
        errorBox.style.display = "block";
        return;
      }
      const amount = parseFloat(rawAmount);
      if (isNaN(amount)) {
        errorBox.innerText = "Montant invalide";
        errorBox.style.display = "block";
        return;
      }
      payload.amount = amount;
    }

    if (type === "unique") {
      payload.max_uses = 1;
    } else {
      const rawQuota = document.getElementById("quota-lien").value;
      if (rawQuota) payload.max_uses = parseInt(rawQuota, 10);
    }

    const res = await apiFetch("/links", { method: "POST", body: payload });
    if (!res.ok) {
      const err = await res.json();
      errorBox.innerText = err.detail || "Impossible de créer le lien";
      errorBox.style.display = "block";
      return;
    }
    const successBox = document.getElementById("success-msg");
    successBox.innerText = "Lien créé avec succès ✅";
    successBox.style.display = "block";
    creationModal.classList.remove("open");
    document.getElementById("nom-lien").value = "";
    document.getElementById("montant-lien").value = "";
    document.getElementById("montant-min-lien").value = "";
    document.getElementById("montant-max-lien").value = "";
    document.getElementById("quota-lien").value = "";
    document.getElementById("type-lien").value = "unique";
    updateLienFormVisibility();
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
      // Même mécanisme que supprimer() : charge la page suivante pour
      // compenser la carte retirée (chargerLiens ajoute à la suite sans
      // réinitialiser offset, donc pas de doublon).
      await chargerLiens();
    } catch (error) {
      if (carte) {
        carte.style.opacity = "1";
        carte.style.pointerEvents = "auto";
      }
      alert("Impossible d'archiver ce lien");
    }
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

  chargerLiens();

  return {
    unmount() {
      // #modalCreationLien fait maintenant partie de TEMPLATE (comme les
      // modals de création de commerce.js) : il est retiré du DOM
      // automatiquement avec le reste de #main-content par le router,
      // plus besoin de le gérer/disposer à part.
      scrollBox.removeEventListener("scroll", onScroll);
      delete window.genererLien;
    },
  };
}
