// Vue "Mon entreprise" — suivi dédié du dossier Buildness (LLC US + EIN
// via doola) après son lancement, demandé le 2026-11-23 : Paramètres >
// Entreprise reste le point d'entrée pour LANCER/RELANCER un dossier
// (formulaire complet, voir spa/views/parametres.js), cette vue-ci n'est
// que pour CONSULTER l'avancement - accessible directement depuis la
// sidebar (juste sous Commerce), sans repasser par Paramètres.
//
// Passage à des onglets le 2026-11-26 (demande explicite, même patron
// que les onglets Shopify de commerce.js) : seul le bandeau de statut
// (nom de la LLC + barre de progression, statusHeaderHtml) reste FIXE
// en haut - tout le reste se répartit désormais dans 4 onglets
// (Informations de l'entreprise / Statut de la formation / Documents /
// Propriétaire et membres). Contrairement à Shopify, les 4 panneaux
// restent tous montés dans le DOM en permanence (juste masqués via
// display:none selon l'onglet actif) plutôt que remplacés/re-fetchés à
// chaque clic : ça préserve tel quel le mécanisme de poll existant
// (fetchBuildnessStatus toutes les BUILDNESS_POLL_INTERVAL_MS) qui doit
// continuer à rafraîchir les 4 sections même quand elles sont masquées,
// pour qu'elles soient à jour si le marchand change d'onglet plus tard.
// Le récap officiel/fondateur/statut détaillé/documents viennent de 2
// sources qui ne quittent jamais le schéma Xepay (BuildnessCompany ne
// stocke que status/company_name/state/ein_number) : la réponse BRUTE
// doola (responsibleParty/addresses/registeredAgent/ein/
// formationFilingNumber/services) et le catalogue de documents (GET
// /buildness/documents).
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
  createBuildnessCorrectionRequest,
  fetchBuildnessCorrectionRequests,
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

// Modal "Demander une correction" (ajouté le 2026-11-27) - doola
// n'expose aucun endpoint pour modifier une société déjà créée
// (vérifié dans leur doc API + Embedded SDK + spec OpenAPI) et n'a de
// relation directe qu'avec Xepay : ce formulaire ne fait qu'enregistrer
// la demande côté Xepay (POST /buildness/correction-request) et alerter
// un humain côté Xepay par email - JAMAIS une mise à jour automatique
// chez doola, d'où l'avertissement explicite dans le corps du modal.
const BUILDNESS_CORRECTION_MODAL_HTML = `
<div class="modal fade" id="buildnessCorrectionModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header border-0">
        <h5 class="modal-title fw-bold">Demander une correction</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Fermer"></button>
      </div>
      <div class="modal-body px-4 pb-4">
        <p class="text-muted" style="font-size:13px;">doola n'a de relation directe qu'avec Xepay : votre demande nous est transmise, nous relayons ensuite la correction auprès d'eux - ce n'est pas une modification automatique.</p>
        <form id="p-buildness-correction-form">
          <div class="form-group">
            <label>Champ à corriger</label>
            <select id="p-buildness-correction-field" class="form-select" required>
              <option value="" disabled selected>Choisir un champ</option>
              <option value="Raison sociale">Raison sociale</option>
              <option value="Adresse commerciale">Adresse commerciale</option>
              <option value="Secteur d'activité">Secteur d'activité</option>
              <option value="Description de l'activité">Description de l'activité</option>
              <option value="Autre">Autre</option>
            </select>
          </div>
          <div class="form-group" id="p-buildness-correction-field-other-group" style="display:none;">
            <label>Précisez le champ</label>
            <input type="text" id="p-buildness-correction-field-other" class="form-control">
          </div>
          <div class="form-group">
            <label>Nouvelle valeur souhaitée</label>
            <input type="text" id="p-buildness-correction-value" class="form-control" required>
          </div>
          <div class="form-group">
            <label>Note (optionnel)</label>
            <textarea id="p-buildness-correction-note" class="form-control"></textarea>
          </div>
          <button type="submit" class="create-client-btn" id="p-buildness-correction-submit">Envoyer la demande</button>
        </form>
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

// Centré (demande du 2026-11-26) - PAS .mon-entreprise-header (flex-row,
// icône+texte côte à côte, utilisé tel quel par statusHeaderHtml) :
// classe dédiée à cet état vide précisément pour ne jamais affecter
// l'autre usage.
function notStartedHtml() {
  return `
    <div class="mon-entreprise-card">
      <div class="mon-entreprise-empty-state">
        <div class="mon-entreprise-icon"><i class="fa-solid fa-building-circle-xmark"></i></div>
        <h3 class="mon-entreprise-title">Aucun dossier en cours</h3>
        <p class="mon-entreprise-status">Vous n'avez pas encore lancé la création de votre société américaine.</p>
        <div class="params-promo-actions">
          <button type="button" id="p-mon-entreprise-goto-params" class="create-client-btn">Créer ma société</button>
        </div>
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
    </div>
  `;
}

function formatAddress(addr) {
  if (!addr) return "—";
  const parts = [addr.line1, addr.line2, addr.postalCode, addr.city, addr.state, addr.country].filter(Boolean);
  return parts.join(", ") || "—";
}

// Disposition multi-ligne demandée le 2026-11-26 (remplace la version
// en une seule ligne de formatAddress ci-dessus, réservée à cet usage
// précis - formatAddress reste utilisée telle quelle ailleurs, ex.
// founderPanelHtml) : ligne 1, ligne 2 (optionnelle), "code postal,
// ville", "état, pays" - jamais de ligne vide si line2 est absent.
function addressLines(addr) {
  if (!addr) return [];
  const lines = [];
  if (addr.line1) lines.push(`${addr.line1},`);
  if (addr.line2) lines.push(`${addr.line2},`);
  const cityLine = [addr.postalCode, addr.city].filter(Boolean).join(", ");
  if (cityLine) lines.push(cityLine);
  const stateLine = [addr.state, addr.country].filter(Boolean).join(", ");
  if (stateLine) lines.push(stateLine);
  return lines;
}

// Bloc adresse copiable (icône copier, demande du 2026-11-26) - exclu
// de la grille scintillée en vrac (.mon-entreprise-grid, voir son
// commentaire) via la classe mon-entreprise-stat--address : un bloc de
// 4 lignes ne peut pas recevoir les mêmes décalages verticaux
// nth-child, pensés pour des valeurs d'une seule ligne. Le texte copié
// (wireAddressCopyButtons, plus bas) est lu directement depuis le DOM
// rendu (innerText, qui respecte les <br>), jamais reconstruit à part -
// une seule source de vérité pour ce qui est affiché vs copié.
function addressBlockHtml(label, addr) {
  const lines = addressLines(addr);
  if (!lines.length) return statHtml(label, "—");
  return `
    <div class="mon-entreprise-stat mon-entreprise-stat--address">
      <div class="mon-entreprise-stat-label">${label}</div>
      <div class="mon-entreprise-address">
        <div class="mon-entreprise-stat-value mon-entreprise-address-lines">${lines.join("<br>")}</div>
        <button type="button" class="mon-entreprise-copy-btn" title="Copier l'adresse"><i class="fa-regular fa-copy"></i></button>
      </div>
    </div>
  `;
}

function findAddress(raw, type) {
  const entry = (raw.addresses || []).find((a) => a.type === type);
  return entry ? entry.address : null;
}

function formatDateFr(value) {
  if (!value || isNaN(new Date(value))) return null;
  return new Date(value).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

const BUILDNESS_ENTITY_TYPE_LABELS = { LLC: "LLC", CCorp: "C-Corp" };

// Traduction best-effort des status/subStatus de raw.services (jamais
// affichés avant le 2026-11-25) - repli sur la valeur brute si elle
// n'est pas connue, plutôt que de la masquer.
const BUILDNESS_SERVICE_STATUS_LABELS = {
  NotStarted: "pas encore commencé",
  InProgress: "en cours",
  Active: "actif",
  Completed: "terminé",
  Done: "terminé",
  Failed: "échoué",
};
const BUILDNESS_SERVICE_SUBSTATUS_LABELS = {
  WaitingForFilingServiceToComplete: "en attente de la fin de la formation",
  WaitingForRaToSucceed: "en attente de la confirmation de l'agent enregistré",
  WaitingForDocumentsFromState: "en attente des documents de l'État",
};
function serviceStatusText(service) {
  if (!service) return null;
  const statusLabel = BUILDNESS_SERVICE_STATUS_LABELS[service.status] || service.status;
  const subLabel = service.subStatus
    ? (BUILDNESS_SERVICE_SUBSTATUS_LABELS[service.subStatus] || service.subStatus)
    : null;
  return subLabel ? `${statusLabel} - ${subLabel}` : statusLabel;
}
function findService(raw, name) {
  return (raw.services || []).find((s) => s.name === name) || null;
}
// Services qu'on demande explicitement dans le payload (voir
// backend/routes/buildness.py) - tout le reste (ex. "AiCofounder",
// jamais demandé par nous, vu sur un vrai dossier le 2026-11-25) est
// affiché génériquement plus bas, sans supposer ce qu'il fait.
const BUILDNESS_KNOWN_SERVICE_NAMES = new Set(["Formation", "EinCreation", "RegisteredAgent"]);

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
// numéro de dossier, adresses, agent enregistré...), jamais stocké côté
// Xepay : lu directement depuis la réponse brute doola. Limité aux
// FAITS depuis le passage aux onglets (2026-11-26) - tout ce qui relève
// de l'avancement/statut de chaque service vit désormais dans
// formationStatusHtml (onglet "Statut de la formation") plus bas.
function officialRecapHtml(raw) {
  // business lu depuis addresses[] (voir backend/routes/buildness.py,
  // corrigé le 2026-11-25 pour matcher le schéma doola) - l'adresse
  // commerciale DE LA LLC, un champ à part de celle de l'agent
  // enregistré même quand les deux coïncident physiquement (le
  // fondateur n'a pas d'autre adresse à donner) - CORRIGÉ le
  // 2026-11-26 : identifié sur un vrai dossier que "business"
  // (state="WYOMING") et "registeredAgent.address" (state="WY") sont
  // deux CHAMPS distincts côté doola représentant 2 concepts différents
  // (adresse de la LLC vs adresse de l'agent), même quand leur rue
  // coïncide - jamais à dédoublonner entre eux, contrairement à ce
  // qu'on pensait la veille. "mailing" (adresse de correspondance,
  // souvent celle, personnelle, du fondateur hors des US) retirée de ce
  // bloc à la demande explicite.
  const business = findAddress(raw, "business");
  const agentAddress = raw.registeredAgent ? raw.registeredAgent.address : null;

  const stats = [
    statHtml("EIN (identifiant fiscal)", raw.ein || "Pas encore émis"),
    statHtml("Numéro de dossier de formation", raw.formationFilingNumber || "En attente"),
    statHtml("Raison sociale validée par l'État", raw.legalName || "En attente de validation"),
    statHtml("Type de société", BUILDNESS_ENTITY_TYPE_LABELS[raw.entityType] || raw.entityType || "—"),
    // État confirmé par doola (raw.state) - jamais réaffiché avant le
    // 2026-11-25, alors que c'est la valeur faisant foi, distincte de
    // ce qui a simplement été saisi au départ côté Xepay.
    statHtml("État de formation", raw.state || "—"),
  ];

  // Secteur/description de l'activité (ajoutés le 2026-11-26, jamais
  // affichés avant - confirmés inutilisés par l'utilisateur). Pas
  // doolaCompanyId/doolaCustomerId : identifiants techniques internes,
  // sans intérêt pour le marchand (voir backend/models.py,
  // BuildnessCompany.doola_company_id - déjà stocké côté Xepay, unique,
  // c'est lui qui sert à certifier qu'une LLC vient bien du partenariat
  // Xepay/doola, pas un champ à afficher ici).
  if (raw.industry) stats.push(statHtml("Secteur d'activité", raw.industry));
  if (raw.description) stats.push(statHtml("Description de l'activité", raw.description));

  const dateStats = [
    raw.formationSubmittedToStateAt ? statHtml("Soumis à l'État le", formatDateFr(raw.formationSubmittedToStateAt)) : null,
    raw.formationFilingDate ? statHtml("Formation déposée le", formatDateFr(raw.formationFilingDate)) : null,
    raw.einApplicationSubmittedAt ? statHtml("EIN demandé le", formatDateFr(raw.einApplicationSubmittedAt)) : null,
  ].filter(Boolean);
  stats.push(...dateStats);

  if (formatAddress(business) !== "—") {
    stats.push(addressBlockHtml("Adresse commerciale", business));
  }

  // Téléphone de contact - rattaché à l'adresse commerciale fournie par
  // le fondateur (provider=customer), jamais affiché avant le
  // 2026-11-25.
  if (business && business.phone) stats.push(statHtml("Téléphone de contact", business.phone));

  if (raw.registeredAgent) {
    stats.push(statHtml("Agent enregistré", raw.registeredAgent.name || "—"));
    stats.push(addressBlockHtml("Adresse de l'agent enregistré", agentAddress));
  }

  return `
    <div class="mon-entreprise-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-landmark"></i> Informations de l'entreprise</h4>
      <div class="mon-entreprise-grid">${stats.join("")}</div>
    </div>
  `;
}

// Avancement service par service - extrait d'officialRecapHtml le
// 2026-11-26 (passage aux onglets, demande explicite) : onglet dédié
// "Statut de la formation", séparé des faits "officiels" ci-dessus. Les
// 3 services qu'on demande explicitement (Formation/EinCreation/
// RegisteredAgent, voir backend/routes/buildness.py) ont chacun leur
// propre ligne via subStatus (ex. "en attente des documents de
// l'État") - plus précis que le simple "..." du bandeau de statut fixe
// en haut (statusHeaderHtml, jamais touché par ce découpage).
function formationStatusHtml(raw) {
  const formationService = findService(raw, "Formation");
  const einService = findService(raw, "EinCreation");
  const agentService = findService(raw, "RegisteredAgent");

  const stats = [
    statHtml("Formation de la société", serviceStatusText(formationService) || "—"),
    statHtml("Obtention de l'EIN", serviceStatusText(einService) || "—"),
  ];
  if (raw.registeredAgent) {
    stats.push(statHtml("Agent enregistré", serviceStatusText(agentService) || "—"));
  }

  // Signatures déjà complétées (ex. SS4) - AJOUTÉ le 2026-11-26 :
  // jusqu'ici, une fois signée, aucune trace n'en restait nulle part
  // (signatureBannerHtml ne montre que les signatures EN ATTENTE) - le
  // marchand n'avait aucun moyen de revérifier qu'il avait bien signé.
  (raw.signatureRequirements || [])
    .filter((s) => String(s.status || "").toUpperCase() === "COMPLETED")
    .forEach((s) => stats.push(statHtml(
      BUILDNESS_SIGNATURE_LABELS[s.documentType] || s.documentType,
      "Déjà signé ✓"
    )));

  // Tout service qu'on n'a jamais explicitement demandé (ex.
  // "AiCofounder", vu sur un vrai dossier le 2026-11-25) - affiché tel
  // quel, sans supposer ce qu'il fait.
  (raw.services || [])
    .filter((s) => !BUILDNESS_KNOWN_SERVICE_NAMES.has(s.name))
    .forEach((s) => stats.push(statHtml(s.name, serviceStatusText(s) || "—")));

  return `
    <div class="mon-entreprise-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-list-check"></i> Avancement détaillé</h4>
      <div class="mon-entreprise-grid">${stats.join("")}</div>
    </div>
  `;
}

// Membres à gauche / propriétaire à droite (demande du 2026-11-26,
// remplace le panneau unique précédent) : raw.members[] (chacun avec sa
// part, ownershipPercent) à gauche, raw.responsibleParty (le fondateur/
// responsable légal transmis à doola lors de la création) à droite -
// 2 sources déjà distinctes dans la réponse brute doola, jamais
// mélangées entre elles.
function founderPanelHtml(raw) {
  const rp = raw.responsibleParty || {};
  const members = Array.isArray(raw.members) ? raw.members : [];

  const ownerStats = [
    statHtml("Nom complet", [rp.legalFirstName, rp.legalLastName].filter(Boolean).join(" ") || "—"),
    statHtml("Email", rp.email || "—"),
    statHtml("Adresse", formatAddress(rp.address)),
  ];

  const memberStats = members.map((m) => {
    const name = m.legalFirstName ? [m.legalFirstName, m.legalLastName].filter(Boolean).join(" ") : (m.contactFullName || "Ce membre");
    return statHtml(name, `${m.ownershipPercent}%`);
  });

  return `
    <div class="mon-entreprise-owners-layout">
      <div class="mon-entreprise-card">
        <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-users"></i> Membres</h4>
        ${memberStats.length
          ? `<div class="mon-entreprise-stack">${memberStats.join("")}</div>`
          : `<p class="text-muted" style="font-size:13.5px;">Aucun membre renseigné.</p>`}
      </div>
      <div class="mon-entreprise-card">
        <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-user"></i> Propriétaire</h4>
        <div class="mon-entreprise-stack">${ownerStats.join("")}</div>
      </div>
    </div>
  `;
}

// NON VÉRIFIÉ sur un vrai document (voir doola_service.list_documents) -
// plusieurs noms de champs possibles tentés par ordre de plausibilité,
// jamais une forme supposée à l'aveugle comme définitive.
//
// Disposition "carte" (demande du 2026-11-26, remplace la liste de
// lignes précédente) - doola ne fournit aucune vignette/aperçu visuel
// du document (juste downloadUrl, récupéré à la demande via
// fetchBuildnessDocument) : la "zone image" est donc une icône de
// document stylée en grand format, jamais une fausse miniature
// inventée. Bouton de téléchargement réduit à l'icône seule (pas de
// texte "Télécharger").
function documentCardHtml(doc) {
  const name = doc.name || doc.documentType || doc.type || "Document";
  const rawDate = doc.createdAt || doc.uploadedAt || doc.date;
  const dateLabel = rawDate && !isNaN(new Date(rawDate))
    ? new Date(rawDate).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" })
    : "—";
  const docId = doc.documentId || doc.id || "";
  return `
    <div class="mon-entreprise-doc-card">
      <div class="mon-entreprise-doc-preview"><i class="fa-solid fa-file-lines"></i></div>
      <div class="mon-entreprise-doc-caption">
        <div class="mon-entreprise-doc-name">${name}</div>
        <div class="mon-entreprise-doc-date">${dateLabel}</div>
      </div>
      <button type="button" class="mon-entreprise-doc-download" data-document-id="${docId}" title="Télécharger"><i class="fa-solid fa-download"></i></button>
    </div>
  `;
}

function documentsCardHtml(documents) {
  return `
    <div class="mon-entreprise-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-folder-open"></i> Documents</h4>
      ${documents && documents.length
        ? `<div class="mon-entreprise-doc-grid">${documents.map(documentCardHtml).join("")}</div>`
        : `<p class="text-muted" style="font-size:13.5px;">Aucun document disponible pour le moment - ils apparaîtront ici dès que doola les transmettra (statuts déposés, lettre EIN...).</p>`}
    </div>
  `;
}

// Demande de correction (ajouté le 2026-11-27) - bouton + historique des
// demandes déjà envoyées (POST/GET /buildness/correction-request(s)) -
// voir le commentaire de BUILDNESS_CORRECTION_MODAL_HTML plus haut :
// jamais une modification automatique, juste une demande tracée.
const BUILDNESS_CORRECTION_STATUS_LABELS = { pending: "En attente", resolved: "Résolue", rejected: "Refusée" };

function correctionRequestRowHtml(r) {
  const dateLabel = formatDateFr(r.created_at) || "—";
  const statusLabel = BUILDNESS_CORRECTION_STATUS_LABELS[r.status] || r.status;
  return `
    <div class="mon-entreprise-doc-row">
      <div class="mon-entreprise-doc-icon"><i class="fa-solid fa-pen"></i></div>
      <div class="mon-entreprise-doc-info">
        <div class="mon-entreprise-doc-name">${r.field_label} → ${r.requested_value}</div>
        <div class="mon-entreprise-doc-date">${dateLabel} - ${statusLabel}</div>
      </div>
    </div>
  `;
}

function correctionSectionHtml(requests) {
  return `
    <div class="mon-entreprise-card">
      <h4 class="mon-entreprise-section-title"><i class="fa-solid fa-pen-to-square"></i> Demande de correction</h4>
      <p class="text-muted" style="font-size:13px; margin-bottom:12px;">Une info à corriger (adresse, secteur, description...) ? doola n'a de relation directe qu'avec Xepay - votre demande nous est transmise, nous relayons ensuite la correction auprès d'eux.</p>
      <button type="button" class="create-client-btn" id="p-buildness-open-correction">Demander une correction</button>
      ${requests && requests.length ? `<div style="margin-top:20px;">${requests.map(correctionRequestRowHtml).join("")}</div>` : ""}
    </div>
  `;
}

// 4 onglets (demande du 2026-11-26, même patron que SHOPIFY_TABS dans
// commerce.js) - paneHtml pose juste le squelette (conteneur + état de
// chargement initial), rempli ensuite par render() via les mêmes ids
// qu'avant le passage aux onglets (#mon-entreprise-official-container
// etc.), jamais détruits/recréés au changement d'onglet (voir le
// commentaire en tête de fichier).
const MON_ENTREPRISE_TABS = [
  {
    key: "infos",
    label: "Informations de l'entreprise",
    paneHtml: `
      <div id="mon-entreprise-official-container"><div class="mon-entreprise-card">${viewLoadingHtml()}</div></div>
      <div id="mon-entreprise-correction-container"></div>
    `,
  },
  {
    key: "statut",
    label: "Statut de la formation",
    paneHtml: `<div id="mon-entreprise-signature-container"></div><div id="mon-entreprise-status-detail-container"><div class="mon-entreprise-card">${viewLoadingHtml()}</div></div>`,
  },
  {
    key: "documents",
    label: "Documents de l'entreprise",
    paneHtml: `<div id="mon-entreprise-documents-container"><div class="mon-entreprise-card">${viewLoadingHtml()}</div></div>`,
  },
  {
    key: "proprietaire",
    label: "Propriétaire et membres",
    paneHtml: `<div id="mon-entreprise-founder-container"><div class="mon-entreprise-card">${viewLoadingHtml()}</div></div>`,
  },
];

function monEntrepriseTabsHtml() {
  return `
    <div class="mon-entreprise-tabs" id="mon-entreprise-tabs">
      ${MON_ENTREPRISE_TABS.map((t, i) => `<button type="button" class="mon-entreprise-tab${i === 0 ? " mon-entreprise-tab--active" : ""}" data-mon-entreprise-tab="${t.key}">${t.label}</button>`).join("")}
    </div>
    ${MON_ENTREPRISE_TABS.map((t, i) => `<div class="mon-entreprise-tab-pane" data-mon-entreprise-pane="${t.key}"${i === 0 ? "" : ' style="display:none;"'}>${t.paneHtml}</div>`).join("")}
  `;
}

// Simple bascule d'affichage (display:none), jamais un remplacement de
// contenu : les 4 panneaux restent tous montés et à jour en continu
// (voir le commentaire en tête de fichier sur le poll).
function wireMonEntrepriseTabs(root) {
  const tabsEl = root.querySelector("#mon-entreprise-tabs");
  if (!tabsEl) return;
  tabsEl.querySelectorAll("[data-mon-entreprise-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.classList.contains("mon-entreprise-tab--active")) return;
      tabsEl.querySelectorAll(".mon-entreprise-tab").forEach((b) => b.classList.remove("mon-entreprise-tab--active"));
      btn.classList.add("mon-entreprise-tab--active");
      const key = btn.dataset.monEntrepriseTab;
      root.querySelectorAll("[data-mon-entreprise-pane]").forEach((pane) => {
        pane.style.display = pane.dataset.monEntreprisePane === key ? "" : "none";
      });
    });
  });
}

export async function mount(container) {
  await setViewStyles(["parametres.css"]);
  container.innerHTML = TEMPLATE;
  document.body.insertAdjacentHTML("beforeend", BUILDNESS_SIGNATURE_MODAL_HTML);
  document.body.insertAdjacentHTML("beforeend", BUILDNESS_CORRECTION_MODAL_HTML);

  document.getElementById("p-buildness-correction-field")?.addEventListener("change", (e) => {
    const otherGroup = document.getElementById("p-buildness-correction-field-other-group");
    if (otherGroup) otherGroup.style.display = e.target.value === "Autre" ? "" : "none";
  });
  document.getElementById("p-buildness-correction-form")?.addEventListener("submit", submitBuildnessCorrection);

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

  // Copie l'adresse affichée (demande du 2026-11-26) - lue directement
  // depuis le DOM rendu (innerText respecte les <br>), jamais
  // reconstruite à part : garantit que ce qui est copié correspond
  // exactement à ce qui est affiché.
  function wireAddressCopyButtons(root) {
    root.querySelectorAll(".mon-entreprise-copy-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const lines = btn.closest(".mon-entreprise-address")?.querySelector(".mon-entreprise-address-lines");
        if (!lines) return;
        try {
          await navigator.clipboard.writeText(lines.innerText);
          showToast("Adresse copiée", "success");
        } catch (err) {
          showToast("Impossible de copier l'adresse", "error");
        }
      });
    });
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

  function openCorrectionModal() {
    const form = document.getElementById("p-buildness-correction-form");
    if (form) form.reset();
    const otherGroup = document.getElementById("p-buildness-correction-field-other-group");
    if (otherGroup) otherGroup.style.display = "none";
    bootstrap.Modal.getOrCreateInstance(document.getElementById("buildnessCorrectionModal")).show();
  }

  async function submitBuildnessCorrection(e) {
    e.preventDefault();
    const fieldSelect = document.getElementById("p-buildness-correction-field");
    const fieldOther = document.getElementById("p-buildness-correction-field-other");
    const fieldLabel = fieldSelect.value === "Autre" ? (fieldOther.value || "").trim() : fieldSelect.value;
    const requestedValue = document.getElementById("p-buildness-correction-value").value.trim();
    const note = document.getElementById("p-buildness-correction-note").value.trim();
    if (!fieldLabel || !requestedValue) return;

    const btn = document.getElementById("p-buildness-correction-submit");
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>`;
    try {
      await createBuildnessCorrectionRequest(fieldLabel, requestedValue, note);
      showToast("Demande envoyée - nous la transmettrons à doola", "success");
      const modalEl = document.getElementById("buildnessCorrectionModal");
      const instance = modalEl && bootstrap.Modal.getInstance(modalEl);
      if (instance) instance.hide();
      loadCorrectionSection();
    } catch (err) {
      showToast(err.message || "Erreur lors de l'envoi", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }

  // Charge/affiche le bouton + l'historique des demandes de correction -
  // appelée au premier rendu du dossier ET juste après l'envoi d'une
  // nouvelle demande (demande du 2026-11-27), jamais à chaque tick du
  // poll (contrairement au récap officiel/fondateur/documents) : les
  // demandes de correction ne changent jamais côté doola/webhook, rien
  // ne justifie un refresh automatique périodique ici.
  function loadCorrectionSection() {
    const el = document.getElementById("mon-entreprise-correction-container");
    if (!el) return;
    fetchBuildnessCorrectionRequests()
      .then((requests) => {
        el.innerHTML = correctionSectionHtml(requests);
        el.querySelector("#p-buildness-open-correction")?.addEventListener("click", openCorrectionModal);
      })
      .catch((err) => console.warn("[Mon entreprise] Echec recuperation demandes de correction :", err));
  }

  // Rendu en 2 temps : le bandeau de statut (rapide, DB Xepay) s'affiche
  // immédiatement ; le récap officiel/statut détaillé/fondateur/
  // documents (appels doola en parallèle, plus lents) se remplissent
  // ensuite chacun dans leur propre conteneur (voir MON_ENTREPRISE_TABS),
  // sans bloquer l'affichage du statut.
  //
  // hasRenderedLayout (ajouté le 2026-11-25, même correctif que les
  // onglets Shopify) : render() est aussi appelé à chaque tick du
  // poll ci-dessous, pas juste au premier chargement - sans ce
  // garde-fou, la reconstruction complète du HTML (+ les onglets)
  // remettait tout en "Chargement..." à CHAQUE refresh auto, faisant
  // sauter la vue. Seul le bandeau de statut est remis à jour en place
  // sur les rafraîchissements suivants ; les 4 panneaux gardent leur
  // contenu jusqu'à ce que les nouvelles données soient prêtes.
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
        ${monEntrepriseTabsHtml()}
      `;
      wireMonEntrepriseTabs(el);
      loadCorrectionSection();
      hasRenderedLayout = true;
    }

    fetchBuildnessRawStatus()
      .then((raw) => {
        console.log("[Mon entreprise] Réponse BRUTE doola ->", raw);
        const signatureEl = document.getElementById("mon-entreprise-signature-container");
        if (signatureEl) {
          signatureEl.innerHTML = signatureBannerHtml(raw);
          wireSignatureButtons(signatureEl);
        }
        const statusDetailEl = document.getElementById("mon-entreprise-status-detail-container");
        if (statusDetailEl) statusDetailEl.innerHTML = formationStatusHtml(raw);
        const officialEl = document.getElementById("mon-entreprise-official-container");
        if (officialEl) {
          officialEl.innerHTML = officialRecapHtml(raw);
          wireAddressCopyButtons(officialEl);
        }
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
      ["buildnessSignatureModal", "buildnessCorrectionModal"].forEach((id) => {
        const modalEl = document.getElementById(id);
        const instance = modalEl && bootstrap.Modal.getInstance(modalEl);
        if (instance) {
          instance.hide();
          instance.dispose();
        }
        modalEl?.remove();
      });
      document.body.classList.remove("modal-open");
      document.body.style.removeProperty("overflow");
      document.body.style.removeProperty("padding-right");
      document.querySelectorAll(".modal-backdrop").forEach((el) => el.remove());
    },
  };
}
