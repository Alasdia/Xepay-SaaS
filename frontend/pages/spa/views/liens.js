// Vue "Mes liens de paiement" — port fidèle de liens.html + liens.js.
import { apiFetch } from "../core/apiClient.js";
import { getToken } from "../core/state.js";
import { setViewStyles } from "../core/styleLoader.js";
import { updateUpgradeModal } from "../shared/modalUpgrade.js";

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
  await setViewStyles(["responsive.css", "liens.css"]);
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", CREATION_LIEN_MODAL_HTML);

  let links = [];
  let offset = 0;
  const limit = 10;
  let isLoading = false;

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
    const token = getToken();
    if (!token) {
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

    function getStatusLabel(lien) {
      if (lien.status === "paid") return "Payé";
      if (!lien.active) return "Expiré";
      if (lien.status === "pending") return "En attente";
      return "Actif";
    }
    function getStatusClass(lien) {
      if (lien.status === "paid") return "status-paid";
      if (!lien.active) return "status-expired";
      if (lien.status === "pending") return "status-pending";
      return "status-active";
    }

    liens
      .filter((lien) => !lien.archived)
      .forEach((lien) => {
        const amount =
          typeof lien.amount === "number"
            ? `${new Intl.NumberFormat("fr-FR").format(lien.amount)} ${lien.currency}`
            : "Montant invalide";
        const div = document.createElement("div");
        div.className = "lien-card";
        div.setAttribute("data-id", lien.id);
        const exp = new Date(lien.expires_at);
        const now = new Date();
        const diff = exp - now;
        const minutes = Math.floor(diff / 60000);
        const seconds = Math.floor((diff % 60000) / 1000);
        const heure = exp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        let expirationLabel = "";
        let color = "orange";
        if (diff <= 0) {
          expirationLabel = "Expiré";
          color = "red";
        } else if (minutes === 0) {
          expirationLabel = `expire dans ${seconds}s`;
          color = "#ff4d4d";
        } else {
          expirationLabel = `expire dans ${minutes} min (${heure})`;
        }
        div.innerHTML = `
          <div class="lien-content">
            <div class="lien-header ">
              <div class="lien-infos">
                <h6>${lien.name}</h6>
                <small style="color:${color}; font-weight:500;">${expirationLabel}</small>
                <div class="montant">${amount}</div>
              </div>
              <div class="lien-status ${getStatusClass(lien)}">${getStatusLabel(lien)}</div>
            </div>
          </div>
          <div class="lien-url ${getStatusClass(lien)}">${lien.url}</div>
          <div class="actions">
            ${
              lien.status === "pending"
                ? `<button class="btn-copy-actif" onclick="copier('${lien.url}')">Copier</button>`
                : ""
            }
            ${
              lien.status === "paid"
                ? `<button class="btn-delete-neutral" onclick="archiverLien('${lien.id}')">Archiver</button>`
                : `<button class="${lien.status === "expired" ? "btn-delete-actif" : "btn-delete-neutral"}" onclick="supprimer('${lien.id}')">Supprimer</button>`
            }
          </div>
        `;
        listeLiens.appendChild(div);
      });
    isLoading = false;
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
  window.supprimer = supprimer;
  window.copier = copier;
  window.archiverLien = archiverLien;
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
      delete window.supprimer;
      delete window.copier;
      delete window.archiverLien;
      delete window.showUpgradeModal;
    },
  };
}
