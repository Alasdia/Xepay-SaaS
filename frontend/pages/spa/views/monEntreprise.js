// Vue "Mon entreprise" — suivi dédié du dossier Buildness (LLC US + EIN
// via doola) après son lancement, demandé le 2026-11-23 : Paramètres >
// Entreprise reste le point d'entrée pour LANCER/RELANCER un dossier
// (formulaire complet, voir spa/views/parametres.js), cette vue-ci n'est
// que pour CONSULTER l'avancement - accessible directement depuis la
// sidebar (juste sous Commerce), sans repasser par Paramètres.
//
// Mise en page refaite le 2026-11-24 (demande explicite) : bandeau de
// statut en haut (toute la largeur), puis 2 colonnes - 75% à gauche
// (récap officiel en haut, catalogue de documents en dessous) / 25% à
// droite (informations du fondateur). Le récap officiel/fondateur/
// documents viennent de 2 sources qui ne quittent jamais le schéma
// Xepay (BuildnessCompany ne stocke que status/company_name/state/
// ein_number) : la réponse BRUTE doola (responsibleParty/addresses/
// registeredAgent/ein/formationFilingNumber) et le nouveau catalogue de
// documents (GET /buildness/documents).
import { setViewStyles } from "../core/styleLoader.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";
import { showToast } from "../shared/toast.js";
import { viewLoadingHtml } from "../shared/loadingSpinner.js";
import {
  BUILDNESS_TERMINAL_STATUSES,
  BUILDNESS_POLL_INTERVAL_MS,
  buildnessStatusLabel,
  fetchBuildnessStatus,
  fetchBuildnessRawStatus,
  fetchBuildnessDocuments,
  fetchBuildnessDocument,
  createBuildnessSignatureSession,
} from "../shared/buildnessStatus.js";

const BUILDNESS_STEPS = ["draft", "submitted", "processing", "completed"];

// Libellés des documents à signer (signatureRequirements côté doola) -
// "SS4"/"FORM8821" sont les seules valeurs possibles.
const BUILDNESS_SIGNATURE_LABELS = {
  SS4: "Formulaire SS-4 (demande d'EIN auprès de l'IRS)",
  FORM8821: "Formulaire 8821 (autorisation fiscale)",
};

// Modal de signature : l'URL renvoyée par doola s'affiche en iframe
// (explicitement supporté de leur côté), jamais dans un nouvel onglet -
// le marchand reste dans Xepay, même principe que l'onboarding Stripe
// Connect intégré.
const BUILDNESS_SIGNATURE_MODAL_HTML = `
<div class="modal fade" id="buildnessSignatureModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-lg">
    <div class="modal-content">
      <div class="modal-header border-0">
        <h5 class="modal-title fw-bold">Signature requise</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fermer"></button>
      </div>
      <div class="modal-body px-4 pb-4">
        <div id="buildness-signature-frame-container"></div>
      </div>
    </div>
  </div>
</div>
`;

const TEMPLATE = `
  <h1 class="page-title"><i class="fa-solid fa-building"></i> Mon entreprise</h1>
  <p class="params-subsection-sub" style="max-width:640px; margin-bottom:24px;">Suivi de la formation de votre société américaine (LLC) et de l'obtention de son EIN (identifiant fiscal fédéral) via notre partenaire doola.</p>
  <div id="mon-entreprise-container">${viewLoadingHtml()}</div>
`;

function notStartedHtml() {
  return `
    <div class="mon-entreprise-card">
      <div class="mon-entreprise-header">
        <div class="mon-entreprise-icon"><i class="fa-solid fa-building-circle-xmark"></i></div>
        <div>
          <h3 class="mon-entreprise-title">Aucun dossier en cours</h3>
          <p class="mon-entreprise-status">Vous n'avez pas encore lancé la création de votre société américaine.</p>
        </div>
      </div>
      <div class="params-promo-actions">
        <button type="button" id="p-mon-entreprise-goto-params" class="create-client-btn">Créer ma société</button>
      </div>
    </div>
  `;
}

// 4 segments (draft/submitted/processing/completed) - colorés jusqu'à
// la dernière étape réussie (voire tous en rouge si failed), jamais un
// stepper interactif, juste un repère visuel de progression.
function stepsHtml(data) {
  const upTo = BUILDNESS_STEPS.indexOf(data.last_successful_step || data.status);
  return `
    <div class="mon-entreprise-steps">
      ${BUILDNESS_STEPS.map((_, i) => {
        const cls = data.status === "failed" && i > upTo ? "" : (i <= upTo ? (data.status === "failed" ? "failed" : "done") : "");
        return `<div class="mon-entreprise-step ${cls}"></div>`;
      }).join("")}
    </div>
  `;
}

function statHtml(label, value) {
  return `
    <div class="mon-entreprise-stat">
      <div class="mon-entreprise-stat-label">${label}</div>
      <div class="mon-entreprise-stat-value">${value}</div>
    </div>
  `;
}

// Bandeau de statut, toute la largeur - jamais le détail des champs ici
// (voir officialRecapHtml/founderPanelHtml plus bas pour ça).
function statusHeaderHtml(data) {
  const status = data.status;
  const statusClass = status === "completed" ? "status-done" : status === "failed" ? "status-failed" : "status-processing";
  const icon = status === "completed" ? "fa-circle-check" : status === "failed" ? "fa-circle-exclamation" : "fa-clock";
  return `
    <div class="mon-entreprise-card" style="margin-bottom:20px;">
      <div class="mon-entreprise-header" style="margin-bottom:0;">
        <div class="mon-entreprise-icon"><i class="fa-solid fa-building"></i></div>
        <div>
          <h3 class="mon-entreprise-title">${data.company_name || "Votre société"}</h3>
          <p class="mon-entreprise-status ${statusClass}"><i class="fa-solid ${icon}"></i> ${buildnessStatusLabel(status)}${status !== "completed" && status !== "failed" ? "..." : ""}</p>
        </div>
      </div>
      ${stepsHtml(data)}
      <div class="params-promo-actions">
        <button type="button" id="p-mon-entreprise-goto-params" class="create-client-btn">${status === "failed" ? "Réessayer" : "Créer une autre société"}</button>
      </div>
    </div>
  `;
}

function formatAddress(addr) {
  if (!addr) return "—";
  const parts = [addr.line1, addr.line2, addr.postalCode, addr.city, addr.state, addr.country].filter(Boolean);
  return parts.join(", ") || "—";
}

function findAddress(raw, type) {
  const entry = (raw.addresses || []).find((a) => a.type === type);
  return entry ? entry.address : null;
}

const BUILDNESS_ENTITY_TYPE_LABELS = { LLC: "LLC", CCorp: "C-Corp" };

// Bannière d'ACTION REQUISE - signatureRequirements côté doola (ex:
// [{"documentType":"SS4","status":"PENDING"}]). Ajoutée le 2026-11-24 :
// ce blocage existait sur les 3 LLC sandbox (formation figée en attente
// de la signature SS-4) sans qu'aucun écran Xepay ne le signale, le
// marchand n'avait aucun moyen de savoir qu'il devait agir.
function signatureBannerHtml(raw) {
  const pending = (raw.signatureRequirements || []).filter(
    (s) => String(s.status || "").toUpperCase() === "PENDING"
  );
  if (!pending.length) return "";
  return `
    <div class="mon-entreprise-card mon-entreprise-action-required">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-triangle-exclamation"></i> Action requise de votre part</h4>
      <p class="mon-entreprise-action-sub">La création de votre société est en attente de votre signature. Sans elle, doola ne peut pas demander votre EIN auprès de l'IRS.</p>
      ${pending.map((s) => `
        <div class="mon-entreprise-doc-row">
          <div class="mon-entreprise-doc-icon"><i class="fa-solid fa-file-signature"></i></div>
          <div class="mon-entreprise-doc-info">
            <div class="mon-entreprise-doc-name">${BUILDNESS_SIGNATURE_LABELS[s.documentType] || s.documentType}</div>
            <div class="mon-entreprise-doc-date">En attente de signature</div>
          </div>
          <button type="button" class="create-client-btn mon-entreprise-sign-btn" data-document-type="${s.documentType}">Signer maintenant</button>
        </div>
      `).join("")}
    </div>
  `;
}

// Récap "officiel" - ce qu'on trouverait dans les documents (EIN,
// numéro de dossier, adresses virtuelles, agent enregistré...), jamais
// stocké côté Xepay : lu directement depuis la réponse brute doola.
function officialRecapHtml(raw) {
  const business = findAddress(raw, "business");
  const mailing = findAddress(raw, "mailing");
  const stats = [
    statHtml("EIN (identifiant fiscal)", raw.ein || "Pas encore émis"),
    statHtml("Numéro de dossier de formation", raw.formationFilingNumber || "En attente"),
    statHtml("Raison sociale validée par l'État", raw.legalName || "En attente de validation"),
    statHtml("Type de société", BUILDNESS_ENTITY_TYPE_LABELS[raw.entityType] || raw.entityType || "—"),
    statHtml("Adresse commerciale (agent enregistré)", formatAddress(business)),
    statHtml("Boîte postale virtuelle (correspondance)", formatAddress(mailing)),
  ];
  if (raw.registeredAgent) {
    stats.push(statHtml("Agent enregistré", raw.registeredAgent.name || "—"));
    stats.push(statHtml("Adresse de l'agent enregistré", formatAddress(raw.registeredAgent.address)));
  }
  return `
    <div class="mon-entreprise-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-landmark"></i> Informations officielles</h4>
      <div class="mon-entreprise-grid">${stats.join("")}</div>
    </div>
  `;
}

// Panneau latéral (25%) - le fondateur/responsable légal, tel que
// transmis à doola lors de la création (voir responsibleParty/members
// dans la réponse brute).
function founderPanelHtml(raw) {
  const rp = raw.responsibleParty || {};
  const stats = [
    statHtml("Nom complet", [rp.legalFirstName, rp.legalLastName].filter(Boolean).join(" ") || "—"),
    statHtml("Email", rp.email || "—"),
    statHtml("Adresse", formatAddress(rp.address)),
  ];
  if (Array.isArray(raw.members)) {
    raw.members.forEach((m) => {
      const name = m.legalFirstName ? [m.legalFirstName, m.legalLastName].filter(Boolean).join(" ") : (m.contactFullName || "Ce membre");
      stats.push(statHtml(`Part de ${name}`, `${m.ownershipPercent}%`));
    });
  }
  return `
    <div class="mon-entreprise-card mon-entreprise-side-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-user"></i> Fondateur / Responsable légal</h4>
      <div class="mon-entreprise-stack">${stats.join("")}</div>
    </div>
  `;
}

// NON VÉRIFIÉ sur un vrai document (voir doola_service.list_documents) -
// plusieurs noms de champs possibles tentés par ordre de plausibilité,
// jamais une forme supposée à l'aveugle comme définitive.
function documentRowHtml(doc) {
  const name = doc.name || doc.documentType || doc.type || "Document";
  const rawDate = doc.createdAt || doc.uploadedAt || doc.date;
  const dateLabel = rawDate && !isNaN(new Date(rawDate))
    ? new Date(rawDate).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
    : "—";
  const docId = doc.documentId || doc.id || "";
  return `
    <div class="mon-entreprise-doc-row">
      <div class="mon-entreprise-doc-icon"><i class="fa-solid fa-file-lines"></i></div>
      <div class="mon-entreprise-doc-info">
        <div class="mon-entreprise-doc-name">${name}</div>
        <div class="mon-entreprise-doc-date">${dateLabel}</div>
      </div>
      <button type="button" class="mon-entreprise-doc-download" data-document-id="${docId}"><i class="fa-solid fa-download"></i> Télécharger</button>
    </div>
  `;
}

function documentsCardHtml(documents) {
  return `
    <div class="mon-entreprise-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-folder-open"></i> Documents</h4>
      ${documents && documents.length
        ? documents.map(documentRowHtml).join("")
        : `<p class="text-muted" style="font-size:13.5px;">Aucun document disponible pour le moment - ils apparaîtront ici dès que doola les transmettra (statuts déposés, lettre EIN...).</p>`}
    </div>
  `;
}

export async function mount(container) {
  await setViewStyles(["parametres.css"]);
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", BUILDNESS_SIGNATURE_MODAL_HTML);

  let pollTimer = null;
  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function gotoParametresEntreprise() {
    navigate(`/dash/workspace/${encodeURIComponent(getWorkspaceId())}/parametres/entreprise`);
  }

  function wireDocumentDownloads(root) {
    root.querySelectorAll(".mon-entreprise-doc-download").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const documentId = btn.dataset.documentId;
        if (!documentId) return;
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;
        try {
          const doc = await fetchBuildnessDocument(documentId);
          if (doc.downloadUrl) window.open(doc.downloadUrl, "_blank", "noopener");
        } catch (err) {
          console.error("[Mon entreprise] Echec telechargement document:", err);
        } finally {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
        }
      });
    });
  }

  // Une NOUVELLE session de signature est créée à chaque clic (l'URL
  // doola expire 2h après émission - jamais réutilisée/mise en cache),
  // puis affichée en iframe dans le modal : le marchand signe sans
  // quitter Xepay.
  function wireSignatureButtons(root) {
    root.querySelectorAll(".mon-entreprise-sign-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const documentType = btn.dataset.documentType || "SS4";
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Préparation...`;
        try {
          const session = await createBuildnessSignatureSession(documentType);
          const frameContainer = document.getElementById("buildness-signature-frame-container");
          if (frameContainer && session.url) {
            frameContainer.innerHTML = `<iframe src="${session.url}" class="buildness-signature-frame" title="Signature ${documentType}"></iframe>`;
            bootstrap.Modal.getOrCreateInstance(document.getElementById("buildnessSignatureModal")).show();
          }
        } catch (err) {
          showToast(err.message || "Impossible de démarrer la signature", "error");
        } finally {
          btn.disabled = false;
          btn.innerHTML = originalHtml;
        }
      });
    });
  }

  // Rendu en 2 temps : le bandeau de statut (rapide, DB Xepay) s'affiche
  // immédiatement ; le récap officiel/fondateur/documents (3 appels
  // doola en parallèle, plus lents) se remplissent ensuite chacun dans
  // leur propre conteneur, sans bloquer l'affichage du statut.
  //
  // hasRenderedLayout (ajouté le 2026-11-25, même correctif que les
  // onglets Shopify) : render() est aussi appelé à chaque tick du
  // poll ci-dessous, pas juste au premier chargement - sans ce
  // garde-fou, la reconstruction complète du HTML remettait les 3
  // cartes en "Chargement..." à CHAQUE refresh auto, faisant sauter la
  // vue (cas explicitement cité comme contre-exemple pour Shopify).
  // Seul le bandeau de statut est remis à jour en place sur les
  // rafraîchissements suivants ; les 3 cartes gardent leur contenu
  // jusqu'à ce que les nouvelles données soient prêtes.
  let hasRenderedLayout = false;

  function render(data) {
    const el = document.getElementById("mon-entreprise-container");
    if (!el) return;
    if (!data.status || data.status === "not_started") {
      el.innerHTML = notStartedHtml();
      const btn = document.getElementById("p-mon-entreprise-goto-params");
      if (btn) btn.addEventListener("click", gotoParametresEntreprise);
      hasRenderedLayout = false;
      return;
    }
    if (hasRenderedLayout) {
      const banner = document.getElementById("mon-entreprise-status-banner");
      if (banner) banner.innerHTML = statusHeaderHtml(data);
    } else {
      el.innerHTML = `
        <div id="mon-entreprise-status-banner">${statusHeaderHtml(data)}</div>
        <div id="mon-entreprise-signature-container"></div>
        <div class="mon-entreprise-layout">
          <div class="mon-entreprise-main">
            <div id="mon-entreprise-official-container"><div class="mon-entreprise-card">${viewLoadingHtml()}</div></div>
            <div id="mon-entreprise-documents-container"><div class="mon-entreprise-card">${viewLoadingHtml()}</div></div>
          </div>
          <div id="mon-entreprise-founder-container"><div class="mon-entreprise-card mon-entreprise-side-card">${viewLoadingHtml()}</div></div>
        </div>
      `;
      hasRenderedLayout = true;
    }
    const btn = document.getElementById("p-mon-entreprise-goto-params");
    if (btn) btn.addEventListener("click", gotoParametresEntreprise);

    fetchBuildnessRawStatus()
      .then((raw) => {
        console.log("[Mon entreprise] Réponse BRUTE doola ->", raw);
        const signatureEl = document.getElementById("mon-entreprise-signature-container");
        if (signatureEl) {
          signatureEl.innerHTML = signatureBannerHtml(raw);
          wireSignatureButtons(signatureEl);
        }
        const officialEl = document.getElementById("mon-entreprise-official-container");
        if (officialEl) officialEl.innerHTML = officialRecapHtml(raw);
        const founderEl = document.getElementById("mon-entreprise-founder-container");
        if (founderEl) founderEl.innerHTML = founderPanelHtml(raw);
      })
      .catch((err) => console.warn("[Mon entreprise] Echec recuperation reponse brute doola :", err));

    fetchBuildnessDocuments()
      .then((documents) => {
        const docsEl = document.getElementById("mon-entreprise-documents-container");
        if (!docsEl) return;
        docsEl.innerHTML = documentsCardHtml(documents);
        wireDocumentDownloads(docsEl);
      })
      .catch((err) => console.warn("[Mon entreprise] Echec recuperation documents :", err));
  }

  async function load() {
    try {
      const data = await fetchBuildnessStatus();
      render(data);
      if (data.status && !BUILDNESS_TERMINAL_STATUSES.has(data.status)) {
        stopPolling();
        pollTimer = setInterval(async () => {
          try {
            const next = await fetchBuildnessStatus();
            render(next);
            if (BUILDNESS_TERMINAL_STATUSES.has(next.status)) stopPolling();
          } catch (err) {
            if (err.isForbidden) stopPolling();
          }
        }, BUILDNESS_POLL_INTERVAL_MS);
      }
    } catch (err) {
      const el = document.getElementById("mon-entreprise-container");
      if (el) {
        el.innerHTML = err.isForbidden
          ? `<p class="text-muted">Vous n'avez pas les droits pour consulter cette page.</p>`
          : `<p class="text-muted">Erreur de chargement.</p>`;
      }
    }
  }

  load();

  return {
    unmount() {
      stopPolling();
      // Même nettoyage que les autres vues à modal (voir mountEntreprise
      // dans parametres.js) : sans ça, le backdrop et les classes posées
      // sur <body> survivent à la navigation.
      const modalEl = document.getElementById("buildnessSignatureModal");
      const instance = modalEl && bootstrap.Modal.getInstance(modalEl);
      if (instance) {
        instance.hide();
        instance.dispose();
      }
      modalEl?.remove();
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("overflow");
      document.body.style.removeProperty("padding-right");
      document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    },
  };
}
