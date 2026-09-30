// Vue "Profil / KYC" — port fidèle de profil.html + profil.js.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";

const TEMPLATE = `
<div class="d-flex justify-content-between align-items-center mb-4">
  <div>
    <h4 class="fw-bold mb-1 text-muted"><i class="fa-solid fa-code"></i> Profil / KYC</h4>
    <small class="text-muted">Complétez votre profil pour activer les paiements</small>
  </div>
  <div class="text-end">
    <small class="text-muted">Profil complété</small>
    <div class="progress mt-1" style="width:150px; height:6px;">
      <div id="kyc-progress-bar" class="progress-bar bg-warning" style="width:0%"></div>
    </div>
    <small id="kyc-progress-text" class="text-warning">0%</small>
  </div>
</div>
<div id="main-kyc-alert"></div>
<div id="kyc-status-box" class="mt-3"></div>
<div class="row g-4">
  <div class="col-md-6">
    <div class="card-epay p-4 h-100">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h6 class="fw-bold mb-0 text-muted">⚡ Compte Stripe</h6>
        <span id="stripe-status-badge" class="status-badge status-warn">Non configuré</span>
      </div>
      <p class="text-muted small mb-3">Configurez Stripe pour activer les paiements internationaux.</p>
      <button id="stripe-action-btn" class="btn btn-warning w-100 fw-bold text-muted mb-5">Configurer Stripe</button>
      <div id="payment-failed-alert" class="alert alert-warning d-none border-0 shadow-sm p-3 mb-4" style="border-radius: 8px;">
        <p class="mb-0 text-muted" style="font-size: 13px; line-height: 1.5;">
          ⚠️ Votre dernier paiement a échoué.
          <a href="javascript:void(0);" id="update-card-btn" class="fw-bold text-decoration-none hover-underline" style="color: #b45309; cursor: pointer;">
            Mettez à jour votre carte pour conserver votre accès Pro
          </a>
        </p>
      </div>
      <button id="btn-cancel-sub" class="btn btn-cancel-custom w-100 fw-bold mt-2 text-muted mb-4" onclick="showCancelModal()">Résilier mon abonnement</button>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card-epay p-4 h-100 d-flex flex-column justify-content-between">
      <div>
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
      </div>
      <a href="https://get.firstbase.io/lzqmlclh3nr9" target="_blank" rel="noopener noreferrer" class="btn btn-warning w-100 fw-bold text-dark text-decoration-none d-flex align-items-center justify-content-center gap-2 text-muted">
        Créer ma LLC & Compte US <i class="fa-solid fa-arrow-up-right-from-square" style="font-size: 0.8rem;"></i>
      </a>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card-epay p-4 h-100 d-flex flex-column justify-content-between">
      <div>
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h6 class="fw-bold mb-0 text-muted"><i class="fa-solid fa-credit-card"></i> Cartes Virtuelles (Issuing)</h6>
          <span id="issuing-status-badge" class="status-badge status-warn">Vérification...</span>
        </div>
        <p class="text-muted small mb-3">Générez et gérez des cartes virtuelles pour vos dépenses professionnelles ou celles de vos équipes.</p>
        <form id="virtual-card-form" class="d-flex flex-column gap-2 mb-3">
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
      </div>
      <button id="btn-create-card" type="button" class="btn btn-warning w-100 fw-bold text-dark mt-3">Créer la carte virtuelle</button>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card-epay p-4 h-100">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h6 class="fw-bold mb-0 text-muted"><i class="fa-brands fa-stripe"></i> Informations du compte Stripe</h6>
      </div>
      <div id="stripe-account-management"></div>
    </div>
  </div>
</div>
<div class="modal fade" id="modalCancelSub" tabindex="-1" aria-hidden="true">
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
          <button type="button" class="btn btn-danger btn-sm fw-bold px-3 py-1" style="font-size: 0.8rem; border-radius: 6px;" id="btn-confirm-cancel" onclick="confirmCancelSubscription()">Résilier</button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

const STRIPE_PUBLISHABLE_KEY =
  "pk_test_51TJYk921oAuf4OUmVuqkub7cs2OUkWGpYlS4IgpfZrF7p6lY4v1YxRirVv1QSZD8Qof4JU78mmLgexh5wINo0vlo00c7HTwz5x";

export async function mount(container) {
  await setViewStyles(["responsive.css", "profil.css"]);
  container.innerHTML = TEMPLATE;

  const boundListeners = [];
  function on(target, type, fn) {
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  async function loadPlanStatus() {
    try {
      const res = await apiFetch("/me/plan");
      const data = await res.json();
      const alertBox = document.getElementById("payment-failed-alert");
      if (alertBox) alertBox.classList.toggle("d-none", data.subscription_status !== "past_due");
      localStorage.setItem("plan", data.plan || "free");
    } catch (err) {
      console.error("Erreur chargement plan:", err);
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

  function setProgress(percent) {
    const bar = document.getElementById("kyc-progress-bar");
    const text = document.getElementById("kyc-progress-text");
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
      const badge = document.getElementById("stripe-status-badge");
      badge.innerText = "Accès restreint";
      badge.classList.remove("status-warn", "status-pending", "status-ok");
      badge.classList.add("status-warn");
      const btn = document.getElementById("stripe-action-btn");
      btn.innerText = "Réservé au propriétaire";
      btn.disabled = true;
      return;
    }
    const data = await res.json();
    updateKycProgress(data);
    const mainAlert = document.getElementById("main-kyc-alert");
    if (!data.connected) {
      mainAlert.innerHTML = `<div class="alert mb-4" style="background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Configurez Stripe pour activer les paiements</div>`;
    } else if (data.needs_kyc) {
      mainAlert.innerHTML = `<div class="alert mb-4" style="background:rgba(255,193,7,0.15); border:1px solid rgba(255,193,7,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Vérification KYC requise pour continuer à recevoir des paiements</div>`;
    } else if (!data.future_requirements) {
      mainAlert.innerHTML = `<div class="alert mb-4" style="background:rgba(34,197,94,0.15); border:1px solid rgba(34,197,94,0.3); border-radius:12px;"><i class="fa-solid fa-circle-check"></i> Compte entièrement vérifié</div>`;
    } else {
      mainAlert.innerHTML = `<div class="alert mb-4" style="background:rgba(255,193,7,0.15); border:1px solid rgba(255,193,7,0.3); border-radius:12px;"><i class="fa-solid fa-triangle-exclamation warning-icon"></i> Compte opérationnel, vérification finale incomplète</div>`;
    }
    const btn = document.getElementById("stripe-action-btn");
    const badge = document.getElementById("stripe-status-badge");
    btn.disabled = false;
    btn.classList.remove("btn-warning", "btn-success");
    btn.classList.add(!data.connected || data.needs_kyc || data.future_requirements ? "btn-warning" : "btn-success");
    badge.classList.remove("status-warn", "stauts-pending", "status-ok");
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
      btn.onclick = () => goToStripeLoginLink(btn);
    } else if (data.future_requirements) {
      badge.innerText = "Opérationnel";
      badge.classList.add("status-pending");
      btn.innerText = "Compléter la vérification finale";
      btn.disabled = false;
      btn.onclick = () => goToStripeLoginLink(btn);
    } else {
      badge.innerText = "Entièrement vérifié";
      badge.classList.add("status-ok");
      btn.innerText = "Compte entièrement vérifié ✅";
      btn.disabled = true;
    }
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

  function showCancelModal() {
    new bootstrap.Modal(document.getElementById("modalCancelSub")).show();
  }

  async function confirmCancelSubscription() {
    const btn = document.getElementById("btn-confirm-cancel");
    if (btn) {
      btn.disabled = true;
      btn.innerText = "Résiliation...";
    }
    try {
      const res = await apiFetch("/me/plan/cancel", { method: "POST" });
      const data = await res.json();
      const modalEl = document.getElementById("modalCancelSub");
      if (modalEl) {
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      if (res.ok) {
        showToast(data.message || "Abonnement résilié avec succès.", "warning");
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

  async function loadProfile() {
    try {
      const res = await apiFetch("/profile");
      const data = await res.json();
      document.getElementById("profile-name") && (document.getElementById("profile-name").innerText = data.full_name || "—");
      document.getElementById("profile-email") && (document.getElementById("profile-email").innerText = data.email || "—");
      document.getElementById("profile-phone") && (document.getElementById("profile-phone").innerText = data.phone || "—");
      document.getElementById("profile-account-id") && (document.getElementById("profile-account-id").innerText = data.account_id || "—");
    } catch (err) {
      console.error("PROFILE ERROR:", err);
    }
  }

  async function loadStripeAccountManagement() {
    const res = await apiFetch("/stripe/account-session", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur Stripe");
    const stripeConnect = window.StripeConnect.init({
      publishableKey: STRIPE_PUBLISHABLE_KEY,
      fetchClientSecret: () => Promise.resolve(data.client_secret),
    });
    const component = stripeConnect.create("account-management");
    document.getElementById("stripe-account-management").appendChild(component);
  }

  const updateBtn = document.getElementById("update-card-btn");
  if (updateBtn) {
    on(updateBtn, "click", async (e) => {
      e.preventDefault();
      try {
        const res = await apiFetch("/me/create-portal-session", { method: "POST" });
        const data = await res.json();
        if (res.ok && data.url) window.location.href = data.url;
        else alert(data.detail || "Impossible d'accéder au portail de facturation.");
      } catch (err) {
        console.error("Erreur redirection portail:", err);
      }
    });
  }

  const createCardBtn = document.getElementById("btn-create-card");
  if (createCardBtn) {
    on(createCardBtn, "click", async () => {
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
        country: "US",
      };
      createCardBtn.disabled = true;
      createCardBtn.innerText = "Création en cours...";
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
        createCardBtn.disabled = false;
        createCardBtn.innerText = "Créer la carte virtuelle";
      }
    });
  }

  window.showCancelModal = showCancelModal;
  window.confirmCancelSubscription = confirmCancelSubscription;

  initStripe();
  loadPlanStatus();
  loadProfile();
  loadStripeAccountManagement().catch(console.error);

  return {
    unmount() {
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      delete window.showCancelModal;
      delete window.confirmCancelSubscription;
    },
  };
}
