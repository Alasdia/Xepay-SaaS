import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";
import { initDetailsDrawer } from "../shared/detailsDrawer.js";
import { navigate } from "../core/router.js";
import { getWorkspaceId } from "../core/state.js";

// Pays acceptés par Stripe pour une adresse (address.country) : tout code
// ISO 3166-1 alpha-2, à l'exception de Cuba, l'Iran, la Corée du Nord et la
// Syrie, non pris en charge par Stripe (voir "Supported countries" dans la
// doc Stripe). Triée par nom affiché à l'affichage (voir buildCountryOptions).
const STRIPE_COUNTRIES = [
    ["AD", "Andorre"], ["AE", "Émirats arabes unis"], ["AF", "Afghanistan"],
    ["AG", "Antigua-et-Barbuda"], ["AI", "Anguilla"], ["AL", "Albanie"],
    ["AM", "Arménie"], ["AO", "Angola"], ["AQ", "Antarctique"],
    ["AR", "Argentine"], ["AS", "Samoa américaines"], ["AT", "Autriche"],
    ["AU", "Australie"], ["AW", "Aruba"], ["AX", "Îles Åland"],
    ["AZ", "Azerbaïdjan"], ["BA", "Bosnie-Herzégovine"], ["BB", "Barbade"],
    ["BD", "Bangladesh"], ["BE", "Belgique"], ["BF", "Burkina Faso"],
    ["BG", "Bulgarie"], ["BH", "Bahreïn"], ["BI", "Burundi"],
    ["BJ", "Bénin"], ["BL", "Saint-Barthélemy"], ["BM", "Bermudes"],
    ["BN", "Brunei"], ["BO", "Bolivie"],
    ["BQ", "Bonaire, Saint-Eustache et Saba"], ["BR", "Brésil"],
    ["BS", "Bahamas"], ["BT", "Bhoutan"], ["BV", "Île Bouvet"],
    ["BW", "Botswana"], ["BY", "Biélorussie"], ["BZ", "Belize"],
    ["CA", "Canada"], ["CC", "Îles Cocos"], ["CD", "Congo (RDC)"],
    ["CF", "République centrafricaine"], ["CG", "Congo"], ["CH", "Suisse"],
    ["CI", "Côte d’Ivoire"], ["CK", "Îles Cook"], ["CL", "Chili"],
    ["CM", "Cameroun"], ["CN", "Chine"], ["CO", "Colombie"],
    ["CR", "Costa Rica"], ["CV", "Cap-Vert"], ["CW", "Curaçao"],
    ["CX", "Île Christmas"], ["CY", "Chypre"], ["CZ", "République tchèque"],
    ["DE", "Allemagne"], ["DJ", "Djibouti"], ["DK", "Danemark"],
    ["DM", "Dominique"], ["DO", "République dominicaine"],
    ["DZ", "Algérie"], ["EC", "Équateur"], ["EE", "Estonie"],
    ["EG", "Égypte"], ["EH", "Sahara occidental"], ["ER", "Érythrée"],
    ["ES", "Espagne"], ["ET", "Éthiopie"], ["FI", "Finlande"],
    ["FJ", "Fidji"], ["FK", "Îles Malouines"], ["FM", "Micronésie"],
    ["FO", "Îles Féroé"], ["FR", "France"], ["GA", "Gabon"],
    ["GB", "Royaume-Uni"], ["GD", "Grenade"], ["GE", "Géorgie"],
    ["GF", "Guyane française"], ["GG", "Guernesey"], ["GH", "Ghana"],
    ["GI", "Gibraltar"], ["GL", "Groenland"], ["GM", "Gambie"],
    ["GN", "Guinée"], ["GP", "Guadeloupe"], ["GQ", "Guinée équatoriale"],
    ["GR", "Grèce"],
    ["GS", "Géorgie du Sud-et-les Îles Sandwich du Sud"],
    ["GT", "Guatemala"], ["GU", "Guam"], ["GW", "Guinée-Bissau"],
    ["GY", "Guyana"], ["HK", "Hong Kong"],
    ["HM", "Îles Heard-et-MacDonald"], ["HN", "Honduras"],
    ["HR", "Croatie"], ["HT", "Haïti"], ["HU", "Hongrie"],
    ["ID", "Indonésie"], ["IE", "Irlande"], ["IL", "Israël"],
    ["IM", "Île de Man"], ["IN", "Inde"],
    ["IO", "Territoire britannique de l’océan Indien"], ["IQ", "Irak"],
    ["IS", "Islande"], ["IT", "Italie"], ["JE", "Jersey"],
    ["JM", "Jamaïque"], ["JO", "Jordanie"], ["JP", "Japon"],
    ["KE", "Kenya"], ["KG", "Kirghizistan"], ["KH", "Cambodge"],
    ["KI", "Kiribati"], ["KM", "Comores"],
    ["KN", "Saint-Christophe-et-Niévès"], ["KR", "Corée du Sud"],
    ["KW", "Koweït"], ["KY", "Îles Caïmans"], ["KZ", "Kazakhstan"],
    ["LA", "Laos"], ["LB", "Liban"], ["LC", "Sainte-Lucie"],
    ["LI", "Liechtenstein"], ["LK", "Sri Lanka"], ["LR", "Libéria"],
    ["LS", "Lesotho"], ["LT", "Lituanie"], ["LU", "Luxembourg"],
    ["LV", "Lettonie"], ["LY", "Libye"], ["MA", "Maroc"],
    ["MC", "Monaco"], ["MD", "Moldavie"], ["ME", "Monténégro"],
    ["MF", "Saint-Martin"], ["MG", "Madagascar"], ["MH", "Îles Marshall"],
    ["MK", "Macédoine du Nord"], ["ML", "Mali"], ["MM", "Myanmar"],
    ["MN", "Mongolie"], ["MO", "Macao"], ["MP", "Îles Mariannes du Nord"],
    ["MQ", "Martinique"], ["MR", "Mauritanie"], ["MS", "Montserrat"],
    ["MT", "Malte"], ["MU", "Maurice"], ["MV", "Maldives"],
    ["MW", "Malawi"], ["MX", "Mexique"], ["MY", "Malaisie"],
    ["MZ", "Mozambique"], ["NA", "Namibie"],
    ["NC", "Nouvelle-Calédonie"], ["NE", "Niger"], ["NF", "Île Norfolk"],
    ["NG", "Nigéria"], ["NI", "Nicaragua"], ["NL", "Pays-Bas"],
    ["NO", "Norvège"], ["NP", "Népal"], ["NR", "Nauru"], ["NU", "Niue"],
    ["NZ", "Nouvelle-Zélande"], ["OM", "Oman"], ["PA", "Panama"],
    ["PE", "Pérou"], ["PF", "Polynésie française"],
    ["PG", "Papouasie-Nouvelle-Guinée"], ["PH", "Philippines"],
    ["PK", "Pakistan"], ["PL", "Pologne"],
    ["PM", "Saint-Pierre-et-Miquelon"], ["PN", "Îles Pitcairn"],
    ["PR", "Porto Rico"], ["PS", "Territoires palestiniens"],
    ["PT", "Portugal"], ["PW", "Palaos"], ["PY", "Paraguay"],
    ["QA", "Qatar"], ["RE", "Réunion"], ["RO", "Roumanie"],
    ["RS", "Serbie"], ["RU", "Russie"], ["RW", "Rwanda"],
    ["SA", "Arabie saoudite"], ["SB", "Îles Salomon"], ["SC", "Seychelles"],
    ["SD", "Soudan"], ["SE", "Suède"], ["SG", "Singapour"],
    ["SH", "Sainte-Hélène"], ["SI", "Slovénie"],
    ["SJ", "Svalbard et Jan Mayen"], ["SK", "Slovaquie"],
    ["SL", "Sierra Leone"], ["SM", "Saint-Marin"], ["SN", "Sénégal"],
    ["SO", "Somalie"], ["SR", "Suriname"], ["SS", "Soudan du Sud"],
    ["ST", "Sao Tomé-et-Principe"], ["SV", "Salvador"],
    ["SX", "Saint-Martin (partie néerlandaise)"],
    ["SZ", "Eswatini (Swaziland)"], ["TC", "Îles Turques-et-Caïques"],
    ["TD", "Tchad"], ["TF", "Terres australes françaises"], ["TG", "Togo"],
    ["TH", "Thaïlande"], ["TJ", "Tadjikistan"], ["TK", "Tokelau"],
    ["TL", "Timor oriental"], ["TM", "Turkménistan"], ["TN", "Tunisie"],
    ["TO", "Tonga"], ["TR", "Turquie"], ["TT", "Trinité-et-Tobago"],
    ["TV", "Tuvalu"], ["TW", "Taïwan"], ["TZ", "Tanzanie"],
    ["UA", "Ukraine"], ["UG", "Ouganda"], ["US", "États-Unis"],
    ["UY", "Uruguay"], ["UZ", "Ouzbékistan"],
    ["VA", "État de la Cité du Vatican"],
    ["VC", "Saint-Vincent-et-les-Grenadines"], ["VE", "Venezuela"],
    ["VG", "Îles Vierges britanniques"], ["VI", "Îles Vierges américaines"],
    ["VN", "Vietnam"], ["VU", "Vanuatu"], ["WF", "Wallis-et-Futuna"],
    ["WS", "Samoa"], ["YE", "Yémen"], ["YT", "Mayotte"],
    ["ZA", "Afrique du Sud"], ["ZM", "Zambie"], ["ZW", "Zimbabwe"],
].sort((a, b) => a[1].localeCompare(b[1], "fr"));

function buildCountryOptions(selectedCode = "") {
    return STRIPE_COUNTRIES.map(
        ([code, name]) =>
            `<option value="${code}" ${code === selectedCode ? "selected" : ""}>${name}</option>`
    ).join("");
}

// Même format que la colonne Date de Paiements (views/transactions.js) :
// jour/mois abrégé/année + heure:minute, plus compact que le format par
// défaut de toLocaleString (secondes incluses, jj/mm/aaaa numérique).
// Partagé par toutes les vues de ce fichier pour un format unique.
function formatDate(timestampSeconds) {
    return timestampSeconds
        ? new Date(timestampSeconds * 1000).toLocaleDateString("fr-FR", {
            day: "2-digit",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        })
        : "—";
}

// xepay_type (posé côté backend sur chaque metadata - voir _enrich_metadata
// et create_link) identifie l'entité réellement concernée, indépendamment
// de l'entityLabel passé par l'appelant - traduit en français pour la ligne
// "Objet" de la section Métadonnées.
const XEPAY_TYPE_LABELS = {
    merchant_invoice: "Facture",
    merchant_subscription: "Abonnement",
    merchant_customer: "Client",
    merchant_product: "Produit",
    payment_link: "Lien",
};

// payment_type (posé uniquement sur les metadata Paiement - voir
// create_checkout_session) décrit comment le paiement a été initié.
const PAYMENT_TYPE_LABELS = {
    payment_link: "Paiement par lien",
};

// Ordre d'affichage fixe plutôt que l'ordre d'insertion du dict (qui place
// user_id avant link_id/merchant_id côté Paiement) - les clés absentes de
// cette liste sont affichées après, dans leur ordre d'origine.
const METADATA_KEY_ORDER = ["link_id", "merchant_id", "payment_type", "user_id", "workspace_id", "xepay_type"];

function sortMetadataEntries(entries) {
    return [...entries].sort(([keyA], [keyB]) => {
        const a = METADATA_KEY_ORDER.indexOf(keyA);
        const b = METADATA_KEY_ORDER.indexOf(keyB);
        if (a === -1 && b === -1) return 0;
        if (a === -1) return 1;
        if (b === -1) return -1;
        return a - b;
    });
}

// user_id/workspace_id arrivent déjà enrichis "<id> (email)" par le backend
// (voir _enrich_metadata) quand l'email est connu - on sépare ça en deux
// lignes Email/Id plutôt que d'afficher la chaîne combinée brute. Sans
// email connu (parenthèse absente), seule la ligne Id est affichée.
function renderIdentityRow(label, value) {
    const match = /^(.+) \((.+)\)$/.exec(String(value));
    const id = match ? match[1] : value;
    const email = match ? match[2] : null;
    return `
        <div class="customer-detail-item">
            <span>${label}</span>
            <strong>
                ${email ? `<div>Email : ${email}</div>` : ""}
                <div>Id : ${id}</div>
            </strong>
        </div>
    `;
}

function renderIdRow(label, value) {
    return `
        <div class="customer-detail-item">
            <span>${label}</span>
            <strong>Id : ${value}</strong>
        </div>
    `;
}

// Bloc "Métadonnées" partagé par les modals de détails (Clients/Produits/
// Abonnements/Factures/Paiements/Liens) : affiche les metadata envoyées à
// la création (user_id/workspace_id/xepay_type, etc.) quand il y en a,
// sinon ne rend rien (pas de section vide). entityLabel ("Client",
// "Produit", "Abonnement", "Facture", "Paiement", "Lien") personnalise le
// libellé de user_id ("<entité> créé par" plutôt que l'ID technique).
// source (Paiement uniquement, toujours "xepay") n'a pas sa propre ligne -
// affiché entre parenthèses à côté du titre "Lien de paiement".
export function renderMetadataSection(metadata, entityLabel = "") {
    const entries = Object.entries(metadata || {});
    if (!entries.length) return "";
    const source = metadata.source;
    const rows = sortMetadataEntries(entries.filter(([key]) => key !== "source")).map(([key, value]) => {
        if (key === "user_id") {
            return renderIdentityRow(entityLabel ? `${entityLabel} créé par` : "Créé par", value);
        }
        if (key === "workspace_id") {
            return renderIdentityRow("Workspace", value);
        }
        if (key === "xepay_type") {
            return `
                <div class="customer-detail-item">
                    <span>Objet</span>
                    <strong>${XEPAY_TYPE_LABELS[value] || entityLabel || value}</strong>
                </div>
            `;
        }
        if (key === "link_id") {
            return renderIdRow(`Lien de paiement${source ? ` (${source})` : ""}`, value);
        }
        if (key === "merchant_id") {
            return renderIdentityRow("Marchand", value);
        }
        if (key === "payment_type") {
            return `
                <div class="customer-detail-item">
                    <span>Type de paiement</span>
                    <strong>${PAYMENT_TYPE_LABELS[value] || value}</strong>
                </div>
            `;
        }
        return `
            <div class="customer-detail-item">
                <span>${key}</span>
                <strong>${value}</strong>
            </div>
        `;
    });
    return `
        <div style="margin-top:20px;">
            <h4>Métadonnées</h4>
            <div class="customer-details-grid">
                ${rows.join("")}
            </div>
        </div>
    `;
}

// Menu d'actions "..." partagé par Clients/Produits/Abonnements/Factures.
// .row-menu-dropdown est position:fixed (voir commerce.css) : ça suffit à
// échapper à l'overflow de #customers-scroll-box sans déplacer l'élément
// dans le DOM (position:fixed se positionne déjà par rapport au viewport,
// pas par rapport à un ancêtre avec overflow, contrairement à absolute/
// relative qui se faisaient couper pour les lignes hors de la zone visible
// du tableau). Seul le top/left est calculé en JS via getBoundingClientRect
// du bouton cliqué. Déclaré une seule fois au niveau module (pas dans une
// fonction render*) pour que les listeners document/window ne soient
// jamais dupliqués, quel que soit le nombre de fois où une vue est
// (re)montée.
let openRowMenuState = null;

function closeRowMenu() {
    if (!openRowMenuState) return;
    const { dropdown, row } = openRowMenuState;
    dropdown.classList.remove("row-menu-dropdown-open");
    dropdown.style.top = "";
    dropdown.style.left = "";
    row.classList.remove("open");
    openRowMenuState = null;
}

function openRowMenu(trigger) {
    closeRowMenu();

    const row = trigger.closest(".row-menu");
    const dropdown = row.querySelector(".row-menu-dropdown");

    dropdown.classList.add("row-menu-dropdown-open");
    row.classList.add("open");

    const rect = trigger.getBoundingClientRect();
    const menuRect = dropdown.getBoundingClientRect();
    let top = rect.bottom + 4;
    if (top + menuRect.height > window.innerHeight) {
        top = rect.top - menuRect.height - 4;
    }
    let left = rect.right - menuRect.width;
    if (left < 4) left = 4;
    dropdown.style.top = `${top}px`;
    dropdown.style.left = `${left}px`;

    openRowMenuState = { dropdown, row };
}

document.addEventListener("click", (event) => {
    if (!openRowMenuState) return;
    if (
        event.target.closest(".row-menu-dropdown") ||
        event.target.closest(".row-menu-trigger")
    ) return;
    closeRowMenu();
});
// Capture (3e argument true) : un scroll à l'intérieur de
// #customers-scroll-box ne remonte jamais jusqu'à window via bubbling
// (scroll ne bubble pas), seule la phase de capture le détecte.
document.addEventListener("scroll", () => closeRowMenu(), true);
window.addEventListener("resize", () => closeRowMenu());
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeRowMenu();
});

export async function mount(container, params = {}) {

    // Évite un dropdown de menu ••• orphelin dans <body> (réparenté par
    // openRowMenu) si on change de section (ex: Produits -> Clients)
    // pendant qu'un menu est encore ouvert - son .row-menu d'origine est
    // détruit par le container.innerHTML ci-dessous, mais pas le dropdown
    // lui-même puisqu'il a été déplacé hors de cet arbre.
    closeRowMenu();

    const section = params.section || "clients";

    setViewStyles(["commerce.css"]);

    container.innerHTML = `
        <div class="commerce-view">
            <div id="commerce-content"></div>
        </div>
    `;

    const content = container.querySelector("#commerce-content");

    switch (section) {

        case "clients":
            await renderClients(content);
            break;

        case "produits":
            await renderProducts(content);
            break;

        case "abonnements":
            await renderSubscriptions(content);
            break;

        case "factures":
            await renderInvoices(content);
            break;

        case "moyens-paiement":
            await renderPaymentMethods(content);
            break;

        case "risque":
            await renderRisk(content);
            break;

        case "shopify":
            await renderShopify(content);
            break;

        default:
            await renderClients(content);
    }
}

/* =========================================================
   KPI CLIQUABLES — composant partagé
   (style et logique de filtrage repris de "Moyens de paiement" :
   .payment-method-kpi / .payment-method-filters, voir renderPaymentMethods
   plus bas — classes génériques ici pour être réutilisées par Clients,
   Produits, Abonnements, Factures et Paiements sans dupliquer le CSS
   4 fois.)
========================================================= */

export function ensureCommerceKpiStyles() {

    if (document.querySelector("#commerce-kpi-style")) return;

    const style = document.createElement("style");
    style.id = "commerce-kpi-style";
    style.textContent = `
        .commerce-kpi-filters {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        .commerce-kpi {
            width: 100%;
            min-height: 58px;
            padding: 9px 13px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #ffffff;
            text-align: left;
            cursor: pointer;
            transition:
                border-color .15s ease,
                background .15s ease,
                box-shadow .15s ease;
        }
        .commerce-kpi:hover {
            border-color: #cbd5e1;
            background: #fafafa;
        }
        .commerce-kpi.active {
            border-color: #94a3b8;
            background: #f8fafc;
            box-shadow: 0 0 0 1px #94a3b8;
        }
        .commerce-kpi-label {
            display: block;
            font-size: 12px;
            line-height: 16px;
            color: #6b7280;
            margin-bottom: 2px;
        }
        .commerce-kpi-value {
            display: block;
            font-size: 19px;
            line-height: 21px;
            font-weight: 600;
            color: #111827;
        }
        .commerce-kpi-sub {
            display: block;
            font-size: 11px;
            line-height: 14px;
            color: #9ca3af;
            margin-top: 4px;
        }
        /* Variante non cliquable (simple affichage de stat, pas de filtre)
           — même carte visuelle que .commerce-kpi, sans curseur pointeur ni
           effet hover/active. Utilisée par les KPI "Paiements" (voir
           transactions.js) qui n'ont pas de logique de filtrage. */
        .commerce-kpi-display {
            cursor: default;
        }
        .commerce-kpi-display:hover {
            border-color: #e5e7eb;
            background: #ffffff;
        }
        /* Variante agrandie — même style (couleurs/bordure/radius), juste
           une taille plus importante pour des KPI mis en avant (grille
           moins dense, police plus grande) plutôt que des petits filtres. */
        .commerce-kpi-filters.commerce-kpi-filters-lg {
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
        }
        .commerce-kpi-lg {
            min-height: 92px;
            padding: 16px 18px;
        }
        .commerce-kpi-lg .commerce-kpi-label {
            font-size: 13px;
        }
        .commerce-kpi-lg .commerce-kpi-value {
            font-size: 24px;
            line-height: 28px;
        }
        /* Variante Paiements : icône représentative du KPI à gauche de la
           carte, contenu (titre/valeur/sous-titre) à droite — space-between
           pour que l'icône reste ancrée à gauche et le texte à droite,
           avec l'espace réservé entre les deux (voir transactions.js).
           Typographie réduite/grisée : l'opacité réduite s'ajoute à
           .text-muted (qui ne fait que griser la couleur, pas l'opacité)
           pour un rendu plus discret que le reste des KPI. */
        .commerce-kpi-paiements-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }
        .commerce-kpi-paiements-text {
            text-align: right;
            opacity: .85;
        }
        .commerce-kpi-paiements-text .commerce-kpi-label {
            font-size: 13px;
        }
        .commerce-kpi-paiements-text .commerce-kpi-value {
            font-size: 14px;
        }
        .commerce-kpi-paiements-text .commerce-kpi-sub {
            font-size: 13px;
        }
        .commerce-kpi-paiements-icon {
            font-size: 15px;
            flex-shrink: 0;
            opacity: .85;
        }
    `;
    document.head.appendChild(style);
}

/**
 * Affiche une rangée de KPI cliquables dans `targetEl` et rebranche les
 * écouteurs de clic à chaque appel (targetEl.innerHTML est régénéré).
 * `kpis` : [{ filter, label, count }]. `onSelect(filter)` est appelé au
 * clic — à charge de l'appelant de ré-afficher la liste filtrée (le KPI ne
 * touche jamais lui-même au tableau).
 */
export function renderCommerceKpis(targetEl, kpis, activeFilter, onSelect) {

    ensureCommerceKpiStyles();

    targetEl.innerHTML = `
        <div class="commerce-kpi-filters">
            ${kpis.map(kpi => `
                <button
                    type="button"
                    class="commerce-kpi${kpi.filter === activeFilter ? " active" : ""}"
                    data-filter="${kpi.filter}"
                >
                    <span class="commerce-kpi-label">${kpi.label}</span>
                    <strong class="commerce-kpi-value">${kpi.count}</strong>
                </button>
            `).join("")}
        </div>
    `;

    targetEl.querySelectorAll(".commerce-kpi").forEach(button => {
        button.addEventListener("click", () => {
            targetEl.querySelectorAll(".commerce-kpi").forEach(item => {
                item.classList.remove("active");
            });
            button.classList.add("active");
            onSelect(button.dataset.filter);
        });
    });
}

/* =========================================================
   CLIENTS
========================================================= */
async function renderClients(container) {

    container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-solid fa-users"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Clients</h1>
                        <p>Votre répertoire clients Stripe Connect : coordonnées et historique de chaque client, au même endroit. Indispensable dès qu'une même personne est facturée ou abonnée plus d'une fois.</p>
                    </div>
                </div>

                <button
                    type="button"
                    class="create-client-btn"
                    id="open-create-client"
                >
                    + Créer un client
                </button>
            </div>

            <!-- KPI : ZONE INDÉPENDANTE DU TABLEAU -->
            <div id="clients-summary"></div>
        </div>

        <div id="clients-list"></div>

        <!-- MODAL CRÉATION CLIENT -->
        <div class="customer-modal-overlay" id="create-client-modal">
            <div class="customer-modal customer-create-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3 id="create-client-modal-title">Créer un client</h3>
                        <p>Ajoutez les informations de votre client.</p>
                    </div>
                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-create-client"
                    >
                        ×
                    </button>
                </div>
                <form id="create-client-form">

                    <p class="form-hint">
                        Aucun champ n'est obligatoire.
                    </p>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="client-first-name">
                                Prénom
                            </label>
                            <input
                                type="text"
                                id="client-first-name"
                                autocomplete="given-name"
                            >
                        </div>
                        <div class="form-group">
                            <label for="client-last-name">
                                Nom
                            </label>
                            <input
                                type="text"
                                id="client-last-name"
                                autocomplete="family-name"
                            >
                        </div>
                    </div>

                    <div class="form-row">
                        <div class="form-group">
                            <label for="client-email">
                                Email
                            </label>
                            <input
                                type="email"
                                id="client-email"
                                autocomplete="email"
                            >
                        </div>
                        <div class="form-group">
                            <label for="client-phone">
                                Téléphone
                            </label>
                            <input
                                type="tel"
                                id="client-phone"
                                autocomplete="tel"
                            >
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="client-country">
                            Pays
                        </label>
                        <select id="client-country">
                            <option value="">Sélectionner un pays</option>
                            ${buildCountryOptions()}
                        </select>
                    </div>

                    <div class="customer-modal-actions">
                        <button
                            type="button"
                            class="modal-cancel-btn"
                            id="cancel-create-client"
                        >
                            Annuler
                        </button>
                        <button
                            type="submit"
                            class="modal-submit-btn"
                            id="create-client-submit-btn"
                        >
                            Créer le client
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- MODAL DÉTAILS CLIENT -->
        <div class="customer-modal-overlay" id="customer-details-modal">
            <div class="customer-modal customer-details-modal">

                <div class="customer-modal-header">
                    <div>
                        <h3>Détails du client</h3>
                        <p id="customer-details-subtitle"></p>
                    </div>

                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-customer-details"
                    >
                        ×
                    </button>
                </div>

                <div id="customer-details-content"></div>

            </div>
        </div>
    `;

    const createModal =
        container.querySelector("#create-client-modal");

    const detailsModal =
        container.querySelector("#customer-details-modal");

    // Détails client -> tiroir latéral droit (voir shared/detailsDrawer.js) ;
    // la logique d'ouverture/fermeture (classList "open") reste inchangée.
    initDetailsDrawer(
        detailsModal,
        detailsModal.querySelector(".customer-modal")
    );

    const form =
        container.querySelector("#create-client-form");

    // Non-null pendant l'édition d'un client existant (menu ••• ->
    // "Modifier") : le formulaire de création est alors réutilisé tel
    // quel, seul le endpoint appelé par le submit change (voir plus bas).
    let editingCustomerId = null;

    function openClientModalForCreate() {
        editingCustomerId = null;
        form.reset();
        container.querySelector("#create-client-modal-title").textContent =
            "Créer un client";
        container.querySelector("#create-client-submit-btn").textContent =
            "Créer le client";
        createModal.classList.add("open");
    }

    function openClientModalForEdit(customer) {
        editingCustomerId = customer.id;
        const [firstName, ...rest] = (customer.name || "").split(" ");
        container.querySelector("#client-first-name").value = firstName || "";
        container.querySelector("#client-last-name").value = rest.join(" ");
        container.querySelector("#client-email").value = customer.email || "";
        container.querySelector("#client-phone").value = customer.phone || "";
        container.querySelector("#client-country").value = customer.country || "";
        container.querySelector("#create-client-modal-title").textContent =
            "Modifier le client";
        container.querySelector("#create-client-submit-btn").textContent =
            "Enregistrer";
        createModal.classList.add("open");
    }

    /* =====================================================
       OUVRIR / FERMER MODAL CRÉATION
    ===================================================== */

    container
        .querySelector("#open-create-client")
        .addEventListener("click", () => {
            openClientModalForCreate();
        });

    container
        .querySelector("#close-create-client")
        .addEventListener("click", () => {
            createModal.classList.remove("open");
        });

    container
        .querySelector("#cancel-create-client")
        .addEventListener("click", () => {
            createModal.classList.remove("open");
        });

    /* =====================================================
       FERMER MODAL DÉTAILS
    ===================================================== */

    container
        .querySelector("#close-customer-details")
        .addEventListener("click", () => {
            detailsModal.classList.remove("open");
        });

    /* Fermer en cliquant sur l'arrière-plan */
    [createModal, detailsModal].forEach(modal => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.classList.remove("open");
            }
        });
    });

    /* =====================================================
       CHARGER LES CLIENTS
    ===================================================== */

    async function loadCustomers() {

        // Évite un dropdown de menu ••• orphelin dans <body> (réparenté par
        // openRowMenu) si cette fonction est rappelée pendant qu'un menu
        // d'une ligne précédente est encore ouvert.
        closeRowMenu();

        const list =
            container.querySelector("#clients-list");

        list.innerHTML = `
            <div class="commerce-card">
                <p>Chargement des clients...</p>
            </div>
        `;

        try {

            const response = await apiFetch(
                "/stripe/connect/customers"
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de récupérer les clients"
                );
            }

            const customers = data.data || [];

            const summaryEl = container.querySelector("#clients-summary");

            // Pagination 10 par 10 (Précédent/Suivant, même mécanisme que
            // Transactions) - purement côté client : la liste complète est
            // déjà en mémoire (customers, récupérée en un seul appel
            // ci-dessus), donc le KPI et le filtre "Avec solde" continuent
            // de porter sur l'ensemble réel, jamais juste la page affichée.
            const customersPageSize = 10;
            let customersPageNumber = 1;

            function renderTable(filter = "all", { resetPage = true } = {}) {

                if (resetPage) customersPageNumber = 1;

                const filteredCustomers = filter === "balance"
                    ? customers.filter(c => (c.balance ?? 0) > 0)
                    : customers;

                if (!filteredCustomers.length) {

                    list.innerHTML = `
                        <div class="commerce-card">
                            <p>Aucun client dans cette catégorie.</p>
                        </div>
                    `;

                    return;
                }

            const customersPageStart = (customersPageNumber - 1) * customersPageSize;
            const pageCustomers = filteredCustomers.slice(customersPageStart, customersPageStart + customersPageSize);

            list.innerHTML = `
                <div class="table-wrap">

                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div>
                            <div class="table-title">Clients</div>
                            <div class="page-subtitle">
                                ${filteredCustomers.length} client(s)
                            </div>
                        </div>
                    </div>

                    <div id="customers-scroll-box">

                        <table class="table">

                            <thead>
                                <tr>
                                    <th>Client</th>
                                    <th>Email</th>
                                    <th>Téléphone</th>
                                    <th>Pays</th>
                                    <th>Moyen de paiement</th>
                                    <th>Total dépensé</th>
                                    <th>Paiements</th>
                                    <th>Remboursements</th>
                                    <th>Litiges</th>
                                    <th>Créé le</th>
                                    <th>Dernier paiement</th>
                                    <th>Statut</th>
                                    <th></th>
                                </tr>
                            </thead>

                            <tbody>

                                ${pageCustomers.map(customer => `

                                    <tr>

                                        <td>
                                            ${customer.name || "—"}
                                        </td>

                                        <td>
                                            ${customer.email || "—"}
                                        </td>

                                        <td>
                                            ${customer.phone || "—"}
                                        </td>

                                        <td>
                                            ${customer.country || "—"}
                                        </td>

                                        <td>
                                            ${customer.payments_method || "—"}
                                        </td>

                                        <td>
                                            ${
                                                customer.total_spent != null
                                                    ? `${(
                                                        customer.total_spent / 100
                                                    ).toLocaleString(
                                                        "fr-FR",
                                                        {
                                                            minimumFractionDigits: 2,
                                                            maximumFractionDigits: 2
                                                        }
                                                    )} ${(customer.currency || "").toUpperCase()}`
                                                    : "—"
                                            }
                                        </td>

                                        <td>
                                            ${customer.payments_count ?? 0}
                                        </td>

                                        <td>
                                            ${customer.refunds_total ?? 0}
                                        </td>

                                        <td>
                                            ${customer.disputes_total ?? 0}
                                        </td>

                                        <td>
                                            ${formatDate(customer.created)}
                                        </td>

                                        <td>
                                            ${formatDate(customer.last_payment_at)}
                                        </td>

                                        <td>
                                            <span class="${
                                                customer.delinquent
                                                    ? "status-badge status-danger"
                                                    : "status-badge status-success"
                                            }">
                                                ${
                                                    customer.delinquent
                                                        ? "Délinquant"
                                                        : "Actif"
                                                }
                                            </span>
                                        </td>

                                        <td>
                                            <div
                                                class="row-menu"
                                                data-customer-id="${customer.id}"
                                            >
                                                <button
                                                    type="button"
                                                    class="row-menu-trigger"
                                                    aria-label="Actions"
                                                    aria-haspopup="true"
                                                >
                                                    •••
                                                </button>
                                                <div class="row-menu-dropdown">
                                                    <button
                                                        type="button"
                                                        class="row-menu-item"
                                                        data-row-action="details"
                                                    >
                                                        Détails
                                                    </button>
                                                    <button
                                                        type="button"
                                                        class="row-menu-item"
                                                        data-row-action="edit"
                                                    >
                                                        Modifier
                                                    </button>
                                                </div>
                                            </div>
                                        </td>

                                    </tr>

                                `).join("")}

                            </tbody>

                        </table>

                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center mt-3">
                    <span id="customers-pagination-info" class="text-muted">Page ${customersPageNumber}</span>
                    <div class="d-flex gap-2">
                        <button id="customers-prev-page" type="button" class="pagination-nav-btn" ${customersPageNumber <= 1 ? "disabled" : ""}><i class="bi bi-chevron-left"></i></button>
                        <button id="customers-next-page" type="button" class="pagination-nav-btn" ${customersPageStart + customersPageSize >= filteredCustomers.length ? "disabled" : ""}><i class="bi bi-chevron-right"></i></button>
                    </div>
                </div>
            `;

            list.querySelector("#customers-prev-page")?.addEventListener("click", () => {
                if (customersPageNumber <= 1) return;
                customersPageNumber--;
                renderTable(filter, { resetPage: false });
            });
            list.querySelector("#customers-next-page")?.addEventListener("click", () => {
                if (customersPageStart + customersPageSize >= filteredCustomers.length) return;
                customersPageNumber++;
                renderTable(filter, { resetPage: false });
            });

            /* =================================================
               MENU D'ACTIONS PAR LIGNE (•••)
            ================================================= */

            list
                .querySelectorAll(".row-menu-trigger")
                .forEach(trigger => {

                    trigger.addEventListener("click", (event) => {

                        event.stopPropagation();

                        if (trigger.closest(".row-menu").classList.contains("open")) {
                            closeRowMenu();
                        } else {
                            openRowMenu(trigger);
                        }

                    });

                });

            list
                .querySelectorAll("[data-row-action]")
                .forEach(item => {

                    item.addEventListener("click", () => {

                        const row = item.closest(".row-menu");
                        closeRowMenu();

                        const customer = customers.find(
                            c => c.id === row.dataset.customerId
                        );

                        if (!customer) return;

                        if (item.dataset.rowAction === "details") {
                            showCustomerDetails(customer);
                        } else if (item.dataset.rowAction === "edit") {
                            openClientModalForEdit(customer);
                        }
                    });
                });

            }

            /* =================================================
               KPI — Tous / Soldes restants
            ================================================= */

            renderCommerceKpis(
                summaryEl,
                [
                    { filter: "all", label: "Tous", count: customers.length },
                    {
                        filter: "balance",
                        label: "Soldes restants",
                        count: customers.filter(c => (c.balance ?? 0) > 0).length
                    },
                ],
                "all",
                renderTable
            );

            renderTable("all");

        } catch (error) {

            console.error(
                "Erreur récupération Customers Stripe :",
                error
            );

            list.innerHTML = `
                <div class="commerce-card">
                    <p>
                        ${
                            error.message ||
                            "Erreur lors du chargement des clients"
                        }
                    </p>
                </div>
            `;
        }
    }

    /* =====================================================
       DÉTAILS CLIENT
    ===================================================== */

    function showCustomerDetails(customer) {

        container.querySelector(
            "#customer-details-subtitle"
        ).textContent = customer.email || customer.id;

        container.querySelector(
            "#customer-details-content"
        ).innerHTML = `

            <div class="customer-profile">

                <div class="customer-profile-avatar">
                    ${
                        customer.name
                            ? customer.name
                                .split(" ")
                                .map(part => part[0])
                                .join("")
                                .slice(0, 2)
                                .toUpperCase()
                            : "—"
                    }
                </div>

                <div>
                    <h4>
                        ${customer.name || "Client sans nom"}
                    </h4>

                    <code>
                        ${customer.id}
                    </code>
                </div>

            </div>

            <div class="customer-details-grid">

                <div class="customer-detail-item">
                    <span>Identifiant</span>
                    <strong>${customer.id || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Nom</span>
                    <strong>${customer.name || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Email</span>
                    <strong>${customer.email || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Téléphone</span>
                    <strong>${customer.phone || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Pays</span>
                    <strong>${customer.country || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Créé le</span>
                    <strong>
                        ${formatDate(customer.created)}
                    </strong>
                </div>

                <div class="customer-detail-item">
                    <span>Statut</span>
                    <strong>
                        ${
                            customer.delinquent
                                ? "Délinquant"
                                : "Actif"
                        }
                    </strong>
                </div>

            </div>

            <div class="customer-stats">

                <div>
                    <span>Total dépensé</span>
                    <strong>
                        ${
                            customer.total_spent != null
                                ? `${(
                                    customer.total_spent / 100
                                ).toLocaleString(
                                    "fr-FR",
                                    {
                                        minimumFractionDigits: 2,
                                        maximumFractionDigits: 2
                                    }
                                )} ${(customer.currency || "").toUpperCase()}`
                                : "—"
                        }
                    </strong>
                </div>

                <div>
                    <span>Paiements</span>
                    <strong>
                        ${customer.payments_count ?? 0}
                    </strong>
                </div>

                <div>
                    <span>Remboursements</span>
                    <strong>
                        ${customer.refunds_total ?? 0}
                    </strong>
                </div>

                <div>
                    <span>Litiges</span>
                    <strong>
                        ${customer.disputes_total ?? 0}
                    </strong>
                </div>

            </div>

            ${renderMetadataSection(customer.metadata, "Client")}

        `;

        detailsModal.classList.add("open");
    }

    /* =====================================================
       CRÉATION CLIENT
    ===================================================== */

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const firstName =
          container.querySelector("#client-first-name").value.trim();
        const lastName =
          container.querySelector("#client-last-name").value.trim();
        const name = `${firstName} ${lastName}`.trim();
        const email =
          container.querySelector("#client-email").value.trim();
        const phone =
          container.querySelector("#client-phone").value.trim();
        const country =
          container.querySelector("#client-country").value.trim();
        const isEditing = Boolean(editingCustomerId);
        try {
            const response = await apiFetch(
                isEditing
                    ? `/stripe/connect/customers/${editingCustomerId}`
                    : "/stripe/connect/customers",
                {
                    method: "POST",
                    body: {
                        name: name || null,
                        email: email || null,
                        phone: phone || null,
                        country: country || null
                    }
                }
            );
            const data = await response.json();
            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    (isEditing
                        ? "Impossible de modifier le client"
                        : "Impossible de créer le client")
                );
            }

            showToast(
                isEditing
                    ? "Client modifié avec succès"
                    : "Client créé avec succès",
                "success"
            );

            form.reset();
            editingCustomerId = null;

            createModal.classList.remove("open");

            await loadCustomers();

        } catch (error) {

            console.error(error);

            showToast(
                error.message ||
                (isEditing
                    ? "Erreur lors de la modification du client"
                    : "Erreur lors de la création du client"),
                "error"
            );
        }
    });

    await loadCustomers();
}

/* =========================================================
   PRODUITS
========================================================= */

async function renderProducts(container) {

    container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-solid fa-box"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Produits</h1>
                        <p>Votre catalogue : produits et tarifs réutilisables pour vos factures et abonnements. Créez-les une fois, facturez-les autant de fois que nécessaire, sans ressaisir le prix à chaque vente.</p>
                    </div>
                </div>

                <button
                    type="button"
                    class="create-client-btn"
                    id="open-create-product"
                >
                    + Créer un produit
                </button>
            </div>

            <!-- KPI : ZONE INDÉPENDANTE DU TABLEAU -->
            <div id="products-summary"></div>
        </div>

        <div id="products-list"></div>


        <!-- =================================================
             MODAL CRÉATION PRODUIT
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="create-product-modal"
        >

            <div class="customer-modal">

                <div class="customer-modal-header">

                    <div>
                        <h3>Créer un produit</h3>
                        <p>
                            Ajoutez un produit et son tarif Stripe.
                        </p>
                    </div>

                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-create-product"
                    >
                        ×
                    </button>

                </div>


                <form id="create-product-form">

                    <div class="form-group">

                        <label>Nom du produit</label>

                        <input
                            type="text"
                            id="product-name"
                            required
                        >

                    </div>


                    <div class="form-group">

                        <label>Description</label>

                        <textarea
                            id="product-description"
                        ></textarea>

                    </div>


                    <div class="form-row">

                        <div class="form-group">

                            <label>Prix</label>

                            <input
                                type="number"
                                id="product-amount"
                                min="0"
                                required
                            >

                        </div>

                        <div class="form-group">

                            <label>Devise</label>

                            <select id="product-currency">

                                <option value="xof">XOF</option>
                                <option value="usd">USD</option>
                                <option value="eur">EUR</option>

                            </select>

                        </div>

                    </div>


                    <div class="form-group">

                        <label>

                            <input
                                type="checkbox"
                                id="product-recurring"
                            >

                            Abonnement récurrent

                        </label>

                    </div>


                    <div
                        id="product-interval-container"
                        style="display:none;"
                    >

                        <div class="form-row">

                            <div class="form-group">

                                <label>Répéter tous les</label>

                                <input
                                    type="number"
                                    id="product-interval-count"
                                    min="1"
                                    value="1"
                                >

                            </div>

                            <div class="form-group">

                                <label>Intervalle</label>

                                <select id="product-interval">

                                    <option value="day">
                                        Jour(s)
                                    </option>

                                    <option value="week">
                                        Semaine(s)
                                    </option>

                                    <option value="month" selected>
                                        Mois
                                    </option>

                                    <option value="year">
                                        An(s)
                                    </option>

                                </select>

                            </div>

                        </div>

                    </div>


                    <div class="customer-modal-actions">

                        <button
                            type="button"
                            class="modal-cancel-btn"
                            id="cancel-create-product"
                        >
                            Annuler
                        </button>

                        <button
                            type="submit"
                            class="modal-submit-btn"
                        >
                            Créer le produit
                        </button>

                    </div>

                </form>

            </div>

        </div>


        <!-- =================================================
             MODAL DÉTAILS PRODUIT
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="product-details-modal"
        >

            <div class="customer-modal customer-details-modal">

                <div class="customer-modal-header">

                    <div>
                        <h3>Détails du produit</h3>
                        <p id="product-details-subtitle"></p>
                    </div>

                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-product-details"
                    >
                        ×
                    </button>

                </div>

                <div id="product-details-content"></div>

            </div>

        </div>
    `;


    const createModal =
        container.querySelector("#create-product-modal");

    const detailsModal =
        container.querySelector("#product-details-modal");

    // Détails produit -> tiroir latéral droit (voir shared/detailsDrawer.js) ;
    // la logique d'ouverture/fermeture (classList "open") reste inchangée.
    initDetailsDrawer(
        detailsModal,
        detailsModal.querySelector(".customer-modal")
    );

    const form =
        container.querySelector("#create-product-form");


    /* =====================================================
       OUVERTURE / FERMETURE CRÉATION
    ===================================================== */

    container
        .querySelector("#open-create-product")
        .addEventListener("click", () => {

            createModal.classList.add("open");

        });


    container
        .querySelector("#close-create-product")
        .addEventListener("click", () => {

            createModal.classList.remove("open");

        });


    container
        .querySelector("#cancel-create-product")
        .addEventListener("click", () => {

            createModal.classList.remove("open");

        });


    /* =====================================================
       FERMETURE DÉTAILS
    ===================================================== */

    container
        .querySelector("#close-product-details")
        .addEventListener("click", () => {

            detailsModal.classList.remove("open");

        });


    [createModal, detailsModal].forEach(modal => {

        modal.addEventListener("click", event => {

            if (event.target === modal) {
                modal.classList.remove("open");
            }

        });

    });


    /* =====================================================
       INTERVALLE RÉCURRENT
    ===================================================== */

    const recurring =
        container.querySelector("#product-recurring");

    const intervalContainer =
        container.querySelector(
            "#product-interval-container"
        );


    recurring.addEventListener("change", () => {

        intervalContainer.style.display =
            recurring.checked
                ? "block"
                : "none";

    });


    /* =====================================================
       CHARGER LES PRODUITS STRIPE
    ===================================================== */

    async function loadProducts() {

        closeRowMenu();

        const list =
            container.querySelector("#products-list");


        list.innerHTML = `
            <div class="commerce-card">
                <p>Chargement des produits...</p>
            </div>
        `;


        try {

            const response = await apiFetch(
                "/stripe/connect/products"
            );


            const data = await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Impossible de récupérer les produits"
                );

            }


            const products =
                data.data || [];


            console.log(
                "Produits Stripe récupérés :",
                products
            );


            const summaryEl = container.querySelector("#products-summary");

            // Pagination 10 par 10 (Précédent/Suivant, même mécanisme que
            // Transactions) - purement côté client : la liste complète est
            // déjà en mémoire (products, récupérée en un seul appel
            // ci-dessus), donc le KPI et les filtres Actifs/Archivés
            // continuent de porter sur l'ensemble réel.
            const productsPageSize = 10;
            let productsPageNumber = 1;

            function renderTable(filter = "all", { resetPage = true } = {}) {

                if (resetPage) productsPageNumber = 1;

                const filteredProducts = filter === "active"
                    ? products.filter(p => p.active)
                    : filter === "archived"
                        ? products.filter(p => !p.active)
                        : products;

                if (!filteredProducts.length) {

                    list.innerHTML = `
                        <div class="commerce-card">
                            <p>
                                Aucun produit dans cette catégorie.
                            </p>
                        </div>
                    `;

                    return;

                }

            const productsPageStart = (productsPageNumber - 1) * productsPageSize;
            const pageProducts = filteredProducts.slice(productsPageStart, productsPageStart + productsPageSize);

            /* =================================================
               TABLE PRODUITS
            ================================================= */

            list.innerHTML = `

                <div class="table-wrap">
                    <div
                        class="d-flex justify-content-between align-items-center mb-3"
                    >
                        <div>
                            <div class="table-title">
                                Produits
                            </div>

                            <div class="page-subtitle">
                                ${filteredProducts.length} produit(s)
                            </div>
                        </div>
                    </div>
                    <div id="customers-scroll-box">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Produit</th>
                                    <th>Description</th>
                                    <th>Prix</th>
                                    <th>Type</th>
                                    <th>Récurrence</th>
                                    <th>Créé le</th>
                                    <th>Modifié le</th>
                                    <th>Statut</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                ${pageProducts.map(product => {
                                    const prices =
                                        product.prices || [];
                                    const price =
                                        prices[0] || null;
                                    const amount =
                                        price?.unit_amount != null
                                            ? (
                                                price.unit_amount / 100
                                            ).toLocaleString(
                                                "fr-FR",
                                                {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                }
                                            )
                                            : "—";
                                    const currency =
                                        price?.currency
                                            ? price.currency.toUpperCase()
                                            : "";
                                    let recurringText = "—";
                                    if (
                                        price?.recurring
                                    ) {
                                        const interval =
                                            price.recurring.interval;
                                        const count =
                                            price.recurring.interval_count || 1;
                                        if (count === 1) {
                                            recurringText =
                                                interval === "month"
                                                    ? "Mensuel"
                                                    : interval === "year"
                                                        ? "Annuel"
                                                        : interval === "week"
                                                            ? "Hebdomadaire"
                                                            : interval === "day"
                                                                ? "Quotidien"
                                                                : interval;
                                        } else {
                                            const unitPlural =
                                                interval === "month"
                                                    ? "mois"
                                                    : interval === "year"
                                                        ? "ans"
                                                        : interval === "week"
                                                            ? "semaines"
                                                            : interval === "day"
                                                                ? "jours"
                                                                : interval;
                                            recurringText =
                                                `Tous les ${count} ${unitPlural}`;
                                        }
                                    }
                                    return `
                                        <tr>
                                            <td>
                                                <div
                                                    class="d-flex align-items-center gap-3"
                                                >
                                                    <div class="avatar">
                                                        ${
                                                            product.name
                                                                ? product.name
                                                                    .split(" ")
                                                                    .map(
                                                                        part =>
                                                                            part[0]
                                                                    )
                                                                    .join("")
                                                                    .slice(0, 2)
                                                                    .toUpperCase()
                                                                : "—"
                                                        }
                                                    </div>
                                                    <div>
                                                        <div>
                                                            ${
                                                                product.name ||
                                                                "Produit sans nom"
                                                            }
                                                        </div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td>
                                                ${
                                                    product.description ||
                                                    "—"
                                                }
                                            </td>
                                            <td>
                                                <span class="amount-cell">
                                                    ${amount}
                                                </span>
                                                ${
                                                    currency
                                                        ? `
                                                            <span class="amount-currency">
                                                                ${currency}
                                                            </span>
                                                        `
                                                        : ""
                                                }
                                            </td>
                                            <td>
                                                ${
                                                    price?.type === "one_time"
                                                        ? "Paiement unique"
                                                        : price?.type === "recurring"
                                                            ? "Paiement récurrent"
                                                            : "—"
                                                }
                                            </td>
                                            <td>
                                                ${recurringText}
                                            </td>
                                            <td>
                                                ${formatDate(product.created)}
                                            </td>
                                            <td>
                                                ${formatDate(product.updated)}
                                            </td>
                                            <td>
                                                <span
                                                    class="${
                                                        product.active
                                                            ? "status-badge status-success"
                                                            : "status-badge status-danger"
                                                    }"
                                                >
                                                    ${
                                                        product.active
                                                            ? "Actif"
                                                            : "Inactif"
                                                    }
                                                </span>
                                            </td>
                                            <td>
                                                <div
                                                    class="row-menu"
                                                    data-product-id="${product.id}"
                                                >
                                                    <button
                                                        type="button"
                                                        class="row-menu-trigger"
                                                        aria-label="Actions"
                                                        aria-haspopup="true"
                                                    >
                                                        •••
                                                    </button>
                                                    <div class="row-menu-dropdown">
                                                        <button
                                                            type="button"
                                                            class="row-menu-item"
                                                            data-row-action="details"
                                                        >
                                                            Détails
                                                        </button>
                                                        <button
                                                            type="button"
                                                            class="row-menu-item row-menu-item-danger"
                                                            data-row-action="archive"
                                                        >
                                                            ${
                                                                product.active
                                                                    ? "Désactiver"
                                                                    : "Activer"
                                                            }
                                                        </button>
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    `;
                                }).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="d-flex justify-content-between align-items-center mt-3">
                    <span id="products-pagination-info" class="text-muted">Page ${productsPageNumber}</span>
                    <div class="d-flex gap-2">
                        <button id="products-prev-page" type="button" class="pagination-nav-btn" ${productsPageNumber <= 1 ? "disabled" : ""}><i class="bi bi-chevron-left"></i></button>
                        <button id="products-next-page" type="button" class="pagination-nav-btn" ${productsPageStart + productsPageSize >= filteredProducts.length ? "disabled" : ""}><i class="bi bi-chevron-right"></i></button>
                    </div>
                </div>
            `;

            list.querySelector("#products-prev-page")?.addEventListener("click", () => {
                if (productsPageNumber <= 1) return;
                productsPageNumber--;
                renderTable(filter, { resetPage: false });
            });
            list.querySelector("#products-next-page")?.addEventListener("click", () => {
                if (productsPageStart + productsPageSize >= filteredProducts.length) return;
                productsPageNumber++;
                renderTable(filter, { resetPage: false });
            });

            /* =================================================
               MENU D'ACTIONS PAR LIGNE (•••)
            ================================================= */

            list
                .querySelectorAll(".row-menu-trigger")
                .forEach(trigger => {

                    trigger.addEventListener("click", (event) => {

                        event.stopPropagation();

                        if (trigger.closest(".row-menu").classList.contains("open")) {
                            closeRowMenu();
                        } else {
                            openRowMenu(trigger);
                        }

                    });

                });

            list
                .querySelectorAll("[data-row-action]")
                .forEach(item => {

                    item.addEventListener("click", () => {

                        const row = item.closest(".row-menu");
                        closeRowMenu();

                        const product =
                            products.find(
                                p => p.id === row.dataset.productId
                            );

                        if (!product) return;

                        if (item.dataset.rowAction === "details") {
                            showProductDetails(product);
                        } else if (item.dataset.rowAction === "archive") {
                            toggleProductArchive(product);
                        }

                    });

                });

            }

            /* =================================================
               KPI — Tout / Actifs / Archivés
            ================================================= */

            renderCommerceKpis(
                summaryEl,
                [
                    { filter: "all", label: "Tout", count: products.length },
                    {
                        filter: "active",
                        label: "Actifs",
                        count: products.filter(p => p.active).length
                    },
                    {
                        filter: "archived",
                        label: "Archivés",
                        count: products.filter(p => !p.active).length
                    },
                ],
                "all",
                renderTable
            );

            renderTable("all");

        } catch (error) {

            console.error(
                "Erreur récupération Products Stripe :",
                error
            );


            list.innerHTML = `

                <div class="commerce-card">

                    <p>
                        ${
                            error.message ||
                            "Erreur lors du chargement des produits"
                        }
                    </p>

                </div>

            `;

        }

    }


    /* =====================================================
       DÉTAILS PRODUIT
    ===================================================== */

    function showProductDetails(product) {

        container.querySelector(
            "#product-details-subtitle"
        ).textContent =
            product.name || product.id;


        const prices =
            product.prices || [];


        container.querySelector(
            "#product-details-content"
        ).innerHTML = `

            <div class="customer-profile">

                <div class="customer-profile-avatar">

                    ${
                        product.name
                            ? product.name
                                .split(" ")
                                .map(part => part[0])
                                .join("")
                                .slice(0, 2)
                                .toUpperCase()
                            : "—"
                    }

                </div>


                <div>

                    <h4>
                        ${product.name || "Produit sans nom"}
                    </h4>

                    <code>
                        ${product.id}
                    </code>

                </div>

            </div>


            <div class="customer-details-grid">

                <div class="customer-detail-item">

                    <span>Nom</span>

                    <strong>
                        ${product.name || "—"}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>ID produit</span>

                    <strong>
                        ${product.id || "—"}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Description</span>

                    <strong>
                        ${product.description || "—"}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Type</span>

                    <strong>
                        ${product.type || "—"}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Statut</span>

                    <strong>
                        ${product.active ? "Actif" : "Inactif"}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Créé le</span>

                    <strong>
                        ${formatDate(product.created)}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Modifié le</span>

                    <strong>
                        ${formatDate(product.updated)}
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Tax code</span>

                    <strong>
                        ${product.tax_code || "—"}
                    </strong>

                </div>

            </div>


            ${
                prices.length
                    ? `

                        <div style="margin-top:20px;">

                            <h4>
                                Tarifs
                            </h4>

                            <div class="customer-details-grid">

                                ${prices.map(price => `

                                    <div class="customer-detail-item">

                                        <span>
                                            Price ID
                                        </span>

                                        <strong>
                                            ${price.id}
                                        </strong>

                                    </div>


                                    <div class="customer-detail-item">

                                        <span>
                                            Prix
                                        </span>

                                        <strong>

                                            ${
                                                price.unit_amount != null
                                                    ? `${(
                                                        price.unit_amount / 100
                                                    ).toLocaleString(
                                                        "fr-FR",
                                                        {
                                                            minimumFractionDigits: 2,
                                                            maximumFractionDigits: 2
                                                        }
                                                    )} ${(
                                                        price.currency || ""
                                                    ).toUpperCase()}`
                                                    : "—"
                                            }

                                        </strong>

                                    </div>


                                    <div class="customer-detail-item">

                                        <span>
                                            Type
                                        </span>

                                        <strong>
                                            ${price.type || "—"}
                                        </strong>

                                    </div>


                                    <div class="customer-detail-item">
                                        <span>
                                            Récurrence
                                        </span>
                                        <strong>
                                            ${
                                                !price.recurring
                                                    ? "Aucune"
                                                    : price.recurring.interval === "month"
                                                        ? (price.recurring.interval_count || 1) === 1
                                                            ? "Tous les mois"
                                                            : `Tous les ${price.recurring.interval_count} mois`
                                                        : price.recurring.interval === "year"
                                                            ? (price.recurring.interval_count || 1) === 1
                                                                ? "Tous les ans"
                                                                : `Tous les ${price.recurring.interval_count} ans`
                                                            : price.recurring.interval === "week"
                                                                ? (price.recurring.interval_count || 1) === 1
                                                                    ? "Toutes les semaines"
                                                                    : `Toutes les ${price.recurring.interval_count} semaines`
                                                                : price.recurring.interval === "day"
                                                                    ? (price.recurring.interval_count || 1) === 1
                                                                        ? "Tous les jours"
                                                                        : `Tous les ${price.recurring.interval_count} jours`
                                                                    : price.recurring.interval
                                            }
                                        </strong>
                                    </div>

                                `).join("")}

                            </div>

                        </div>

                    `
                    : `
                        <div style="margin-top:20px;">
                            <p>
                                Aucun tarif associé.
                            </p>
                        </div>
                    `
            }

            ${renderMetadataSection(product.metadata, "Produit")}

        `;

        detailsModal.classList.add("open");

    }

    /* =====================================================
       ACTIVER / DÉSACTIVER UN PRODUIT
       (appelé depuis le menu ••• de la ligne, voir plus bas)
    ===================================================== */

    async function toggleProductArchive(product) {

        const isActive = product.active;
        const endpoint = isActive ? "archive" : "unarchive";

        try {
            const response = await apiFetch(
                `/stripe/connect/products/${product.id}/${endpoint}`,
                { method: "POST" }
            );
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de mettre à jour le produit"
                );
            }

            showToast(
                isActive
                    ? "Produit désactivé"
                    : "Produit réactivé",
                "success"
            );

            await loadProducts();

        } catch (error) {
            showToast(
                error.message ||
                "Erreur lors de la mise à jour du produit",
                "error"
            );
        }
    }


    /* =====================================================
       CRÉATION PRODUIT
    ===================================================== */

    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const name =
                container
                    .querySelector("#product-name")
                    .value
                    .trim();


            const description =
                container
                    .querySelector("#product-description")
                    .value
                    .trim();


            const unit_amount =
                Math.round(
                    Number(
                        container
                            .querySelector("#product-amount")
                            .value
                        ) * 100
                    );
            const currency =
                container
                    .querySelector("#product-currency")
                    .value;


            const isRecurring =
                recurring.checked;


            const interval =
                container
                    .querySelector("#product-interval")
                    .value;

            const intervalCount =
                Number(
                    container
                        .querySelector("#product-interval-count")
                        .value
                ) || 1;


            try {

                const response =
                    await apiFetch(
                        "/stripe/connect/products",
                        {
                            method: "POST",

                            body: {
                                name,
                                description:
                                    description || null,
                                unit_amount,
                                currency,
                                recurring:
                                    isRecurring,
                                interval:
                                    isRecurring
                                        ? interval
                                        : null,
                                interval_count:
                                    isRecurring
                                        ? intervalCount
                                        : 1
                            }
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        "Impossible de créer le produit"
                    );

                }


                showToast(
                    "Produit créé avec succès",
                    "success"
                );


                form.reset();

                intervalContainer.style.display =
                    "none";

                createModal.classList.remove(
                    "open"
                );


                /*
                 * On recharge depuis Stripe.
                 * Le frontend ne construit pas lui-même
                 * le produit créé.
                 */

                await loadProducts();


            } catch (error) {

                console.error(error);


                showToast(
                    error.message ||
                    "Erreur lors de la création du produit",
                    "error"
                );

            }

        }
    );


    /* =====================================================
       CHARGEMENT INITIAL
    ===================================================== */

    await loadProducts();

}
/* =========================================================
   ABONNEMENTS
========================================================= */

async function renderSubscriptions(container) {

    container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-solid fa-repeat"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Abonnements</h1>
                        <p>La facturation récurrente automatisée : définissez un cycle (mensuel, annuel...) et Xepay prélève vos clients à chaque échéance, sans intervention de votre part.</p>
                    </div>
                </div>

                <button
                    type="button"
                    class="create-client-btn"
                    id="open-create-subscription-modal"
                >
                    + Créer un abonnement
                </button>
            </div>

            <!-- KPI : ZONE INDÉPENDANTE DU TABLEAU -->
            <div id="subscriptions-summary"></div>
        </div>

        <div id="subscriptions-list"></div>

        <!-- =================================================
             MODAL CRÉATION ABONNEMENT
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="create-subscription-modal"
        >

            <div class="customer-modal">

                <div class="customer-modal-header">

                    <div>
                        <h3>Créer un abonnement</h3>

                        <p>
                            Créez un abonnement pour l'un de vos clients.
                        </p>
                    </div>

                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-create-subscription"
                    >
                        ×
                    </button>

                </div>

                <form id="create-subscription-form">

                    <div class="form-group">

                        <label>Client</label>

                        <select
                            id="subscription-customer"
                            required
                        >
                            <option value="">
                                Chargement des clients...
                            </option>
                        </select>

                    </div>

                    <div class="form-group">

                        <label>Tarif</label>

                        <select
                            id="subscription-price"
                            required
                        >
                            <option value="">
                                Chargement des tarifs...
                            </option>
                        </select>

                    </div>

                    <div class="form-group">

                        <label>Quantité</label>

                        <input
                            type="number"
                            id="subscription-quantity"
                            value="1"
                            min="1"
                            required
                        >

                    </div>

                    <div class="customer-modal-actions">

                        <button
                            type="button"
                            class="modal-cancel-btn"
                            id="cancel-create-subscription"
                        >
                            Annuler
                        </button>

                        <button
                            type="submit"
                            id="create-subscription-btn"
                            class="modal-submit-btn"
                        >
                            Créer l'abonnement
                        </button>

                    </div>

                </form>

            </div>

        </div>

        <!-- =================================================
             MODAL DÉTAILS ABONNEMENT
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="subscription-details-modal"
        >

            <div class="customer-modal customer-details-modal">

                <div class="customer-modal-header">

                    <div>
                        <h3>Détails de l'abonnement</h3>
                        <p id="subscription-details-subtitle"></p>
                    </div>

                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-subscription-details"
                    >
                        ×
                    </button>

                </div>

                <div id="subscription-details-content"></div>

            </div>

        </div>

        <!-- =================================================
             MODAL CHANGER LA QUANTITÉ
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="subscription-quantity-modal"
        >
            <div class="customer-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3>Changer la quantité</h3>
                        <p>Nouvelle quantité pour cet abonnement.</p>
                    </div>
                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-subscription-quantity"
                    >
                        ×
                    </button>
                </div>
                <form id="subscription-quantity-form">
                    <div class="form-group">
                        <label for="subscription-quantity-input">
                            Quantité
                        </label>
                        <input
                            type="number"
                            id="subscription-quantity-input"
                            min="1"
                            value="1"
                            required
                        >
                    </div>
                    <div class="customer-modal-actions">
                        <button
                            type="button"
                            class="modal-cancel-btn"
                            id="cancel-subscription-quantity"
                        >
                            Annuler
                        </button>
                        <button
                            type="submit"
                            class="modal-submit-btn"
                        >
                            Enregistrer
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;


    /* =====================================================
       ÉLÉMENTS
    ===================================================== */

    const form =
        container.querySelector(
            "#create-subscription-form"
        );

    const customerSelect =
        container.querySelector(
            "#subscription-customer"
        );

    const priceSelect =
        container.querySelector(
            "#subscription-price"
        );

    const quantityInput =
        container.querySelector(
            "#subscription-quantity"
        );

    const createModal =
        container.querySelector(
            "#create-subscription-modal"
        );

    const detailsModal =
        container.querySelector(
            "#subscription-details-modal"
        );

    // Détails abonnement -> tiroir latéral droit (voir shared/detailsDrawer.js),
    // même gabarit que Clients/Produits.
    initDetailsDrawer(
        detailsModal,
        detailsModal.querySelector(".customer-modal")
    );

    container
        .querySelector("#close-subscription-details")
        .addEventListener("click", () => {
            detailsModal.classList.remove("open");
        });

    function showSubscriptionDetails(subscription) {

        const item = subscription.items?.data?.[0];
        const price = item?.price;

        const amount =
            price?.unit_amount != null
                ? `${(price.unit_amount / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${(price.currency || "").toUpperCase()}`
                : "—";

        const statusLabels = {
            active: "Actif",
            trialing: "Essai",
            past_due: "En retard",
            canceled: "Annulé",
            incomplete: "Incomplet",
            incomplete_expired: "Incomplet (expiré)",
            unpaid: "Impayé",
            paused: "En pause",
        };

        container.querySelector("#subscription-details-subtitle").textContent =
            subscription.id;

        container.querySelector("#subscription-details-content").innerHTML = `
            <div class="customer-details-grid">

                <div class="customer-detail-item">
                    <span>ID abonnement</span>
                    <strong>${subscription.id}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Client</span>
                    <strong>${subscription.customer || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Montant</span>
                    <strong>${amount}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Statut</span>
                    <strong>${statusLabels[subscription.status] || subscription.status || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Mode de paiement</span>
                    <strong>
                        ${
                            subscription.collection_method === "charge_automatically"
                                ? "Prélèvement automatique"
                                : subscription.collection_method === "send_invoice"
                                    ? "Facturation sur facture"
                                    : subscription.collection_method || "—"
                        }
                    </strong>
                </div>

                <div class="customer-detail-item">
                    <span>Quantité</span>
                    <strong>${item?.quantity ?? "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Début</span>
                    <strong>${formatDate(subscription.start_date)}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Prochaine échéance</span>
                    <strong>${formatDate(item?.current_period_end)}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Créé le</span>
                    <strong>${formatDate(subscription.created)}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Annulation prévue</span>
                    <strong>${subscription.cancel_at_period_end ? "Oui" : "Non"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Annulé le</span>
                    <strong>${formatDate(subscription.canceled_at)}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Facture Stripe</span>
                    <strong>${subscription.latest_invoice || "—"}</strong>
                </div>

            </div>

            ${renderMetadataSection(subscription.metadata, "Abonnement")}
        `;

        detailsModal.classList.add("open");
    }


    /* =====================================================
       OUVERTURE / FERMETURE MODAL
    ===================================================== */

    container
        .querySelector(
            "#open-create-subscription-modal"
        )
        .addEventListener("click", () => {

            createModal.classList.add("open");

        });


    container
        .querySelector(
            "#close-create-subscription"
        )
        .addEventListener("click", () => {

            createModal.classList.remove("open");

        });


    container
        .querySelector(
            "#cancel-create-subscription"
        )
        .addEventListener("click", () => {

            createModal.classList.remove("open");

        });


    const quantityModal =
        container.querySelector("#subscription-quantity-modal");
    const quantityForm =
        container.querySelector("#subscription-quantity-form");
    const changeQuantityInput =
        container.querySelector("#subscription-quantity-input");

    // Abonnement actuellement visé par le modal "Changer la quantité"
    // (posé au clic sur le menu ••• de la ligne, voir plus bas).
    let quantitySubscriptionId = null;

    [createModal, detailsModal, quantityModal].forEach(modal => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.classList.remove("open");
            }
        });
    });

    container
        .querySelector("#close-subscription-quantity")
        .addEventListener("click", () => {
            quantityModal.classList.remove("open");
        });

    container
        .querySelector("#cancel-subscription-quantity")
        .addEventListener("click", () => {
            quantityModal.classList.remove("open");
        });

    function openQuantityModal(subscription) {
        quantitySubscriptionId = subscription.id;
        changeQuantityInput.value =
            subscription.items?.data?.[0]?.quantity || 1;
        quantityModal.classList.add("open");
    }

    quantityForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const newQuantity = Number(changeQuantityInput.value);

        try {
            const response = await apiFetch(
                `/stripe/connect/subscriptions/${quantitySubscriptionId}/quantity`,
                {
                    method: "POST",
                    body: { quantity: newQuantity }
                }
            );
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de modifier la quantité"
                );
            }

            showToast("Quantité mise à jour", "success");

            quantityModal.classList.remove("open");

            await loadSubscriptions();

        } catch (error) {
            console.error(error);
            showToast(
                error.message ||
                "Erreur lors de la modification de la quantité",
                "error"
            );
        }
    });

    async function cancelSubscription(subscription) {
        if (!confirm(
            "Confirmer l'annulation de cet abonnement ? Cette action est immédiate et irréversible."
        )) return;

        try {
            const response = await apiFetch(
                `/stripe/connect/subscriptions/${subscription.id}/cancel`,
                { method: "POST" }
            );
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible d'annuler l'abonnement"
                );
            }

            showToast("Abonnement annulé", "success");

            await loadSubscriptions();

        } catch (error) {
            console.error(error);
            showToast(
                error.message ||
                "Erreur lors de l'annulation de l'abonnement",
                "error"
            );
        }
    }

    /* =====================================================
       CHARGER CLIENTS + TARIFS
    ===================================================== */

    async function loadFormData() {

        try {

            const [
                customersResponse,
                productsResponse
            ] = await Promise.all([

                apiFetch(
                    "/stripe/connect/customers"
                ),

                apiFetch(
                    "/stripe/connect/products"
                )

            ]);


            const customersData =
                await customersResponse.json();

            const productsData =
                await productsResponse.json();


            if (!customersResponse.ok) {

                throw new Error(
                    customersData.detail ||
                    "Impossible de récupérer les clients"
                );

            }


            if (!productsResponse.ok) {

                throw new Error(
                    productsData.detail ||
                    "Impossible de récupérer les produits"
                );

            }


            const customers =
                customersData.data || [];

            const products =
                productsData.data || [];


            /* =============================================
               CLIENTS
            ============================================= */

            customerSelect.innerHTML = `
                <option value="">
                    Sélectionner un client
                </option>

                ${customers.map(customer => `

                    <option value="${customer.id}">

                        ${
                            customer.name ||
                            customer.email ||
                            customer.id
                        }

                        ${
                            customer.email
                                ? ` — ${customer.email}`
                                : ""
                        }

                    </option>

                `).join("")}
            `;


            /* =============================================
               TARIFS RÉCURRENTS
            ============================================= */

            const recurringPrices = [];


            products.forEach(product => {

                const prices =
                    product.prices || [];


                prices.forEach(price => {

                    if (
                        price.active !== false &&
                        price.type === "recurring" &&
                        price.recurring
                    ) {

                        recurringPrices.push({
                            product,
                            price
                        });

                    }

                });

            });


            priceSelect.innerHTML = `
                <option value="">
                    Sélectionner un tarif
                </option>

                ${recurringPrices.map(item => {

                    const product =
                        item.product;

                    const price =
                        item.price;


                    const amount =
                        price.unit_amount != null
                            ? (
                                price.unit_amount / 100
                            ).toLocaleString(
                                "fr-FR",
                                {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                }
                            )
                            : "—";


                    const currency =
                        (
                            price.currency || ""
                        ).toUpperCase();


                    const interval =
                        price.recurring.interval;


                    const intervalCount =
                        price.recurring.interval_count || 1;


                    let recurringText =
                        interval;


                    if (
                        intervalCount === 1
                    ) {

                        recurringText =
                            interval === "month"
                                ? "Mensuel"
                                : interval === "year"
                                    ? "Annuel"
                                    : interval === "week"
                                        ? "Hebdomadaire"
                                        : interval === "day"
                                            ? "Quotidien"
                                            : interval;

                    } else {

                        const unitPlural =
                            interval === "month"
                                ? "mois"
                                : interval === "year"
                                    ? "ans"
                                    : interval === "week"
                                        ? "semaines"
                                        : interval === "day"
                                            ? "jours"
                                            : interval;

                        recurringText =
                            `Tous les ${intervalCount} ${unitPlural}`;

                    }


                    return `

                        <option value="${price.id}">

                            ${product.name || "Produit"}

                            — ${amount} ${currency}

                            — ${recurringText}

                        </option>

                    `;

                }).join("")}
            `;


        } catch (error) {

            console.error(
                "Erreur chargement formulaire abonnement :",
                error
            );


            customerSelect.innerHTML = `
                <option value="">
                    Impossible de charger les clients
                </option>
            `;


            priceSelect.innerHTML = `
                <option value="">
                    Impossible de charger les tarifs
                </option>
            `;


            showToast(
                error.message ||
                "Impossible de charger les données",
                "error"
            );

        }

    }


    /* =====================================================
       CHARGER LES ABONNEMENTS
    ===================================================== */

    async function loadSubscriptions() {

        closeRowMenu();

        const list =
            container.querySelector(
                "#subscriptions-list"
            );


        list.innerHTML = `
            <div class="commerce-card">
                <p>Chargement des abonnements...</p>
            </div>
        `;


        try {
            const response =
                await apiFetch(
                    "/stripe/connect/subscriptions"
                );
            const data = await response.json();
            if (!response.ok) {
                throw new Error(
                    response.status === 401
                        ? "Votre session a expiré. Veuillez vous reconnecter."
                        : data.detail || "Impossible de récupérer les abonnements"
                );
            }
            const customersResponse =
                await apiFetch(
                    "/stripe/connect/customers"
                );
            const customersData = await customersResponse.json();
            if (!customersResponse.ok) {

                throw new Error(
                    customersData.detail ||
                    "Impossible de récupérer les clients"
                );

            }
            const customers =
                customersData.data || [];

            const subscriptions =
                data.data || [];


            console.log(
                "SUBSCRIPTION LIST:",
                subscriptions
            );


            const summaryEl = container.querySelector("#subscriptions-summary");

            // Mapping des 6 KPI sur les statuts Stripe réels (status="all"
            // côté backend, sinon les annulés ne seraient même pas
            // remontés) : Planifiés = essai (trialing), En attente =
            // paiement initial pas encore confirmé (incomplete), Fictifs =
            // jamais finalisés et expirés (incomplete_expired).
            function matchesSubscriptionFilter(subscription, filter) {
                switch (filter) {
                    case "active": return subscription.status === "active";
                    case "trialing": return subscription.status === "trialing";
                    case "incomplete": return subscription.status === "incomplete";
                    case "canceled": return subscription.status === "canceled";
                    case "incomplete_expired": return subscription.status === "incomplete_expired";
                    default: return true;
                }
            }

            // Pagination 10 par 10 (Précédent/Suivant, même mécanisme que
            // Transactions) - purement côté client : la liste complète est
            // déjà en mémoire (subscriptions, récupérée en un seul appel
            // ci-dessus), donc les KPI par statut continuent de porter
            // sur l'ensemble réel.
            const subscriptionsPageSize = 10;
            let subscriptionsPageNumber = 1;

            function renderTable(filter = "all", { resetPage = true } = {}) {

                if (resetPage) subscriptionsPageNumber = 1;

                const filteredSubscriptions = subscriptions.filter(
                    subscription => matchesSubscriptionFilter(subscription, filter)
                );

                if (!filteredSubscriptions.length) {

                    list.innerHTML = `
                        <div class="commerce-card">

                            <p>
                                Aucun abonnement dans cette catégorie.
                            </p>

                        </div>
                    `;

                    return;

                }

            const subscriptionsPageStart = (subscriptionsPageNumber - 1) * subscriptionsPageSize;
            const pageSubscriptions = filteredSubscriptions.slice(subscriptionsPageStart, subscriptionsPageStart + subscriptionsPageSize);

            list.innerHTML = `

                <div class="table-wrap">

                    <div
                        class="d-flex justify-content-between align-items-center mb-3"
                    >

                        <div>

                            <div class="table-title">
                                Abonnements
                            </div>

                            <div class="page-subtitle">

                                ${filteredSubscriptions.length}
                                abonnement(s)

                            </div>

                        </div>

                    </div>


                    <div id="customers-scroll-box">

                        <table class="table">

                            <thead>

                                <tr>

                                    <th>Email du client</th>

                                    <th>Nom du client</th>

                                    <th>Produit</th>

                                    <th>Montant</th>

                                    <th>Fréquence</th>

                                    <th>Total mensuel</th>

                                    <th>Total annuel</th>

                                    <th>Mode de paiement</th>

                                    <th>Début</th>

                                    <th>Prochaine échéance</th>

                                    <th>Créé le</th>

                                    <th>Statut</th>

                                    <th></th>

                                </tr>

                            </thead>


                            <tbody>

                                ${pageSubscriptions.map(subscription => {

                                    const item =
                                        subscription.items?.data?.[0];


                                    const price =
                                        item?.price;


                                    const customer =
                                        customers.find(
                                            customer =>
                                                customer.id ===
                                                subscription.customer
                                        );


                                    const customerName =
                                        customer?.name || "—";


                                    const customerEmail =
                                        customer?.email || "—";


                                    const amount =
                                        price?.unit_amount != null
                                            ? (
                                                price.unit_amount / 100
                                            ).toLocaleString(
                                                "fr-FR",
                                                {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                }
                                            )
                                            : "—";


                                    const currency =
                                        price?.currency
                                            ? price.currency.toUpperCase()
                                            : "";


                                    const interval =
                                        price?.recurring?.interval;


                                    const intervalCount =
                                        price?.recurring?.interval_count || 1;


                                    let recurringText =
                                        "—";


                                    if (interval) {

                                        if (
                                            intervalCount === 1
                                        ) {

                                            recurringText =
                                                interval === "month"
                                                    ? "Mensuel"
                                                    : interval === "year"
                                                        ? "Annuel"
                                                        : interval === "week"
                                                            ? "Hebdomadaire"
                                                            : interval;

                                        } else {

                                            recurringText =
                                                `Tous les ${intervalCount} ${interval}`;

                                        }

                                    }


                                    // Total facturé par cycle (prix unitaire x quantité), ramené
                                    // à un total mensuel/annuel équivalent selon l'intervalle -
                                    // permet de comparer des abonnements à fréquences différentes.
                                    const quantity =
                                        item?.quantity || 1;

                                    const perCycleAmount =
                                        price?.unit_amount != null
                                            ? (price.unit_amount * quantity) / 100
                                            : null;

                                    let monthlyTotal = null;
                                    let annualTotal = null;

                                    if (perCycleAmount != null && interval) {
                                        const perUnitInterval =
                                            perCycleAmount / intervalCount;
                                        if (interval === "month") {
                                            monthlyTotal = perUnitInterval;
                                            annualTotal = perUnitInterval * 12;
                                        } else if (interval === "year") {
                                            annualTotal = perUnitInterval;
                                            monthlyTotal = perUnitInterval / 12;
                                        } else if (interval === "week") {
                                            monthlyTotal = perUnitInterval * (52 / 12);
                                            annualTotal = perUnitInterval * 52;
                                        } else if (interval === "day") {
                                            monthlyTotal = perUnitInterval * 30;
                                            annualTotal = perUnitInterval * 365;
                                        }
                                    }

                                    const formatSubscriptionAmount = (value) =>
                                        value != null
                                            ? `${value.toLocaleString("fr-FR", {
                                                minimumFractionDigits: 2,
                                                maximumFractionDigits: 2
                                            })} ${currency}`
                                            : "—";


                                    let statusClass =
                                        "status-warning";


                                    let statusText =
                                        subscription.status || "—";


                                    if (
                                        subscription.status ===
                                        "active"
                                    ) {

                                        statusClass =
                                            "status-success";

                                        statusText =
                                            "Actif";

                                    } else if (
                                        subscription.status ===
                                        "canceled"
                                    ) {

                                        statusClass =
                                            "status-danger";

                                        statusText =
                                            "Annulé";

                                    } else if (
                                        subscription.status ===
                                        "past_due"
                                    ) {

                                        statusClass =
                                            "status-danger";

                                        statusText =
                                            "Impayé";

                                    } else if (
                                        subscription.status ===
                                        "trialing"
                                    ) {

                                        statusClass =
                                            "status-success";

                                        statusText =
                                            "Essai";

                                    }


                                    return `

                                        <tr>

                                            <td>
                                                ${customerEmail}
                                            </td>


                                            <td>
                                                ${customerName}
                                            </td>


                                            <td>
                                                ${subscription.product_name || "—"}
                                            </td>


                                            <td>

                                                <span class="amount-cell">
                                                    ${amount}
                                                </span>

                                                ${
                                                    currency
                                                        ? `
                                                            <span class="amount-currency">
                                                                ${currency}
                                                            </span>
                                                        `
                                                        : ""
                                                }

                                            </td>


                                            <td>
                                                ${recurringText}
                                            </td>


                                            <td>
                                                ${formatSubscriptionAmount(monthlyTotal)}
                                            </td>


                                            <td>
                                                ${formatSubscriptionAmount(annualTotal)}
                                            </td>


                                            <td>

                                                ${
                                                    subscription.collection_method ===
                                                    "charge_automatically"

                                                        ? "Prélèvement automatique"

                                                        : subscription.collection_method ===
                                                          "send_invoice"

                                                            ? "Facturation sur facture"

                                                            : subscription.collection_method ||
                                                              "—"
                                                }

                                            </td>


                                            <td>

                                                ${formatDate(subscription.start_date)}

                                            </td>


                                            <td>

                                                ${formatDate(subscription.items?.data?.[0]?.current_period_end)}

                                            </td>


                                            <td>

                                                ${formatDate(subscription.created)}

                                            </td>

                                            <td>

                                                <span
                                                    class="status-badge ${statusClass}"
                                                >
                                                    ${statusText}
                                                </span>

                                            </td>

                                            <td>
                                                <div
                                                    class="row-menu"
                                                    data-subscription-id="${subscription.id}"
                                                >
                                                    <button
                                                        type="button"
                                                        class="row-menu-trigger"
                                                        aria-label="Actions"
                                                        aria-haspopup="true"
                                                    >
                                                        •••
                                                    </button>
                                                    <div class="row-menu-dropdown">
                                                        <button
                                                            type="button"
                                                            class="row-menu-item"
                                                            data-row-action="details"
                                                        >
                                                            Détails
                                                        </button>
                                                        ${
                                                            subscription.status !== "canceled"
                                                                ? `
                                                                    <button
                                                                        type="button"
                                                                        class="row-menu-item"
                                                                        data-row-action="quantity"
                                                                    >
                                                                        Changer la quantité
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        class="row-menu-item row-menu-item-danger"
                                                                        data-row-action="cancel"
                                                                    >
                                                                        Annuler
                                                                    </button>
                                                                `
                                                                : ""
                                                        }
                                                    </div>
                                                </div>
                                            </td>

                                        </tr>

                                    `;

                                }).join("")}

                            </tbody>

                        </table>

                    </div>

                </div>

                <div class="d-flex justify-content-between align-items-center mt-3">
                    <span id="subscriptions-pagination-info" class="text-muted">Page ${subscriptionsPageNumber}</span>
                    <div class="d-flex gap-2">
                        <button id="subscriptions-prev-page" type="button" class="pagination-nav-btn" ${subscriptionsPageNumber <= 1 ? "disabled" : ""}><i class="bi bi-chevron-left"></i></button>
                        <button id="subscriptions-next-page" type="button" class="pagination-nav-btn" ${subscriptionsPageStart + subscriptionsPageSize >= filteredSubscriptions.length ? "disabled" : ""}><i class="bi bi-chevron-right"></i></button>
                    </div>
                </div>

            `;

            list.querySelector("#subscriptions-prev-page")?.addEventListener("click", () => {
                if (subscriptionsPageNumber <= 1) return;
                subscriptionsPageNumber--;
                renderTable(filter, { resetPage: false });
            });
            list.querySelector("#subscriptions-next-page")?.addEventListener("click", () => {
                if (subscriptionsPageStart + subscriptionsPageSize >= filteredSubscriptions.length) return;
                subscriptionsPageNumber++;
                renderTable(filter, { resetPage: false });
            });

            /* =================================================
               MENU D'ACTIONS PAR LIGNE (•••)
            ================================================= */

            list
                .querySelectorAll(".row-menu-trigger")
                .forEach(trigger => {

                    trigger.addEventListener("click", (event) => {

                        event.stopPropagation();

                        if (trigger.closest(".row-menu").classList.contains("open")) {
                            closeRowMenu();
                        } else {
                            openRowMenu(trigger);
                        }

                    });

                });

            list
                .querySelectorAll("[data-row-action]")
                .forEach(item => {

                    item.addEventListener("click", () => {

                        const row = item.closest(".row-menu");
                        closeRowMenu();

                        const subscription = subscriptions.find(
                            s => s.id === row.dataset.subscriptionId
                        );

                        if (!subscription) return;

                        if (item.dataset.rowAction === "details") {
                            showSubscriptionDetails(subscription);
                        } else if (item.dataset.rowAction === "quantity") {
                            openQuantityModal(subscription);
                        } else if (item.dataset.rowAction === "cancel") {
                            cancelSubscription(subscription);
                        }
                    });
                });

            }

            /* =================================================
               KPI — Actifs / Planifiés / En attente / Annulés / Fictifs / Tout
            ================================================= */

            renderCommerceKpis(
                summaryEl,
                [
                    {
                        filter: "active",
                        label: "Actifs",
                        count: subscriptions.filter(s => matchesSubscriptionFilter(s, "active")).length
                    },
                    {
                        filter: "trialing",
                        label: "Planifiés",
                        count: subscriptions.filter(s => matchesSubscriptionFilter(s, "trialing")).length
                    },
                    {
                        filter: "incomplete",
                        label: "En attente",
                        count: subscriptions.filter(s => matchesSubscriptionFilter(s, "incomplete")).length
                    },
                    {
                        filter: "canceled",
                        label: "Annulés",
                        count: subscriptions.filter(s => matchesSubscriptionFilter(s, "canceled")).length
                    },
                    {
                        filter: "incomplete_expired",
                        label: "Fictifs",
                        count: subscriptions.filter(s => matchesSubscriptionFilter(s, "incomplete_expired")).length
                    },
                    { filter: "all", label: "Tout", count: subscriptions.length },
                ],
                "all",
                renderTable
            );

            renderTable("all");

        } catch (error) {

            console.error(
                "Erreur récupération abonnements Stripe :",
                error
            );


            list.innerHTML = `

                <div class="commerce-card">

                    <p>

                        ${
                            error.message ||
                            "Erreur lors du chargement des abonnements"
                        }

                    </p>

                </div>

            `;

        }

    }


    /* =====================================================
       CRÉATION DE L'ABONNEMENT
    ===================================================== */

    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const customer_id =
                customerSelect.value;


            const price_id =
                priceSelect.value;


            const quantity =
                Number(
                    quantityInput.value
                );


            if (
                !customer_id ||
                !price_id
            ) {

                showToast(
                    "Sélectionnez un client et un tarif.",
                    "error"
                );

                return;

            }


            const submitButton =
                container.querySelector(
                    "#create-subscription-btn"
                );


            submitButton.disabled = true;

            submitButton.textContent =
                "Création du lien...";


            try {

                const response =
                    await apiFetch(
                        "/stripe/connect/subscriptions",
                        {
                            method: "POST",

                            body: {
                                customer_id,
                                price_id,
                                quantity,
                                collection_method:
                                    "charge_automatically"
                            }
                        }
                    );


                const data =
                    await response.json();


                console.log(
                    "SUBSCRIPTION CREATE STATUS:",
                    response.status
                );


                console.log(
                    "SUBSCRIPTION CREATE RESPONSE:",
                    data
                );


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        "Impossible de créer le lien d'abonnement"
                    );

                }


                const checkoutUrl =
                    data.url;


                if (!checkoutUrl) {

                    throw new Error(
                        "URL Stripe Checkout introuvable"
                    );

                }


                form.reset();

                createModal.classList.remove(
                    "open"
                );


                /*
                 * Recharge la liste AVANT d'ajouter
                 * le lien afin que loadSubscriptions()
                 * ne l'efface pas.
                 */
                await loadSubscriptions();


                const list =
                    container.querySelector(
                        "#subscriptions-list"
                    );


                list.insertAdjacentHTML(
                    "afterbegin",
                    `
                        <div
                            class="commerce-card subscription-checkout-link"
                        >

                            <div>

                                <strong>
                                    Lien de paiement du client
                                </strong>

                                <p>
                                    Envoyez ce lien à votre client
                                    pour qu'il renseigne son moyen
                                    de paiement.
                                </p>

                                <input
                                    type="text"
                                    value="${checkoutUrl}"
                                    readonly
                                    class="form-control"
                                    id="subscription-checkout-url"
                                >

                            </div>

                            <button
                                type="button"
                                class="modal-submit-btn"
                                id="copy-subscription-checkout-url"
                            >
                                Copier le lien
                            </button>

                        </div>
                    `
                );


                container
                    .querySelector(
                        "#copy-subscription-checkout-url"
                    )
                    .addEventListener(
                        "click",
                        async () => {

                            try {

                                await navigator.clipboard.writeText(
                                    checkoutUrl
                                );

                                showToast(
                                    "Lien Stripe copié.",
                                    "success"
                                );

                            } catch (error) {

                                console.error(
                                    "Erreur copie lien Stripe :",
                                    error
                                );

                                showToast(
                                    "Impossible de copier le lien.",
                                    "error"
                                );

                            }

                        }
                    );


                showToast(
                    "Le lien Stripe est prêt à être envoyé au client.",
                    "success"
                );


            } catch (error) {

                console.error(
                    "Erreur création abonnement :",
                    error
                );


                showToast(
                    error.message ||
                    "Erreur lors de la création du lien d'abonnement",
                    "error"
                );


            } finally {

                submitButton.disabled = false;

                submitButton.textContent =
                    "Créer l'abonnement";

            }

        }
    );


    /* =====================================================
       INITIALISATION
    ===================================================== */

    await Promise.all([

        loadFormData(),

        loadSubscriptions()

    ]);

}
/* =========================================================
   FACTURES
========================================================= */

async function renderInvoices(container) {

      container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-solid fa-file-invoice"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Factures</h1>
                        <p>Pour une prestation ponctuelle facturée formellement : devis accepté, mission freelance, vente B2B. Un document professionnel envoyé au client, payable en un clic.</p>
                    </div>
                </div>
                <button
                    type="button"
                    class="create-client-btn"
                    id="open-create-invoice-modal"
                >
                    + Créer une facture
                </button>
            </div>
            <!-- KPI : ZONE INDÉPENDANTE DU TABLEAU -->
            <div id="invoices-summary"></div>
        </div>
        <div id="invoices-list"></div>
        <!-- MODAL CRÉATION FACTURE -->
        <div
            class="customer-modal-overlay"
            id="create-invoice-modal"
        >
            <div class="customer-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3>Créer une facture</h3>
                        <p>
                            Créez une facture pour l'un de vos clients.
                        </p>
                    </div>
                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-create-invoice"
                    >
                        ×
                    </button>
                </div>
                <form id="create-invoice-form">
                    <div class="form-group">
                        <label>Client</label>
                        <select
                            id="invoice-customer"
                            required
                        >
                            <option value="">
                                Chargement des clients...
                            </option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Tarif</label>
                        <select
                            id="invoice-price"
                            required
                        >
                            <option value="">
                                Chargement des tarifs...
                            </option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Quantité</label>
                        <input
                            type="number"
                            id="invoice-quantity"
                            value="1"
                            min="1"
                            required
                        >
                    </div>
                    <div class="form-group">
                        <label>Délai de paiement</label>
                        <input
                            type="number"
                            id="invoice-days"
                            value="7"
                            min="0"
                            required
                        >
                    </div>
                    <div class="customer-modal-actions">
                        <button
                            type="button"
                            class="modal-cancel-btn"
                            id="cancel-create-invoice"
                        >
                            Annuler
                        </button>
                        <button
                            type="submit"
                            id="create-invoice-btn"
                            class="modal-submit-btn"
                        >
                            Créer la facture
                        </button>
                    </div>
                </form>
            </div>
        </div>

        <!-- =================================================
             MODAL DÉTAILS FACTURE
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="invoice-details-modal"
        >
            <div class="customer-modal customer-details-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3>Détails de la facture</h3>
                        <p id="invoice-details-subtitle"></p>
                    </div>
                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-invoice-details"
                    >
                        ×
                    </button>
                </div>
                <div id="invoice-details-content"></div>
            </div>
        </div>

        <!-- =================================================
             MODAL MODIFIER L'ÉCHÉANCE
        ================================================== -->

        <div
            class="customer-modal-overlay"
            id="invoice-edit-modal"
        >
            <div class="customer-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3>Modifier la facture</h3>
                        <p>Nouvelle échéance pour cette facture.</p>
                    </div>
                    <button
                        type="button"
                        class="customer-modal-close"
                        id="close-invoice-edit"
                    >
                        ×
                    </button>
                </div>
                <form id="invoice-edit-form">
                    <div class="form-group">
                        <label for="invoice-edit-days">
                            Jours avant échéance (à partir d'aujourd'hui)
                        </label>
                        <input
                            type="number"
                            id="invoice-edit-days"
                            min="0"
                            value="7"
                            required
                        >
                    </div>
                    <div class="customer-modal-actions">
                        <button
                            type="button"
                            class="modal-cancel-btn"
                            id="cancel-invoice-edit"
                        >
                            Annuler
                        </button>
                        <button
                            type="submit"
                            class="modal-submit-btn"
                        >
                            Enregistrer
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    const form =
        container.querySelector(
            "#create-invoice-form"
        );


    const customerSelect =
        container.querySelector(
            "#invoice-customer"
        );


    const priceSelect =
        container.querySelector(
            "#invoice-price"
        );
    const createModal =
        container.querySelector(
            "#create-invoice-modal"
        );

    const detailsModal =
        container.querySelector(
            "#invoice-details-modal"
        );

    // Détails facture -> tiroir latéral droit (voir shared/detailsDrawer.js),
    // même gabarit que Clients/Produits/Abonnements.
    initDetailsDrawer(
        detailsModal,
        detailsModal.querySelector(".customer-modal")
    );

    container
        .querySelector("#close-invoice-details")
        .addEventListener("click", () => {
            detailsModal.classList.remove("open");
        });

    container
        .querySelector("#open-create-invoice-modal")
        .addEventListener("click", () => {
            createModal.classList.add("open");
        });
    container
        .querySelector("#close-create-invoice")
        .addEventListener("click", () => {
            createModal.classList.remove("open");
        });
    container
        .querySelector("#cancel-create-invoice")
        .addEventListener("click", () => {
            createModal.classList.remove("open");
        });

    const editModal =
        container.querySelector("#invoice-edit-modal");
    const editForm =
        container.querySelector("#invoice-edit-form");
    const editDaysInput =
        container.querySelector("#invoice-edit-days");

    // Facture actuellement visée par le modal "Modifier" (posé au clic
    // sur le menu ••• de la ligne, voir plus bas).
    let editingInvoiceId = null;

    [createModal, detailsModal, editModal].forEach(modal => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.classList.remove("open");
            }
        });
    });

    container
        .querySelector("#close-invoice-edit")
        .addEventListener("click", () => {
            editModal.classList.remove("open");
        });

    container
        .querySelector("#cancel-invoice-edit")
        .addEventListener("click", () => {
            editModal.classList.remove("open");
        });

    function openInvoiceEditModal(invoice) {
        editingInvoiceId = invoice.id;
        editDaysInput.value = 7;
        editModal.classList.add("open");
    }

    editForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const days = Number(editDaysInput.value);

        try {
            const response = await apiFetch(
                `/stripe/connect/invoices/${editingInvoiceId}`,
                {
                    method: "POST",
                    body: { days_until_due: days }
                }
            );
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de modifier la facture"
                );
            }

            showToast("Facture modifiée", "success");

            editModal.classList.remove("open");

            await loadInvoices();

        } catch (error) {
            console.error(error);
            showToast(
                error.message ||
                "Erreur lors de la modification de la facture",
                "error"
            );
        }
    });

    async function voidInvoice(invoice) {
        if (!confirm(
            invoice.status === "draft"
                ? "Confirmer la suppression de ce brouillon de facture ?"
                : "Confirmer l'annulation de cette facture ? Cette action est irréversible."
        )) return;

        try {
            const response = await apiFetch(
                `/stripe/connect/invoices/${invoice.id}/void`,
                { method: "POST" }
            );
            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible d'annuler la facture"
                );
            }

            showToast("Facture annulée", "success");

            await loadInvoices();

        } catch (error) {
            console.error(error);
            showToast(
                error.message ||
                "Erreur lors de l'annulation de la facture",
                "error"
            );
        }
    }

    function showInvoiceDetails(invoice) {

        const statusLabels = {
            draft: "Brouillon",
            open: "À encaisser",
            paid: "Payée",
            uncollectible: "Irrécouvrable",
            void: "Annulée",
        };

        container.querySelector("#invoice-details-subtitle").textContent =
            invoice.number || invoice.id;

        container.querySelector("#invoice-details-content").innerHTML = `
            <div class="customer-details-grid">

                <div class="customer-detail-item">
                    <span>ID facture</span>
                    <strong>${invoice.id}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Numéro</span>
                    <strong>${invoice.number || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Client</span>
                    <strong>${invoice.customer_email || invoice.customer || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Montant dû</span>
                    <strong>${invoice.amount_due != null ? `${(invoice.amount_due / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${(invoice.currency || "").toUpperCase()}` : "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Montant payé</span>
                    <strong>${invoice.amount_paid != null ? `${(invoice.amount_paid / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${(invoice.currency || "").toUpperCase()}` : "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Statut</span>
                    <strong>${statusLabels[invoice.status] || invoice.status || "—"}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Encaissement</span>
                    <strong>
                        ${
                            invoice.collection_method === "send_invoice"
                                ? "Paiement par facture"
                                : invoice.collection_method === "charge_automatically"
                                    ? "Prélèvement automatique"
                                    : "—"
                        }
                    </strong>
                </div>

                <div class="customer-detail-item">
                    <span>Échéance</span>
                    <strong>${formatDate(invoice.due_date)}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Créée le</span>
                    <strong>${formatDate(invoice.created)}</strong>
                </div>

                <div class="customer-detail-item">
                    <span>Payée le</span>
                    <strong>${formatDate(invoice.status_transitions?.paid_at)}</strong>
                </div>

            </div>

            ${renderMetadataSection(invoice.metadata, "Facture")}
        `;

        detailsModal.classList.add("open");
    }

    /* =====================================================
       CHARGER CLIENTS + TARIFS
    ===================================================== */

    async function loadFormData() {

        try {
            const [
                customersResponse,
                productsResponse
            ] = await Promise.all([
                apiFetch(
                    "/stripe/connect/customers"
                ),
                apiFetch(
                    "/stripe/connect/products"
                )
            ]);
            const customersData =
                await customersResponse.json();
            const productsData =
                await productsResponse.json();
            if (!customersResponse.ok) {
                throw new Error(
                    customersData.detail ||
                    "Impossible de récupérer les clients"
                );
            }
            if (!productsResponse.ok) {
                throw new Error(
                    productsData.detail ||
                    "Impossible de récupérer les produits"
                );
            }
            const customers =
                customersData.data || [];
            const products =
                productsData.data || [];

            /* =============================================
               CLIENTS
            ============================================= */

            customerSelect.innerHTML = `
                <option value="">
                    Sélectionner un client
                </option>

                ${customers.map(customer => `

                    <option value="${customer.id}">

                        ${
                            customer.name ||
                            customer.email ||
                            customer.id
                        }

                        ${
                            customer.email
                                ? ` — ${customer.email}`
                                : ""
                        }

                    </option>

                `).join("")}
            `;


            /* =============================================
               TARIFS
               Facture = tarifs actifs
            ============================================= */

            const prices = [];


            products.forEach(product => {

                const productPrices =
                    product.prices || [];


                productPrices.forEach(price => {
                    if (price.active && price.type === "one_time") {
                        prices.push({
                            product,
                            price
                        });
                    }
                });

            });


            priceSelect.innerHTML = `
                <option value="">
                    Sélectionner un tarif
                </option>

                ${prices.map(item => {

                    const product =
                        item.product;

                    const price =
                        item.price;


                    const amount =
                        price.unit_amount != null
                            ? (
                                price.unit_amount / 100
                            ).toLocaleString(
                                "fr-FR",
                                {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                }
                            )
                            : "—";


                    const currency =
                        (
                            price.currency || ""
                        ).toUpperCase();


                    let typeText =
                        price.type === "recurring"
                            ? "Récurrent"
                            : "Unique";


                    if (
                        price.type === "recurring" &&
                        price.recurring
                    ) {

                        const interval =
                            price.recurring.interval;

                        const count =
                            price.recurring.interval_count || 1;


                        typeText =
                            count === 1
                                ? (
                                    interval === "month"
                                        ? "Mensuel"
                                        : interval === "year"
                                            ? "Annuel"
                                            : interval === "week"
                                                ? "Hebdomadaire"
                                                : interval
                                )
                                : `Tous les ${count} ${interval}`;

                    }


                    return `

                        <option value="${price.id}">

                            ${product.name || "Produit"}

                            — ${amount} ${currency}

                            — ${typeText}

                        </option>

                    `;

                }).join("")}
            `;


        } catch (error) {

            console.error(
                "Erreur chargement formulaire facture :",
                error
            );


            customerSelect.innerHTML = `
                <option value="">
                    Impossible de charger les clients
                </option>
            `;


            priceSelect.innerHTML = `
                <option value="">
                    Impossible de charger les tarifs
                </option>
            `;


            showToast(
                error.message ||
                "Impossible de charger les données",
                "error"
            );

        }

    }


    /* =====================================================
       CHARGER LES FACTURES
    ===================================================== */

    async function loadInvoices() {

        closeRowMenu();

        const list =
            container.querySelector(
                "#invoices-list"
            );


        list.innerHTML = `
            <div class="commerce-card">
                <p>Chargement des factures...</p>
            </div>
        `;


        try {

            const response =
                await apiFetch(
                    "/stripe/connect/invoices"
                );
            const data = await response.json();
            console.log("Invoice objet :", data)
            if (!response.ok) {
                throw new Error(
                    response.status === 401
                        ? "Votre session a expiré. Veuillez vous reconnecter."
                        : data.detail || "Impossible de récupérer les factures"
                );
            }
            const invoices =
                data.data || [];

            const summaryEl = container.querySelector("#invoices-summary");

            // Pagination 10 par 10 (Précédent/Suivant, même mécanisme que
            // Transactions) - purement côté client : la liste complète est
            // déjà en mémoire (invoices, récupérée en un seul appel
            // ci-dessus), donc les KPI et les filtres par statut
            // continuent de porter sur l'ensemble réel, jamais juste la
            // page affichée. resetPage=false uniquement pour un clic
            // Précédent/Suivant, qui ne doit pas revenir à la page 1.
            const invoicesPageSize = 10;
            let invoicesPageNumber = 1;

            function isInvoiceLate(invoice) {
                return (
                    invoice.status === "open" &&
                    !!invoice.due_date &&
                    (invoice.due_date * 1000) < Date.now()
                );
            }

            function matchesInvoiceFilter(invoice, filter) {
                switch (filter) {
                    case "draft": return invoice.status === "draft";
                    case "open": return invoice.status === "open" && !isInvoiceLate(invoice);
                    case "late": return isInvoiceLate(invoice);
                    case "paid": return invoice.status === "paid";
                    default: return true;
                }
            }

            function renderTable(filter = "all", { resetPage = true } = {}) {

                if (resetPage) invoicesPageNumber = 1;

                const filteredInvoices = invoices.filter(
                    invoice => matchesInvoiceFilter(invoice, filter)
                );

                if (!filteredInvoices.length) {
                    list.innerHTML = `
                        <div class="commerce-card">
                            <p>
                                Aucune facture dans cette catégorie.
                            </p>
                        </div>
                    `;
                    return;
                }

                const invoicesPageStart = (invoicesPageNumber - 1) * invoicesPageSize;
                const pageInvoices = filteredInvoices.slice(invoicesPageStart, invoicesPageStart + invoicesPageSize);
            /* =================================================
               TABLEAU
            ================================================= */

            list.innerHTML = `

                <div class="table-wrap">

                    <div
                        class="d-flex justify-content-between align-items-center mb-3"
                    >

                        <div>

                            <div class="table-title">
                                Factures
                            </div>

                            <div class="page-subtitle">
                                ${filteredInvoices.length}
                                facture(s)
                            </div>

                        </div>

                    </div>


                    <div id="customers-scroll-box">

                        <table class="table">

                            <thead>

                                <tr>

                                    <th>Nom du client</th>

                                    <th>Email du client</th>

                                    <th>Numéro de facture</th>

                                    <th>Montant dû</th>

                                    <th>Montant payé</th>

                                    <th>Encaissement</th>

                                    <th>Échéance</th>

                                    <th>Créée le</th>

                                    <th>Statut</th>

                                    <th></th>

                                </tr>

                            </thead>


                            <tbody>

                                ${pageInvoices.map(invoice => {

                                    const amountDue =
                                        invoice.amount_due != null
                                            ? (
                                                invoice.amount_due / 100
                                            ).toLocaleString(
                                                "fr-FR",
                                                {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                }
                                            )
                                            : "—";


                                    const amountPaid =
                                        invoice.amount_paid != null
                                            ? (
                                                invoice.amount_paid / 100
                                            ).toLocaleString(
                                                "fr-FR",
                                                {
                                                    minimumFractionDigits: 2,
                                                    maximumFractionDigits: 2
                                                }
                                            )
                                            : "—";


                                    const currency =
                                        (
                                            invoice.currency || ""
                                        ).toUpperCase();


                                    let statusClass =
                                        "status-warning";

                                    let statusText =
                                        invoice.status || "—";


                                    if (
                                        invoice.status ===
                                        "paid"
                                    ) {

                                        statusClass =
                                            "status-success";

                                        statusText =
                                            "Payée";

                                    } else if (
                                        invoice.status ===
                                        "open"
                                    ) {

                                        statusClass =
                                            "status-warning";

                                        statusText =
                                            "Ouverte";

                                    } else if (
                                        invoice.status ===
                                        "void"
                                    ) {

                                        statusClass =
                                            "status-danger";

                                        statusText =
                                            "Annulée";

                                    } else if (
                                        invoice.status ===
                                        "uncollectible"
                                    ) {

                                        statusClass =
                                            "status-danger";

                                        statusText =
                                            "Irrécouvrable";

                                    } else if (
                                        invoice.status ===
                                        "draft"
                                    ) {

                                        statusClass =
                                            "status-warning";

                                        statusText =
                                            "Brouillon";

                                    }


                                    return `

                                        <tr>

                                            <td>

                                                ${invoice.customer_name || "—"}

                                            </td>


                                            <td>

                                                ${invoice.customer_email || "—"}

                                            </td>


                                            <td>

                                                <code class="customer-id">
                                                    ${
                                                        invoice.number ||
                                                        invoice.id
                                                    }
                                                </code>

                                            </td>


                                            <td>

                                                <span class="amount-cell">
                                                    ${amountDue}
                                                </span>

                                                <span class="amount-currency">
                                                    ${currency}
                                                </span>

                                            </td>


                                            <td>

                                                <span class="amount-cell">
                                                    ${amountPaid}
                                                </span>

                                                <span class="amount-currency">
                                                    ${currency}
                                                </span>

                                            </td>


                                            <td>
                                                ${
                                                    invoice.collection_method === "send_invoice"
                                                        ? "Paiement par facture"
                                                        : invoice.collection_method === "charge_automatically"
                                                            ? "Prélèvement automatique"
                                                            : "—"
                                                }
                                            </td>
                                            <td>

                                                ${formatDate(invoice.due_date)}

                                            </td>


                                            <td>

                                                ${formatDate(invoice.created)}

                                            </td>

                                            <td>

                                                <span
                                                    class="status-badge ${statusClass}"
                                                >
                                                    ${statusText}
                                                </span>

                                            </td>

                                            <td>
                                                <div
                                                    class="row-menu"
                                                    data-invoice-id="${invoice.id}"
                                                >
                                                    <button
                                                        type="button"
                                                        class="row-menu-trigger"
                                                        aria-label="Actions"
                                                        aria-haspopup="true"
                                                    >
                                                        •••
                                                    </button>
                                                    <div class="row-menu-dropdown">
                                                        <button
                                                            type="button"
                                                            class="row-menu-item"
                                                            data-row-action="details"
                                                        >
                                                            Détails
                                                        </button>
                                                        ${
                                                            invoice.invoice_pdf
                                                                ? `
                                                                    <a
                                                                        href="${invoice.invoice_pdf}"
                                                                        download
                                                                        class="row-menu-item"
                                                                    >
                                                                        Télécharger
                                                                    </a>
                                                                `
                                                                : ""
                                                        }
                                                        ${
                                                            invoice.hosted_invoice_url
                                                                ? `
                                                                    <a
                                                                        href="${invoice.hosted_invoice_url}"
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        class="row-menu-item"
                                                                    >
                                                                        Voir sur Stripe
                                                                    </a>
                                                                `
                                                                : ""
                                                        }
                                                        ${
                                                            invoice.status === "draft" || invoice.status === "open"
                                                                ? `
                                                                    <button
                                                                        type="button"
                                                                        class="row-menu-item"
                                                                        data-row-action="edit"
                                                                    >
                                                                        Modifier
                                                                    </button>
                                                                    <button
                                                                        type="button"
                                                                        class="row-menu-item row-menu-item-danger"
                                                                        data-row-action="void"
                                                                    >
                                                                        Annuler
                                                                    </button>
                                                                `
                                                                : ""
                                                        }
                                                    </div>
                                                </div>
                                            </td>

                                        </tr>

                                    `;

                                }).join("")}

                            </tbody>

                        </table>

                    </div>

                </div>

                <div class="d-flex justify-content-between align-items-center mt-3">
                    <span id="invoices-pagination-info" class="text-muted">Page ${invoicesPageNumber}</span>
                    <div class="d-flex gap-2">
                        <button id="invoices-prev-page" type="button" class="pagination-nav-btn" ${invoicesPageNumber <= 1 ? "disabled" : ""}><i class="bi bi-chevron-left"></i></button>
                        <button id="invoices-next-page" type="button" class="pagination-nav-btn" ${invoicesPageStart + invoicesPageSize >= filteredInvoices.length ? "disabled" : ""}><i class="bi bi-chevron-right"></i></button>
                    </div>
                </div>

            `;

            list.querySelector("#invoices-prev-page")?.addEventListener("click", () => {
                if (invoicesPageNumber <= 1) return;
                invoicesPageNumber--;
                renderTable(filter, { resetPage: false });
            });
            list.querySelector("#invoices-next-page")?.addEventListener("click", () => {
                if (invoicesPageStart + invoicesPageSize >= filteredInvoices.length) return;
                invoicesPageNumber++;
                renderTable(filter, { resetPage: false });
            });

            /* =================================================
               MENU D'ACTIONS PAR LIGNE (•••)
            ================================================= */

            list
                .querySelectorAll(".row-menu-trigger")
                .forEach(trigger => {

                    trigger.addEventListener("click", (event) => {

                        event.stopPropagation();

                        if (trigger.closest(".row-menu").classList.contains("open")) {
                            closeRowMenu();
                        } else {
                            openRowMenu(trigger);
                        }

                    });

                });

            list
                .querySelectorAll(".row-menu-item")
                .forEach(item => {

                    item.addEventListener("click", () => {

                        const row = item.closest(".row-menu");
                        closeRowMenu();

                        if (!item.dataset.rowAction) return;

                        const invoice = invoices.find(
                            i => i.id === row.dataset.invoiceId
                        );

                        if (!invoice) return;

                        if (item.dataset.rowAction === "details") {
                            showInvoiceDetails(invoice);
                        } else if (item.dataset.rowAction === "edit") {
                            openInvoiceEditModal(invoice);
                        } else if (item.dataset.rowAction === "void") {
                            voidInvoice(invoice);
                        }
                    });
                });

            }

            /* =================================================
               KPI — Toutes / Brouillons / À encaisser / En retard / Payées
            ================================================= */

            renderCommerceKpis(
                summaryEl,
                [
                    { filter: "all", label: "Toutes les factures", count: invoices.length },
                    {
                        filter: "draft",
                        label: "Brouillons",
                        count: invoices.filter(i => matchesInvoiceFilter(i, "draft")).length
                    },
                    {
                        filter: "open",
                        label: "À encaisser",
                        count: invoices.filter(i => matchesInvoiceFilter(i, "open")).length
                    },
                    {
                        filter: "late",
                        label: "En retard de paiement",
                        count: invoices.filter(i => matchesInvoiceFilter(i, "late")).length
                    },
                    {
                        filter: "paid",
                        label: "Payées",
                        count: invoices.filter(i => matchesInvoiceFilter(i, "paid")).length
                    },
                ],
                "all",
                renderTable
            );

            renderTable("all");

        } catch (error) {

            console.error(
                "Erreur récupération factures Stripe :",
                error
            );


            list.innerHTML = `
                <div class="commerce-card">
                    <p>
                        ${
                            error.message ||
                            "Erreur lors du chargement des factures"
                        }
                    </p>
                </div>
            `;

        }

    }


    /* =====================================================
       CRÉATION
    ===================================================== */

    form.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const customer_id =
                customerSelect.value;


            const price_id =
                priceSelect.value;


            const quantity =
                Number(
                    container
                        .querySelector(
                            "#invoice-quantity"
                        )
                        .value
                );


            const days_until_due =
                Number(
                    container
                        .querySelector(
                            "#invoice-days"
                        )
                        .value
                );


            if (!customer_id || !price_id) {

                showToast(
                    "Sélectionnez un client et un tarif.",
                    "error"
                );

                return;

            }


            try {

                const response =
                    await apiFetch(
                        "/stripe/connect/invoices",
                        {
                            method: "POST",

                            body: {
                                customer_id,
                                price_id,
                                quantity,
                                collection_method:
                                    "send_invoice",
                                days_until_due
                            }
                        }
                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.detail ||
                        "Impossible de créer la facture"
                    );

                }


                showToast(
                    "Facture créée avec succès",
                    "success"
                );


                form.reset();


                await loadInvoices();


            } catch (error) {

                console.error(error);


                showToast(
                    error.message ||
                    "Erreur lors de la création de la facture",
                    "error"
                );

            }

        }
    );


    await Promise.all([
        loadFormData(),
        loadInvoices()
    ]);

}
/* =========================================================
   MOYENS DE PAIEMENT
========================================================= */
async function renderPaymentMethods(container) {

    container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-solid fa-credit-card"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Moyens de paiement</h1>
                        <p>Les réglages de votre compte Stripe connecté : quelles cartes et quels wallets (Apple Pay, Google Pay...) vous acceptez. À ajuster une fois pour couvrir plus de clients, dans plus de pays.</p>
                    </div>
                </div>
            </div>

            <!-- KPI : ZONE INDÉPENDANTE DU TABLEAU -->
            <div id="payment-methods-summary"></div>
        </div>

        <!-- TABLEAU : ZONE INDÉPENDANTE -->
        <div id="payment-methods-table"></div>
    `;

    const summary = container.querySelector(
        "#payment-methods-summary"
    );

    const tableContainer = container.querySelector(
        "#payment-methods-table"
    );

    /* =========================================================
       LIBELLÉS UX
    ========================================================= */

    const PAYMENT_METHOD_LABELS = {
        acss_debit: "ACSS Debit",
        affirm: "Affirm",
        afterpay_clearpay: "Afterpay / Clearpay",
        alipay: "Alipay",
        alma: "Alma",
        amazon_pay: "Amazon Pay",
        au_becs_debit: "BECS Direct Debit",
        bacs_debit: "Bacs Direct Debit",
        bancontact: "Bancontact",
        billie: "Billie",
        blik: "BLIK",
        boleto: "Boleto",
        card: "Cartes",
        cartes_bancaires: "Cartes Bancaires",
        cashapp: "Cash App",
        eps: "EPS",
        fpx: "FPX",
        giropay: "Giropay",
        grabpay: "GrabPay",
        ideal: "iDEAL",
        klarna: "Klarna",
        link: "Link",
        mobilepay: "MobilePay",
        multibanco: "Multibanco",
        oxxo: "OXXO",
        p24: "Przelewy24",
        paypal: "PayPal",
        paynow: "PayNow",
        promptpay: "PromptPay",
        revolut_pay: "Revolut Pay",
        samsung_pay: "Samsung Pay",
        sepa_debit: "Prélèvement SEPA",
        sofort: "Sofort",
        swish: "Swish",
        twint: "TWINT",
        us_bank_account: "US Bank Account",
        wechat_pay: "WeChat Pay",
        zip: "Zip"
    };
    const PAYMENT_METHOD_ICONS = {
        affirm: "/assets/affirm.svg",
        apple_pay: "/assets/apple-pay.svg",
        bancontact: "/assets/bancontact.svg",
        blik: "/assets/blik-logo.svg",
        card: "/assets/carte.svg",
        cartes_bancaires: "/assets/carte_bancaire.svg",
        cashapp: "/assets/cashapp.svg",
        eps: "/assets/eps.svg",
        google_pay: "/assets/google-pay.svg",
        ideal: "/assets/ideal.svg",
        klarna: "/assets/klarna-logo.svg",
        link: "/assets/link.svg",
        mastercard: "/assets/mastercard.svg"
    };

    const PAYMENT_METHOD_TYPES = {
        card: "Cartes bancaires",
        cartes_bancaires: "Cartes bancaires",

        sepa_debit: "Prélèvement bancaire",
        bacs_debit: "Prélèvement bancaire",
        acss_debit: "Prélèvement bancaire",

        us_bank_account: "Compte bancaire",

        paypal: "Portefeuille électronique",
        alipay: "Portefeuille électronique",
        cashapp: "Portefeuille électronique",
        link: "Portefeuille électronique",

        klarna: "Paiement différé",
        affirm: "Paiement différé",
        afterpay_clearpay: "Paiement différé",

        bancontact: "Paiement bancaire",
        ideal: "Paiement bancaire",
        p24: "Paiement bancaire",
        eps: "Paiement bancaire"
    };
    const PAYMENT_METHOD_POPULARITY = {
        card: "Toutes les régions",
        cartes_bancaires: "France",
        cartes_coreennes: "Corée du Sud",
        alipay: "Chine",
        amazon_pay: "Toutes les régions",
        apple_pay: "Toutes les régions",
        cashapp: "États-Unis",
        klarna: "Toutes les régions",
        bancontact: "Belgique",
        blik: "Pologne",
        boleto: "Brésil",
        eps: "Autriche",
        fpx: "Malaisie",
        ideal: "Pays-Bas",
        p24: "Pologne",
        paypal: "Toutes les régions",
        sepa_debit: "Toutes les régions",
        sofort: "Europe",
        twint: "Suisse",
        us_bank_account: "États-Unis",
        wechat_pay: "Chine"
    };

    function formatPaymentMethodName(id) {

        return PAYMENT_METHOD_LABELS[id]
            || id
                .replace(/_/g, " ")
                .replace(/\b\w/g, char => char.toUpperCase());
    }

    function getPaymentMethodType(id) {
        return PAYMENT_METHOD_TYPES[id]
            || "Moyen de paiement";
    }
    function getPaymentMethodPopularity(id) {
        return PAYMENT_METHOD_POPULARITY[id]
             || "";
    }

    /* =========================================================
       STYLE UX
    ========================================================= */

    if (!document.querySelector("#payment-methods-ux-style")) {

        const style = document.createElement("style");

        style.id = "payment-methods-ux-style";

        style.textContent = `

            /* ================================================
               KPI
            ================================================ */

            .payment-method-filters {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 10px;
                margin-bottom: 20px;
            }

            .payment-method-kpi {
                width: 100%;
                min-height: 58px;
                padding: 9px 13px;

                border: 1px solid #e5e7eb;
                border-radius: 8px;

                background: #ffffff;

                text-align: left;
                cursor: pointer;

                transition:
                    border-color .15s ease,
                    background .15s ease,
                    box-shadow .15s ease;
            }

            .payment-method-kpi:hover {
                border-color: #cbd5e1;
                background: #fafafa;
            }

            .payment-method-kpi.active {
                border-color: #94a3b8;
                background: #f8fafc;
                box-shadow: 0 0 0 1px #94a3b8;
            }

            .payment-method-kpi-label {
                display: block;

                font-size: 12px;
                line-height: 16px;

                color: #6b7280;

                margin-bottom: 2px;
            }

            .payment-method-kpi-value {
                display: block;

                font-size: 19px;
                line-height: 21px;

                font-weight: 600;

                color: #111827;
            }


            /* ================================================
               TABLEAU
            ================================================ */

            .payment-methods-card {
                background: #a0a4aaff;

                border: 1px solid #e5e7eb;
                border-radius: 10px;

                overflow: hidden;
            }

            .payment-methods-card-header {
                padding: 16px 18px;

                border-bottom: 1px solid #e5e7eb;
            }

            .payment-methods-card-title {
                font-size: 14px;
                font-weight: 600;
                color: #111827;
            }

            .payment-methods-table-wrapper {
                overflow-x: auto;
            }

            .payment-methods-table {
                width: 100%;
                border-collapse: collapse;
            }
            .payment-methods-table tbody td {
                background: #a0a4aaff !important;
            }

            .payment-methods-table th {
                padding: 11px 16px;

                text-align: left;

                font-size: 11px;
                font-weight: 600;

                color: #6b7280;

                border-bottom: 1px solid #e5e7eb;
            }

            .payment-methods-table td {
                padding: 12px 16px;

                font-size: 13px;

                border-bottom: 1px solid #f1f5f9;

                vertical-align: middle;
            }

            .payment-methods-table tr:last-child td {
                border-bottom: none;
            }


            /* ================================================
               NOM DU MOYEN DE PAIEMENT
            ================================================ */

            .payment-method-name {
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .payment-method-icon {
                width: 32px;
                height: 32px;
                flex: 0 0 32px;

                display: flex;
                align-items: center;
                justify-content: center;

                border: none;
                border-radius: 0;
                background: transparent;
            }

            .payment-method-icon-img {
                width: 30px;
                height: 30px;
                object-fit: contain;
                display: block;
            }

            .payment-method-name-text {
                color: #111827;
                font-weight: 500;
            }


            /* ================================================
               TYPE + STATUT
            ================================================ */

            .payment-method-type {
                display: flex;
                align-items: center;
                gap: 8px;

                color: #4b5563;
            }


            /* ================================================
               POPULARITÉ
            ================================================ */

            .payment-method-popularity {
                color: #6b7280;
                font-size: 13px;
            }


            @media (max-width: 768px) {

                .payment-method-filters {
                    grid-template-columns: repeat(2, 1fr);
                }

            }

        `;

        document.head.appendChild(style);
    }

    /* =========================================================
       CHARGEMENT
    ========================================================= */

    try {

        tableContainer.innerHTML = `
            <div class="payment-methods-card">
                <div style="padding:20px;">
                    Chargement des moyens de paiement...
                </div>
            </div>
        `;

        const response = await apiFetch(
            "/stripe/connect/payment-methods"
        );

        const data = await response.json();

        console.log(
            "DONNÉES STRIPE — CONFIGURATION MOYENS DE PAIEMENT :",
            data
        );

        if (!response.ok) {

            throw new Error(
                data.detail ||
                "Impossible de récupérer les moyens de paiement"
            );
        }

        const configurations = Array.isArray(data.data)
            ? data.data
            : [];

        if (!configurations.length) {

            summary.innerHTML = "";

            tableContainer.innerHTML = `
                <div class="payment-methods-card">
                    <div style="padding:20px;">
                        Aucun moyen de paiement trouvé.
                    </div>
                </div>
            `;

            return;
        }

        const configuration = configurations.find(config => config.application) || configurations[0];
        console.log("CONFIGURATION STRIPE COMPLÈTE :", configuration);
        console.log("CLÉS DE MOYENS DE PAIEMENT :", Object.entries(configuration)
            .filter(([id, value]) =>
                value &&
                typeof value === "object" &&
                (
                    "available" in value ||
                    "display_preference" in value
                )
            )
            .map(([id]) => id)
        );
        console.table(
            Object.entries(configuration)
                .filter(([id, value]) =>
                    value &&
                    typeof value === "object" &&
                    (
                        "available" in value ||
                        "display_preference" in value
                    )
                )
                .map(([id, value]) => ({
                    id,
                    available: value.available,
                    preference: value.display_preference?.preference,
                    value: value.display_preference?.value
                }))
        );
        /* =========================================================
           EXTRACTION DYNAMIQUE DES MOYENS STRIPE
        ========================================================= */

        const methods = Object.entries(configuration)
            .filter(([id, value]) => {
                if (
                    !value ||
                    typeof value !== "object"
                ) {
                    return false;
                }
                return (
                    Object.prototype.hasOwnProperty.call(
                        value,
                        "available"
                    ) ||
                    Object.prototype.hasOwnProperty.call(
                        value,
                        "display_preference"
                    )
                );
            })
            .map(([id, stripeData]) => {

                const preference =
                    stripeData.display_preference?.value || null;
                const enabled =
                    preference === "on";
                const blocked =
                    stripeData.blocked === true;
                return {
                    id,

                    name: formatPaymentMethodName(id),

                    type: getPaymentMethodType(id),

                    available:
                        stripeData.available === true,

                    enabled,

                    blocked,

                    stripe: stripeData
                };
            });

        /* =========================================================
           COMPTEURS
        ========================================================= */

        const totalCount = methods.length;

        const activeCount = methods.filter(
            method =>
                method.enabled &&
                !method.blocked
        ).length;

        const inactiveCount = methods.filter(
            method =>
                !method.enabled &&
                !method.blocked
        ).length;

        const blockedCount = methods.filter(
            method =>
                method.blocked
        ).length;

        /* =========================================================
           KPI — INDÉPENDANTS DU TABLEAU
        ========================================================= */

        summary.innerHTML = `
            <div class="payment-method-filters">

                <button
                    type="button"
                    class="payment-method-kpi active"
                    data-filter="all"
                >
                    <span class="payment-method-kpi-label">
                        Tout
                    </span>

                    <strong class="payment-method-kpi-value">
                        ${totalCount}
                    </strong>
                </button>


                <button
                    type="button"
                    class="payment-method-kpi"
                    data-filter="active"
                >
                    <span class="payment-method-kpi-label">
                        Activé
                    </span>

                    <strong class="payment-method-kpi-value">
                        ${activeCount}
                    </strong>
                </button>


                <button
                    type="button"
                    class="payment-method-kpi"
                    data-filter="inactive"
                >
                    <span class="payment-method-kpi-label">
                        Désactivé
                    </span>

                    <strong class="payment-method-kpi-value">
                        ${inactiveCount}
                    </strong>
                </button>


                <button
                    type="button"
                    class="payment-method-kpi"
                    data-filter="blocked"
                >
                    <span class="payment-method-kpi-label">
                        Bloqué
                    </span>

                    <strong class="payment-method-kpi-value">
                        ${blockedCount}
                    </strong>
                </button>

            </div>
        `;

        /* =========================================================
           TABLEAU
        ========================================================= */

        // Pagination 10 par 10 (Précédent/Suivant, même mécanisme que
        // Transactions) - purement côté client : la liste complète
        // (methods) est déjà en mémoire, donc le KPI et les filtres
        // Actifs/Inactifs/Bloqués continuent de porter sur l'ensemble réel.
        const methodsPageSize = 10;
        let methodsPageNumber = 1;

        function renderTable(filter = "all", { resetPage = true } = {}) {

            if (resetPage) methodsPageNumber = 1;

            let filteredMethods = methods;

            if (filter === "active") {

                filteredMethods = methods.filter(
                    method =>
                        method.enabled &&
                        !method.blocked
                );

            } else if (filter === "inactive") {

                filteredMethods = methods.filter(
                    method =>
                        !method.enabled &&
                        !method.blocked
                );

            } else if (filter === "blocked") {

                filteredMethods = methods.filter(
                    method =>
                        method.blocked
                );
            }

            const methodsPageStart = (methodsPageNumber - 1) * methodsPageSize;
            const pageMethods = filteredMethods.slice(methodsPageStart, methodsPageStart + methodsPageSize);

            tableContainer.innerHTML = `
                <div class="table-wrap">

                    <div class="table-title">
                        Moyens de paiement
                    </div>
                    <div id="customers-scroll-box">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>
                                        Moyen de paiement
                                    </th>
                                    <th>
                                        Type
                                    </th>
                                    <th>
                                        Popularité
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                ${
                                    filteredMethods.length

                                        ? pageMethods.map(
                                            method => {

                                                const statusLabel =
                                                    method.blocked
                                                        ? "Bloqué"
                                                        : method.enabled
                                                            ? "Activé"
                                                            : "Désactivé";

                                                const statusClass =
                                                    method.blocked
                                                        ? "status-danger"
                                                        : method.enabled
                                                            ? "status-success"
                                                            : "status-danger";

                                                
                                                const popularity = getPaymentMethodPopularity(method.id);
                                                return `

                                                    <tr>

                                                        <!-- MOYEN -->

                                                        <td>

                                                            <div class="payment-method-name">
                                                                <!--
                                                                    Emplacement
                                                                    réservé pour
                                                                    l'icône.
                                                                -->
                                                                <div class="payment-method-icon" aria-hidden="true">
                                                                    ${
                                                                        PAYMENT_METHOD_ICONS[method.id]
                                                                            ? `
                                                                                <img
                                                                                    src="${PAYMENT_METHOD_ICONS[method.id]}"
                                                                                    alt=""
                                                                                    class="payment-method-icon-img"
                                                                                >
                                                                            `
                                                                            : ""
                                                                    }
                                                                </div>
                                                                <span
                                                                    class="payment-method-name-text"
                                                                >
                                                                    ${method.name}
                                                                </span>
                                                            </div>

                                                        </td>


                                                        <!-- TYPE + STATUT -->
                                                        <td>
                                                            <div class="payment-method-type">
                                                                <span class="payment-method-type-name">
                                                                    ${method.type}
                                                                </span>
                                                                <span class="payment-method-status ${
                                                                    method.blocked
                                                                        ? "blocked"
                                                                        : method.enabled
                                                                            ? "active"
                                                                            : "inactive"
                                                                }">
                                                                    ${statusLabel}
                                                                </span>
                                                            </div>
                                                        </td>
                                                        <!-- POPULARITÉ -->
                                                        <td>
                                                            <span
                                                                class="payment-method-popularity"
                                                            >
                                                                ${popularity}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                `;
                                            }
                                        ).join("")
                                        : `
                                            <tr>

                                                <td
                                                    colspan="3"
                                                    style="
                                                        text-align:center;
                                                        padding:30px;
                                                        color:#6b7280;
                                                    "
                                                >
                                                    Aucun moyen de paiement
                                                    dans cette catégorie.
                                                </td>

                                            </tr>
                                        `
                                }

                            </tbody>

                        </table>

                    </div>

                </div>

                <div class="d-flex justify-content-between align-items-center mt-3">
                    <span id="methods-pagination-info" class="text-muted">Page ${methodsPageNumber}</span>
                    <div class="d-flex gap-2">
                        <button id="methods-prev-page" type="button" class="pagination-nav-btn" ${methodsPageNumber <= 1 ? "disabled" : ""}><i class="bi bi-chevron-left"></i></button>
                        <button id="methods-next-page" type="button" class="pagination-nav-btn" ${methodsPageStart + methodsPageSize >= filteredMethods.length ? "disabled" : ""}><i class="bi bi-chevron-right"></i></button>
                    </div>
                </div>
            `;

            tableContainer.querySelector("#methods-prev-page")?.addEventListener("click", () => {
                if (methodsPageNumber <= 1) return;
                methodsPageNumber--;
                renderTable(filter, { resetPage: false });
            });
            tableContainer.querySelector("#methods-next-page")?.addEventListener("click", () => {
                if (methodsPageStart + methodsPageSize >= filteredMethods.length) return;
                methodsPageNumber++;
                renderTable(filter, { resetPage: false });
            });
        }

        /* =========================================================
           AFFICHAGE INITIAL
        ========================================================= */

        renderTable("all");

        /* =========================================================
           FILTRES KPI
        ========================================================= */

        summary
            .querySelectorAll(".payment-method-kpi")
            .forEach(button => {

                button.addEventListener(
                    "click",
                    () => {

                        summary
                            .querySelectorAll(
                                ".payment-method-kpi"
                            )
                            .forEach(item => {

                                item.classList.remove(
                                    "active"
                                );

                            });

                        button.classList.add(
                            "active"
                        );

                        renderTable(
                            button.dataset.filter
                        );
                    }
                );

            });

    } catch (error) {

        console.error(
            "ERREUR MOYENS DE PAIEMENT :",
            error
        );

        summary.innerHTML = "";

        tableContainer.innerHTML = `
            <div class="payment-methods-card">
                <div style="padding:20px;">
                    ${
                        error.message ||
                        "Erreur lors du chargement des moyens de paiement"
                    }
                </div>
            </div>
        `;

        if (typeof showToast === "function") {

            showToast(
                error.message ||
                "Erreur lors du chargement des moyens de paiement",
                "error"
            );
        }
    }
}
/* =========================================================
   RISQUE
========================================================= */
async function renderRisk(container) {

    container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-solid fa-shield-halved"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Risque</h1>
                        <p>Votre filet de sécurité anti-fraude : alertes Radar, paiements à risque élevé et litiges Stripe remontés ici en premier. À consulter régulièrement pour réagir avant qu'un litige ne s'aggrave.</p>
                    </div>
                </div>
            </div>
        </div>

        <div id="risk-list"></div>
    `;

    const STATUS_LABELS = {
        won: "Gagné",
        lost: "Perdu",
        warning_closed: "Clôturé",
        charge_refunded: "Remboursé",
        needs_response: "Réponse requise",
        warning_needs_response: "Réponse requise",
        under_review: "En cours d'examen",
        warning_under_review: "En cours d'examen"
    };

    const SUCCESS_STATUSES = ["won", "warning_closed", "charge_refunded"];

    const RISK_LEVEL_LABELS = {
        normal: "Normal",
        elevated: "Élevé",
        highest: "Très élevé",
        not_assessed: "Non évalué",
        unknown: "Inconnu"
    };

    function fmtAmount(amount, currency) {
        return amount != null
            ? `${(amount / 100).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${(currency || "").toUpperCase()}`
            : "—";
    }

    async function loadRisk() {

        const list = container.querySelector("#risk-list");

        list.innerHTML = `
            <div class="commerce-card">
                <p>Chargement des données de risque...</p>
            </div>
        `;

        try {

            const response = await apiFetch("/stripe/connect/risk");
            const data = await response.json();

            console.log("DONNÉES STRIPE — RISQUE :", data);

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de récupérer les données de risque"
                );
            }

            const disputes = data.disputes || [];
            const earlyFraudWarnings = data.early_fraud_warnings || [];
            const allChargesRisk = data.charges_risk || [];
            // Niveau de risque Radar propre à CHAQUE charge
            // (Charge.outcome.risk_level) - coexiste avec disputed=false,
            // c'est la source qui manquait entièrement avant ce fix.
            const chargesRisk = allChargesRisk.filter(
                c => c.outcome?.risk_level && c.outcome.risk_level !== "normal"
            );
            const accountStatus = data.account_status || {};
            const requirements = accountStatus.requirements || {};
            const hasAccountIssue =
                accountStatus.charges_enabled === false ||
                accountStatus.payouts_enabled === false ||
                !!requirements.disabled_reason ||
                (requirements.currently_due || []).length > 0 ||
                (requirements.past_due || []).length > 0;

            const sections = [];

            if (hasAccountIssue) {
                sections.push(`
                    <div class="commerce-card" style="border-color:#f87171; margin-bottom:20px;">
                        <div class="table-title" style="margin-bottom:8px;">Statut du compte connecté</div>
                        <div class="customer-details-grid">
                            <div class="customer-detail-item">
                                <span>Paiements activés</span>
                                <strong>${accountStatus.charges_enabled ? "Oui" : "Non"}</strong>
                            </div>
                            <div class="customer-detail-item">
                                <span>Versements activés</span>
                                <strong>${accountStatus.payouts_enabled ? "Oui" : "Non"}</strong>
                            </div>
                            <div class="customer-detail-item">
                                <span>Raison de restriction</span>
                                <strong>${requirements.disabled_reason || "—"}</strong>
                            </div>
                            <div class="customer-detail-item">
                                <span>Exigences en retard</span>
                                <strong>${(requirements.past_due || []).join(", ") || "—"}</strong>
                            </div>
                        </div>
                    </div>
                `);
            }

            sections.push(`
                <div class="table-wrap" style="margin-bottom:20px;">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div>
                            <div class="table-title">Alertes de fraude (Radar)</div>
                            <div class="page-subtitle">${earlyFraudWarnings.length} alerte(s) — signalées par la banque émettrice, souvent avant tout litige formel</div>
                        </div>
                    </div>
                    ${!earlyFraudWarnings.length ? `
                        <p class="text-muted">Aucune alerte de fraude Radar pour le moment.</p>
                    ` : `
                        <div id="customers-scroll-box">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Alerte</th>
                                        <th>Paiement</th>
                                        <th>Type de fraude</th>
                                        <th>Actionnable</th>
                                        <th>Créé le</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${earlyFraudWarnings.map(efw => `
                                        <tr>
                                            <td><code class="customer-id">${efw.id || "—"}</code></td>
                                            <td><code class="customer-id">${efw.charge || "—"}</code></td>
                                            <td>${efw.fraud_type || "—"}</td>
                                            <td>${efw.actionable ? "Oui" : "Non"}</td>
                                            <td>${formatDate(efw.created)}</td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>
            `);

            sections.push(`
                <div class="table-wrap" style="margin-bottom:20px;">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div>
                            <div class="table-title">Paiements à risque élevé (Radar)</div>
                            <div class="page-subtitle">${chargesRisk.length} paiement(s) signalé(s) sur les ${allChargesRisk.length} plus récents analysés</div>
                        </div>
                    </div>
                    ${!chargesRisk.length ? `
                        <p class="text-muted">Aucun paiement signalé à risque élevé parmi les plus récents.</p>
                    ` : `
                        <div id="customers-scroll-box">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Paiement</th>
                                        <th>Montant</th>
                                        <th>Niveau de risque</th>
                                        <th>Score</th>
                                        <th>Déjà contesté</th>
                                        <th>Créé le</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${chargesRisk.map(c => `
                                        <tr>
                                            <td><code class="customer-id">${c.id || "—"}</code></td>
                                            <td>${fmtAmount(c.amount, c.currency)}</td>
                                            <td><span class="status-badge status-danger">${RISK_LEVEL_LABELS[c.outcome?.risk_level] || c.outcome?.risk_level || "—"}</span></td>
                                            <td>${c.outcome?.risk_score ?? "—"}</td>
                                            <td>${c.disputed ? "Oui" : "Non"}</td>
                                            <td>${formatDate(c.created)}</td>
                                        </tr>
                                    `).join("")}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>
            `);

            sections.push(`
                <div class="table-wrap">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div>
                            <div class="table-title">Litiges</div>
                            <div class="page-subtitle">${disputes.length} litige(s)</div>
                        </div>
                    </div>
                    ${!disputes.length ? `
                        <p class="text-muted">Aucun litige pour le moment.</p>
                    ` : `
                        <div id="customers-scroll-box">
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Litige</th>
                                        <th>Paiement</th>
                                        <th>Montant</th>
                                        <th>Motif</th>
                                        <th>Statut</th>
                                        <th>Créé le</th>
                                        <th>Réponse avant le</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${disputes.map(dispute => {
                                        const statusClass = SUCCESS_STATUSES.includes(dispute.status) ? "status-success" : "status-danger";
                                        const evidenceDueBy = dispute.evidence_details?.due_by;
                                        return `
                                            <tr>
                                                <td><code class="customer-id">${dispute.id || "—"}</code></td>
                                                <td><code class="customer-id">${dispute.charge || "—"}</code></td>
                                                <td>${fmtAmount(dispute.amount, dispute.currency)}</td>
                                                <td>${dispute.reason || "—"}</td>
                                                <td><span class="status-badge ${statusClass}">${STATUS_LABELS[dispute.status] || dispute.status || "—"}</span></td>
                                                <td>${formatDate(dispute.created)}</td>
                                                <td>${formatDate(evidenceDueBy)}</td>
                                            </tr>
                                        `;
                                    }).join("")}
                                </tbody>
                            </table>
                        </div>
                    `}
                </div>
            `);

            list.innerHTML = sections.join("");

        } catch (error) {

            console.error(error);

            list.innerHTML = `
                <div class="commerce-card">
                    <p>
                        ${
                            error.message ||
                            "Erreur lors du chargement des données de risque"
                        }
                    </p>
                </div>
            `;

            showToast(
                error.message ||
                "Erreur lors du chargement des données de risque",
                "error"
            );
        }
    }

    await loadRisk();
}

/* =========================================================
   SHOPIFY (demande du 2026-11-24) — lecture DIRECTE depuis l'API Admin
   Shopify (backend/routes/shopify.py, GET /shopify/products|orders|
   customers) : AUCUNE table miroir côté Xepay, AUCUN objet Stripe créé
   à partir de ces données - séparé à dessein de Clients/Produits
   ci-dessus (Stripe Connect), jamais mélangé dans les mêmes tableaux.
   Trois sections chargées indépendamment (Promise distincte chacune) :
   un échec/scope manquant sur Clients ne doit jamais empêcher
   Produits/Commandes de s'afficher, et inversement.
========================================================= */

function shopifyNotConnectedCardHtml() {
    return `
        <div class="commerce-card">
            <p>Aucune boutique Shopify connectée.</p>
            <p class="text-muted" style="font-size:12.5px;">Connectez votre boutique depuis <strong>Paramètres &gt; Shopify</strong> pour voir ses produits, commandes et clients ici.</p>
        </div>
    `;
}

function shopifyMoneyRange(priceRangeV2) {
    if (!priceRangeV2) return "—";
    const min = priceRangeV2.minVariantPrice;
    const max = priceRangeV2.maxVariantPrice;
    if (!min) return "—";
    const fmt = (m) => `${Number(m.amount).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${m.currencyCode}`;
    if (!max || max.amount === min.amount) return fmt(min);
    return `${fmt(min)} – ${fmt(max)}`;
}

function shopifyMoney(moneyV2) {
    if (!moneyV2) return "—";
    return `${Number(moneyV2.amount).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${moneyV2.currencyCode}`;
}

function shopifyDate(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleDateString("fr-FR", { year: "numeric", month: "short", day: "numeric" });
}

// Les 3 fonctions list_* (backend) renvoient l'id Shopify au format GID
// ("gid://shopify/Product/123") - les routes d'écriture (PATCH/POST .../
// {id}) attendent l'id NUMÉRIQUE brut (voir customer_gid/product_gid/
// order_gid, services/shopify_service.py, qui reconstruisent le GID côté
// serveur) : on extrait donc le dernier segment ici, une seule fois,
// plutôt que de dupliquer cette extraction à chaque bouton d'action.
function shopifyNumericId(gid) {
    if (!gid) return "";
    return String(gid).split("/").pop();
}

function escapeHtmlAttr(value) {
    return String(value ?? "").replace(/"/g, "&quot;");
}

async function renderShopifyProductsSection(container) {
    container.innerHTML = `<div class="commerce-card"><p>Chargement des produits...</p></div>`;
    try {
        const response = await apiFetch("/shopify/products");
        const data = await response.json();
        if (response.status === 404) {
            container.innerHTML = "";
            return false;
        }
        if (!response.ok) throw new Error(data.detail || "Impossible de récupérer les produits Shopify");
        const products = data.data || [];
        container.innerHTML = `
            <div class="table-wrap">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div>
                        <div class="table-title">Produits Shopify</div>
                        <div class="page-subtitle">${products.length} produit(s) - ${data.shop_domain}</div>
                    </div>
                    <button type="button" class="create-client-btn" id="shopify-open-create-product">+ Créer un produit</button>
                </div>
                ${!products.length ? `<p class="text-muted">Aucun produit dans cette boutique.</p>` : `
                <table class="table">
                    <thead>
                        <tr><th>Produit</th><th>Statut</th><th>Stock</th><th>Prix</th><th></th></tr>
                    </thead>
                    <tbody>
                        ${products.map((p) => `
                            <tr>
                                <td>${p.title || "—"}</td>
                                <td>${p.status || "—"}</td>
                                <td>${p.totalInventory ?? "—"}</td>
                                <td>${shopifyMoneyRange(p.priceRangeV2)}</td>
                                <td class="text-end">
                                    <button type="button" class="shopify-row-action-btn"
                                        data-shopify-edit-product="${shopifyNumericId(p.id)}"
                                        data-title="${escapeHtmlAttr(p.title)}"
                                        data-status="${escapeHtmlAttr(p.status)}"
                                    >Modifier</button>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
                `}
            </div>
        `;
        return true;
    } catch (error) {
        console.error(error);
        container.innerHTML = `<div class="commerce-card"><p>${error.message || "Erreur lors du chargement des produits Shopify"}</p></div>`;
        return true;
    }
}

async function renderShopifyOrdersSection(container) {
    container.innerHTML = `<div class="commerce-card"><p>Chargement des commandes...</p></div>`;
    try {
        const response = await apiFetch("/shopify/orders");
        const data = await response.json();
        if (response.status === 404) {
            container.innerHTML = "";
            return;
        }
        if (!response.ok) throw new Error(data.detail || "Impossible de récupérer les commandes Shopify");
        const orders = data.data || [];
        container.innerHTML = `
            <div class="table-wrap">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div>
                        <div class="table-title">Commandes Shopify</div>
                        <div class="page-subtitle">${orders.length} commande(s) - ${data.shop_domain}</div>
                    </div>
                </div>
                ${!orders.length ? `<p class="text-muted">Aucune commande dans cette boutique.</p>` : `
                <table class="table">
                    <thead>
                        <tr><th>Commande</th><th>Client</th><th>Statut financier</th><th>Statut livraison</th><th>Montant</th><th>Date</th><th></th></tr>
                    </thead>
                    <tbody>
                        ${orders.map((o) => `
                            <tr>
                                <td>${o.name || "—"}</td>
                                <td>${o.customer?.displayName || o.customer?.email || "—"}</td>
                                <td>${o.displayFinancialStatus || "—"}</td>
                                <td>${o.cancelledAt ? "Annulée" : (o.displayFulfillmentStatus || "—")}</td>
                                <td>${shopifyMoney(o.totalPriceSet?.shopMoney)}</td>
                                <td>${shopifyDate(o.createdAt)}</td>
                                <td class="text-end">
                                    ${o.cancelledAt ? "" : `<button type="button" class="shopify-row-action-btn"
                                        data-shopify-cancel-order="${shopifyNumericId(o.id)}"
                                        data-order-name="${escapeHtmlAttr(o.name)}"
                                    >Annuler</button>`}
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
                `}
            </div>
        `;
    } catch (error) {
        console.error(error);
        container.innerHTML = `<div class="commerce-card"><p>${error.message || "Erreur lors du chargement des commandes Shopify"}</p></div>`;
    }
}

async function renderShopifyCustomersSection(container) {
    container.innerHTML = `<div class="commerce-card"><p>Chargement des clients...</p></div>`;
    try {
        const response = await apiFetch("/shopify/customers");
        const data = await response.json();
        if (response.status === 404) {
            container.innerHTML = "";
            return;
        }
        if (response.status === 409) {
            // Scope client manquant (read_customers, voir routes/
            // shopify.py) - jamais un échec générique : produits/
            // commandes restent affichés indépendamment, seul ce bloc
            // explique la limite. Pas de bouton "+ Créer" tant que ce
            // scope n'est pas accordé (write_customers irait de toute
            // façon échouer côté Shopify).
            container.innerHTML = `
                <div class="commerce-card">
                    <p>Les clients Shopify ne sont pas encore accessibles.</p>
                    <p class="text-muted" style="font-size:12.5px;">Le scope <code>read_customers</code> n'est pas accordé à "Xepay Sync". Ajoutez-le dans le Partner Dashboard, puis reconnectez la boutique depuis Paramètres &gt; Shopify.</p>
                </div>
            `;
            return;
        }
        if (!response.ok) throw new Error(data.detail || "Impossible de récupérer les clients Shopify");
        const customers = data.data || [];
        container.innerHTML = `
            <div class="table-wrap">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div>
                        <div class="table-title">Clients Shopify</div>
                        <div class="page-subtitle">${customers.length} client(s) - ${data.shop_domain}</div>
                    </div>
                    <button type="button" class="create-client-btn" id="shopify-open-create-customer">+ Créer un client</button>
                </div>
                ${!customers.length ? `<p class="text-muted">Aucun client dans cette boutique.</p>` : `
                <table class="table">
                    <thead>
                        <tr><th>Client</th><th>Email</th><th>Commandes</th><th>Total dépensé</th><th>Créé le</th><th></th></tr>
                    </thead>
                    <tbody>
                        ${customers.map((c) => `
                            <tr>
                                <td>${c.displayName || "—"}</td>
                                <td>${c.email || "—"}</td>
                                <td>${c.numberOfOrders ?? "—"}</td>
                                <td>${shopifyMoney(c.amountSpent)}</td>
                                <td>${shopifyDate(c.createdAt)}</td>
                                <td class="text-end">
                                    <button type="button" class="shopify-row-action-btn"
                                        data-shopify-edit-customer="${shopifyNumericId(c.id)}"
                                        data-first-name="${escapeHtmlAttr(c.firstName)}"
                                        data-last-name="${escapeHtmlAttr(c.lastName)}"
                                        data-email="${escapeHtmlAttr(c.email)}"
                                        data-phone="${escapeHtmlAttr(c.phone)}"
                                    >Modifier</button>
                                </td>
                            </tr>
                        `).join("")}
                    </tbody>
                </table>
                `}
            </div>
        `;
    } catch (error) {
        console.error(error);
        container.innerHTML = `<div class="commerce-card"><p>${error.message || "Erreur lors du chargement des clients Shopify"}</p></div>`;
    }
}

// 3 onglets (demande du 2026-11-24, remplace l'ancien affichage des
// trois sections empilées sur une seule page) - un seul chargé à la
// fois, dans #shopify-tab-content, re-fetché à chaque clic d'onglet
// (pas de cache : cohérent avec le reste de la lecture directe). Chaque
// entrée retourne un booléen "connecté" (voir renderShopifyProductsSection)
// seulement pour l'onglet "produits", qui est aussi celui chargé en
// premier - c'est lui qui détecte si la boutique est connectée avant
// même d'afficher la barre d'onglets.
const SHOPIFY_TABS = [
    { key: "produits", label: "Produits", render: renderShopifyProductsSection },
    { key: "commandes", label: "Commandes", render: renderShopifyOrdersSection },
    { key: "clients", label: "Clients", render: renderShopifyCustomersSection },
];

// Modales d'écriture (demande du 2026-11-24) - partagées entre tous les
// onglets, posées UNE SEULE FOIS dans le gabarit statique de
// renderShopify (donc jamais détruites par un changement d'onglet, qui
// ne remplace que #shopify-tab-content) - même classes CSS que les
// modales Stripe existantes (.customer-modal-overlay/.customer-modal),
// voir renderProducts/renderClients plus haut dans ce fichier.
function shopifyCustomerModalHtml() {
    return `
        <div class="customer-modal-overlay" id="shopify-customer-modal">
            <div class="customer-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3 id="shopify-customer-modal-title">Créer un client</h3>
                        <p>Client Shopify de votre boutique connectée.</p>
                    </div>
                    <button type="button" class="customer-modal-close" id="shopify-customer-modal-close">×</button>
                </div>
                <form id="shopify-customer-form">
                    <input type="hidden" id="shopify-customer-id">
                    <div class="form-row">
                        <div class="form-group"><label>Prénom</label><input type="text" id="shopify-customer-first-name"></div>
                        <div class="form-group"><label>Nom</label><input type="text" id="shopify-customer-last-name"></div>
                    </div>
                    <div class="form-group"><label>Email</label><input type="email" id="shopify-customer-email"></div>
                    <div class="form-group"><label>Téléphone</label><input type="text" id="shopify-customer-phone"></div>
                    <button type="submit" class="create-client-btn" id="shopify-customer-submit">Créer</button>
                </form>
            </div>
        </div>
    `;
}

function shopifyProductModalHtml() {
    return `
        <div class="customer-modal-overlay" id="shopify-product-modal">
            <div class="customer-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3 id="shopify-product-modal-title">Créer un produit</h3>
                        <p>Produit Shopify de votre boutique connectée.</p>
                    </div>
                    <button type="button" class="customer-modal-close" id="shopify-product-modal-close">×</button>
                </div>
                <form id="shopify-product-form">
                    <input type="hidden" id="shopify-product-id">
                    <div class="form-group"><label>Titre</label><input type="text" id="shopify-product-title" required></div>
                    <div class="form-group"><label>Description</label><textarea id="shopify-product-description"></textarea></div>
                    <div class="form-row">
                        <div class="form-group" id="shopify-product-price-group">
                            <label>Prix</label>
                            <input type="number" step="0.01" min="0.01" id="shopify-product-price">
                        </div>
                        <div class="form-group">
                            <label>Statut</label>
                            <select id="shopify-product-status">
                                <option value="ACTIVE">Actif</option>
                                <option value="DRAFT">Brouillon</option>
                                <option value="ARCHIVED">Archivé</option>
                            </select>
                        </div>
                    </div>
                    <p class="text-muted" style="font-size:12px;" id="shopify-product-price-note">Le prix ne peut être défini qu'à la création (pas encore modifiable ici).</p>
                    <button type="submit" class="create-client-btn" id="shopify-product-submit">Créer</button>
                </form>
            </div>
        </div>
    `;
}

function shopifyCancelOrderModalHtml() {
    return `
        <div class="customer-modal-overlay" id="shopify-cancel-order-modal">
            <div class="customer-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3>Annuler la commande <span id="shopify-cancel-order-name"></span></h3>
                        <p>L'annulation est traitée de façon asynchrone par Shopify - elle n'est pas instantanée.</p>
                    </div>
                    <button type="button" class="customer-modal-close" id="shopify-cancel-order-modal-close">×</button>
                </div>
                <form id="shopify-cancel-order-form">
                    <input type="hidden" id="shopify-cancel-order-id">
                    <div class="form-group">
                        <label>Motif</label>
                        <select id="shopify-cancel-order-reason" required>
                            <option value="CUSTOMER">Demande du client</option>
                            <option value="FRAUD">Fraude</option>
                            <option value="INVENTORY">Stock indisponible</option>
                            <option value="PAYMENT_DECLINED">Paiement refusé</option>
                            <option value="STAFF_ERROR">Erreur interne</option>
                            <option value="OTHER">Autre</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" id="shopify-cancel-order-restock" checked> Remettre les articles en stock</label>
                    </div>
                    <div class="form-group">
                        <label><input type="checkbox" id="shopify-cancel-order-notify"> Prévenir le client par email</label>
                    </div>
                    <div class="form-group"><label>Note interne (optionnel)</label><input type="text" maxlength="255" id="shopify-cancel-order-staff-note"></div>
                    <button type="submit" class="create-client-btn" id="shopify-cancel-order-submit">Confirmer l'annulation</button>
                </form>
            </div>
        </div>
    `;
}

async function renderShopify(container) {
    container.innerHTML = `
        <div class="subview-sticky-intro">
            <div class="subview-sticky-intro-top">
                <div class="subview-sticky-intro-main">
                    <div class="subview-sticky-intro-icon"><i class="fa-brands fa-shopify"></i></div>
                    <div class="subview-sticky-intro-body">
                        <h1>Shopify</h1>
                        <p>Produits, commandes et clients de votre boutique Shopify connectée - lecture directe depuis Shopify, jamais stockée côté Xepay ni mélangée à vos objets Stripe.</p>
                    </div>
                </div>
            </div>
        </div>

        <div id="shopify-not-connected"></div>
        <div class="shopify-tabs" id="shopify-tabs" style="display:none;">
            ${SHOPIFY_TABS.map((t, i) => `<button type="button" class="shopify-tab${i === 0 ? " shopify-tab--active" : ""}" data-shopify-tab="${t.key}">${t.label}</button>`).join("")}
        </div>
        <div id="shopify-tab-content"></div>

        ${shopifyCustomerModalHtml()}
        ${shopifyProductModalHtml()}
        ${shopifyCancelOrderModalHtml()}
    `;

    const tabsEl = container.querySelector("#shopify-tabs");
    const contentEl = container.querySelector("#shopify-tab-content");
    let activeTabKey = "produits";

    async function reloadActiveTab() {
        const tab = SHOPIFY_TABS.find((t) => t.key === activeTabKey);
        await tab.render(contentEl);
    }

    // Premier onglet ("Produits") chargé d'office : sert aussi à
    // détecter si la boutique est connectée (404) avant même de
    // proposer "Commandes"/"Clients".
    const connected = await renderShopifyProductsSection(contentEl);
    if (connected === false) {
        container.querySelector("#shopify-not-connected").innerHTML = shopifyNotConnectedCardHtml();
        return;
    }
    tabsEl.style.display = "";

    tabsEl.querySelectorAll("[data-shopify-tab]").forEach((btn) => {
        btn.addEventListener("click", async () => {
            if (btn.classList.contains("shopify-tab--active")) return;
            tabsEl.querySelectorAll(".shopify-tab").forEach((b) => b.classList.remove("shopify-tab--active"));
            btn.classList.add("shopify-tab--active");
            activeTabKey = btn.dataset.shopifyTab;
            await reloadActiveTab();
        });
    });

    /* =====================================================
       MODALE CLIENT (créer / modifier) - delegation depuis `container`
       (jamais re-liée à chaque re-rendu d'onglet, contrairement aux
       lignes du tableau qui elles sont recréées à chaque fetch).
    ===================================================== */
    const customerModal = container.querySelector("#shopify-customer-modal");
    const customerForm = container.querySelector("#shopify-customer-form");

    function openCustomerModal({ id = "", firstName = "", lastName = "", email = "", phone = "" } = {}) {
        container.querySelector("#shopify-customer-modal-title").textContent = id ? "Modifier le client" : "Créer un client";
        container.querySelector("#shopify-customer-submit").textContent = id ? "Enregistrer" : "Créer";
        container.querySelector("#shopify-customer-id").value = id;
        container.querySelector("#shopify-customer-first-name").value = firstName;
        container.querySelector("#shopify-customer-last-name").value = lastName;
        container.querySelector("#shopify-customer-email").value = email;
        container.querySelector("#shopify-customer-phone").value = phone;
        customerModal.classList.add("open");
    }

    container.querySelector("#shopify-customer-modal-close").addEventListener("click", () => customerModal.classList.remove("open"));

    customerForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const customerId = container.querySelector("#shopify-customer-id").value;
        const isEditing = Boolean(customerId);
        const body = {
            first_name: container.querySelector("#shopify-customer-first-name").value.trim() || null,
            last_name: container.querySelector("#shopify-customer-last-name").value.trim() || null,
            email: container.querySelector("#shopify-customer-email").value.trim() || null,
            phone: container.querySelector("#shopify-customer-phone").value.trim() || null,
        };
        try {
            const response = await apiFetch(
                isEditing ? `/shopify/customers/${customerId}` : "/shopify/customers",
                { method: isEditing ? "PATCH" : "POST", body }
            );
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || (isEditing ? "Impossible de modifier le client" : "Impossible de créer le client"));
            showToast(isEditing ? "Client Shopify modifié" : "Client Shopify créé", "success");
            customerModal.classList.remove("open");
            if (activeTabKey === "clients") await reloadActiveTab();
        } catch (error) {
            showToast(error.message || "Erreur lors de l'enregistrement du client", "error");
        }
    });

    /* =====================================================
       MODALE PRODUIT (créer / modifier)
    ===================================================== */
    const productModal = container.querySelector("#shopify-product-modal");
    const productForm = container.querySelector("#shopify-product-form");
    const productPriceGroup = container.querySelector("#shopify-product-price-group");
    const productPriceNote = container.querySelector("#shopify-product-price-note");

    function openProductModal({ id = "", title = "", status = "ACTIVE" } = {}) {
        const isEditing = Boolean(id);
        container.querySelector("#shopify-product-modal-title").textContent = isEditing ? "Modifier le produit" : "Créer un produit";
        container.querySelector("#shopify-product-submit").textContent = isEditing ? "Enregistrer" : "Créer";
        container.querySelector("#shopify-product-id").value = id;
        container.querySelector("#shopify-product-title").value = title;
        container.querySelector("#shopify-product-description").value = "";
        container.querySelector("#shopify-product-price").value = "";
        container.querySelector("#shopify-product-status").value = status || "ACTIVE";
        // Le prix n'est réglable qu'à la création (productCreate ne crée
        // qu'une variante sans prix, voir create_product - productUpdate
        // ne le modifie pas) - masqué en édition plutôt que trompeur.
        productPriceGroup.style.display = isEditing ? "none" : "";
        productPriceNote.style.display = isEditing ? "none" : "";
        productModal.classList.add("open");
    }

    container.querySelector("#shopify-product-modal-close").addEventListener("click", () => productModal.classList.remove("open"));

    productForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const productId = container.querySelector("#shopify-product-id").value;
        const isEditing = Boolean(productId);
        const title = container.querySelector("#shopify-product-title").value.trim();
        if (!title) {
            showToast("Le titre est obligatoire", "error");
            return;
        }
        const body = isEditing
            ? {
                title,
                description: container.querySelector("#shopify-product-description").value.trim() || null,
                status: container.querySelector("#shopify-product-status").value,
            }
            : {
                title,
                description: container.querySelector("#shopify-product-description").value.trim() || null,
                price: Number(container.querySelector("#shopify-product-price").value) || null,
                status: container.querySelector("#shopify-product-status").value,
            };
        try {
            const response = await apiFetch(
                isEditing ? `/shopify/products/${productId}` : "/shopify/products",
                { method: isEditing ? "PATCH" : "POST", body }
            );
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || (isEditing ? "Impossible de modifier le produit" : "Impossible de créer le produit"));
            showToast(isEditing ? "Produit Shopify modifié" : "Produit Shopify créé", "success");
            productModal.classList.remove("open");
            if (activeTabKey === "produits") await reloadActiveTab();
        } catch (error) {
            showToast(error.message || "Erreur lors de l'enregistrement du produit", "error");
        }
    });

    /* =====================================================
       MODALE ANNULATION COMMANDE
    ===================================================== */
    const cancelOrderModal = container.querySelector("#shopify-cancel-order-modal");
    const cancelOrderForm = container.querySelector("#shopify-cancel-order-form");

    function openCancelOrderModal(orderId, orderName) {
        container.querySelector("#shopify-cancel-order-id").value = orderId;
        container.querySelector("#shopify-cancel-order-name").textContent = orderName;
        container.querySelector("#shopify-cancel-order-reason").value = "CUSTOMER";
        container.querySelector("#shopify-cancel-order-restock").checked = true;
        container.querySelector("#shopify-cancel-order-notify").checked = false;
        container.querySelector("#shopify-cancel-order-staff-note").value = "";
        cancelOrderModal.classList.add("open");
    }

    container.querySelector("#shopify-cancel-order-modal-close").addEventListener("click", () => cancelOrderModal.classList.remove("open"));

    cancelOrderForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const orderId = container.querySelector("#shopify-cancel-order-id").value;
        const body = {
            reason: container.querySelector("#shopify-cancel-order-reason").value,
            restock: container.querySelector("#shopify-cancel-order-restock").checked,
            notify_customer: container.querySelector("#shopify-cancel-order-notify").checked,
            staff_note: container.querySelector("#shopify-cancel-order-staff-note").value.trim() || null,
        };
        try {
            const response = await apiFetch(`/shopify/orders/${orderId}/cancel`, { method: "POST", body });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "Impossible d'annuler cette commande");
            // orderCancel est ASYNCHRONE côté Shopify (voir cancel_order,
            // services/shopify_service.py) - jamais "commande annulée"
            // avec certitude ici, seulement "annulation lancée".
            showToast("Annulation lancée - le statut se mettra à jour sur Shopify dans un instant", "success");
            cancelOrderModal.classList.remove("open");
            if (activeTabKey === "commandes") await reloadActiveTab();
        } catch (error) {
            showToast(error.message || "Erreur lors de l'annulation de la commande", "error");
        }
    });

    /* =====================================================
       DÉLÉGATION : boutons "+ Créer"/"Modifier"/"Annuler" injectés
       dynamiquement dans #shopify-tab-content à chaque fetch - jamais
       de addEventListener direct sur ces boutons (ils sont détruits/
       recréés à chaque rendu d'onglet), toujours via `container`, qui
       lui survit pour toute la durée de vie de la vue.
    ===================================================== */
    container.addEventListener("click", (event) => {
        const createCustomerBtn = event.target.closest("#shopify-open-create-customer");
        if (createCustomerBtn) {
            openCustomerModal();
            return;
        }
        const editCustomerBtn = event.target.closest("[data-shopify-edit-customer]");
        if (editCustomerBtn) {
            openCustomerModal({
                id: editCustomerBtn.dataset.shopifyEditCustomer,
                firstName: editCustomerBtn.dataset.firstName || "",
                lastName: editCustomerBtn.dataset.lastName || "",
                email: editCustomerBtn.dataset.email || "",
                phone: editCustomerBtn.dataset.phone || "",
            });
            return;
        }
        const createProductBtn = event.target.closest("#shopify-open-create-product");
        if (createProductBtn) {
            openProductModal();
            return;
        }
        const editProductBtn = event.target.closest("[data-shopify-edit-product]");
        if (editProductBtn) {
            openProductModal({
                id: editProductBtn.dataset.shopifyEditProduct,
                title: editProductBtn.dataset.title || "",
                status: editProductBtn.dataset.status || "ACTIVE",
            });
            return;
        }
        const cancelOrderBtn = event.target.closest("[data-shopify-cancel-order]");
        if (cancelOrderBtn) {
            openCancelOrderModal(cancelOrderBtn.dataset.shopifyCancelOrder, cancelOrderBtn.dataset.orderName || "");
        }
    });
}
