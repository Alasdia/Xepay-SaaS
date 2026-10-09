import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";
import { showToast } from "../shared/toast.js";

export async function mount(container, params = {}) {

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

        default:
            await renderClients(content);
    }
}

/* =========================================================
   CLIENTS
========================================================= */
async function renderClients(container) {

    container.innerHTML = `
        <div class="page-header">
            <div>
                <h1>Clients</h1>
                <p>Gérez les clients de votre activité.</p>
            </div>

            <button
                type="button"
                class="create-client-btn"
                id="open-create-client"
            >
                + Créer un client
            </button>
        </div>

        <div id="clients-list"></div>

        <!-- MODAL CRÉATION CLIENT -->
        <div class="customer-modal-overlay" id="create-client-modal">
            <div class="customer-modal customer-create-modal">
                <div class="customer-modal-header">
                    <div>
                        <h3>Créer un client</h3>
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

                <!-- =================================================
                 INFORMATIONS DU CLIENT
                ================================================== -->

                <div class="customer-form-section">
                    <div class="customer-form-section-title">
                        Informations du client
                    </div>
                    <div class="customer-form-grid customer-form-grid-2">
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
                                required
                            >
                        </div>
                        </div>
                        <div class="customer-form-grid customer-form-grid-2">
                            <div class="form-group">
                                <label for="client-email">
                                    Email
                                </label>
                                <input
                                    type="email"
                                    id="client-email"
                                    autocomplete="email"
                                    required
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
                    </div>
                    <!-- =================================================
                      ADRESSE DE FACTURATION
                    ================================================== -->
                    <div class="customer-form-section">
                        <div class="customer-form-section-title">
                            Adresse de facturation
                        </div>
                        <div class="form-group">
                            <label for="billing-country">
                                Pays
                            </label>
                            <select id="billing-country">
                                <option value="">Sélectionner un pays</option>
                                <option value="SN">Sénégal</option>
                                <option value="CI">Côte d’Ivoire</option>
                                <option value="ML">Mali</option>
                                <option value="BF">Burkina Faso</option>
                                <option value="BJ">Bénin</option>
                                <option value="TG">Togo</option>
                                <option value="FR">France</option>
                                <option value="US">États-Unis</option>
                                <option value="GB">Royaume-Uni</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="billing-line1">
                                Adresse
                            </label>
                            <input
                                type="text"
                                id="billing-line1"
                                autocomplete="address-line1"
                            >
                        </div>
                        <div class="form-group">
                            <label for="billing-line2">
                                Appartement, unité, bâtiment, complément
                            </label>
                            <input
                                type="text"
                                id="billing-line2"
                                autocomplete="address-line2"
                            >
                        </div>
                        <div class="customer-form-grid customer-form-grid-2">
                            <div class="form-group">
                               <label for="billing-postal-code">
                                    Code postal
                                </label>
                                <input
                                    type="text"
                                    id="billing-postal-code"
                                    autocomplete="postal-code"
                                >
                            </div>
                            <div class="form-group">
                                <label for="billing-city">
                                    Ville
                                </label>
                                <input
                                    type="text"
                                    id="billing-city"
                                    autocomplete="address-level2"
                                >
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="billing-state">
                                État / Région
                            </label>
                            <input
                                type="text"
                                id="billing-state"
                                autocomplete="address-level1"
                            >
                        </div>
                    </div>

                    <!-- =================================================
                      ADRESSE DE LIVRAISON
                    ================================================== -->

                    <div class="customer-form-section">
                        <div class="customer-form-section-title">
                            Adresse de livraison
                        </div>
                        <label class="customer-checkbox-row">
                            <input
                                type="checkbox"
                                id="shipping-same-as-billing"
                            >
                            <span>
                                Identique à l’adresse de facturation
                            </span>
                        </label>
                        <div id="shipping-fields">
                            <div class="form-group">
                                <label for="shipping-name">
                                    Nom du destinataire
                                </label>
                                <input
                                    type="text"
                                    id="shipping-name"
                                    autocomplete="shipping name"
                                >
                            </div>
                            <div class="form-group">
                                <label for="shipping-country">
                                    Pays
                                </label>
                                <select id="shipping-country">
                                    <option value="">
                                        Sélectionner un pays
                                    </option>
                                    <option value="SN">Sénégal</option>
                                    <option value="CI">Côte d’Ivoire</option>
                                    <option value="ML">Mali</option>
                                    <option value="BF">Burkina Faso</option>
                                    <option value="BJ">Bénin</option>
                                    <option value="TG">Togo</option>
                                    <option value="FR">France</option>
                                    <option value="US">États-Unis</option>
                                    <option value="GB">Royaume-Uni</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="shipping-line1">
                                    Adresse
                                </label>
                                <input
                                    type="text"
                                    id="shipping-line1"
                                    autocomplete="shipping address-line1"
                                >
                            </div>
                            <div class="form-group">
                                <label for="shipping-line2">
                                    Appartement, unité, bâtiment, complément
                                </label>
                                <input
                                    type="text"
                                    id="shipping-line2"
                                    autocomplete="shipping address-line2"
                                >
                            </div>
                            <div class="customer-form-grid customer-form-grid-2">
                                <div class="form-group">
                                    <label for="shipping-postal-code">
                                        Code postal
                                    </label>
                                    <input
                                        type="text"
                                        id="shipping-postal-code"
                                        autocomplete="shipping postal-code"
                                    >
                                </div>
                                <div class="form-group">
                                    <label for="shipping-city">
                                        Ville
                                    </label>
                                    <input
                                        type="text"
                                        id="shipping-city"
                                        autocomplete="shipping address-level2"
                                    >
                                </div>
                            </div>
                            <div class="form-group">
                                <label for="shipping-state">
                                    État / Région
                                </label>
                                <input
                                    type="text"
                                    id="shipping-state"
                                    autocomplete="shipping address-level1"
                                >
                            </div>
                            <div class="form-group">
                                <label for="shipping-phone">
                                    Téléphone
                                </label>
                                <input
                                    type="tel"
                                    id="shipping-phone"
                                    autocomplete="shipping tel"
                                >
                            </div>
                        </div>
                    </div>

                    <!-- =================================================
                      PRÉFÉRENCES
                    ================================================== -->

                    <div class="customer-form-section">
                        <div class="customer-form-section-title">
                            Préférences
                        </div>
                        <div class="form-group">
                            <label for="client-language">
                                Langue
                            </label>
                            <select id="client-language">
                                <option value="fr-FR">
                                    Français
                                </option>
                                <option value="en">
                                    English
                                </option>
                            </select>
                        </div>
                    </div>

                    <!-- =================================================
                      ACTIONS
                    ================================================== -->

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

    const form =
        container.querySelector("#create-client-form");

    /* =====================================================
       OUVRIR / FERMER MODAL CRÉATION
    ===================================================== */

    container
        .querySelector("#open-create-client")
        .addEventListener("click", () => {
            createModal.classList.add("open");
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

            if (!customers.length) {

                list.innerHTML = `
                    <div class="commerce-card">
                        <p>Aucun client pour le moment.</p>
                    </div>
                `;

                return;
            }

            list.innerHTML = `
                <div class="table-wrap">

                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <div>
                            <div class="table-title">Clients</div>
                            <div class="page-subtitle">
                                ${customers.length} client(s)
                            </div>
                        </div>
                    </div>

                    <div id="customers-scroll-box">

                        <table class="table">

                            <thead>
                                <tr>
                                    <th>Client</th>
                                    <th>Identifiant</th>
                                    <th>Email</th>
                                    <th>Téléphone</th>
                                    <th>Pays</th>
                                    <th>Moyen de paiement</th>
                                    <th>Créé le</th>
                                    <th>Total dépensé</th>
                                    <th>Paiements</th>
                                    <th>Remboursements</th>
                                    <th>Litiges</th>
                                    <th>Dernier paiement</th>
                                    <th>Statut</th>
                                    <th></th>
                                </tr>
                            </thead>

                            <tbody>

                                ${customers.map(customer => `

                                    <tr>

                                        <td>
                                            ${customer.name || "—"}
                                        </td>

                                        <td>
                                            ${customer.id || "—"}
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
                                                customer.created
                                                    ? new Date(
                                                        customer.created * 1000
                                                    ).toLocaleString("fr-FR")
                                                    : "—"
                                            }
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
                                            ${
                                                customer.last_payment_at
                                                    ? new Date(
                                                        customer.last_payment_at * 1000
                                                    ).toLocaleString("fr-FR")
                                                    : "—"
                                            }
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
                                            <button
                                                type="button"
                                                class="customer-details-btn"
                                                data-customer-id="${customer.id}"
                                            >
                                                Détails
                                            </button>
                                        </td>

                                    </tr>

                                `).join("")}

                            </tbody>

                        </table>

                    </div>
                </div>
            `;

            /* =================================================
               BOUTONS DÉTAILS
            ================================================= */

            list
                .querySelectorAll(".customer-details-btn")
                .forEach(button => {

                    button.addEventListener("click", () => {

                        const customer = customers.find(
                            item =>
                                item.id ===
                                button.dataset.customerId
                        );

                        if (!customer) return;

                        showCustomerDetails(customer);
                    });
                });

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
                        ${
                            customer.created
                                ? new Date(
                                    customer.created * 1000
                                ).toLocaleString("fr-FR")
                                : "—"
                        }
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

        `;

        detailsModal.classList.add("open");
    }

    /* =====================================================
       CRÉATION CLIENT
    ===================================================== */

    form.addEventListener("submit", async (event) => {

        event.preventDefault();

        const name =
            container
                .querySelector("#client-name")
                .value
                .trim();

        const email =
            container
                .querySelector("#client-email")
                .value
                .trim();

        const phone =
            container
                .querySelector("#client-phone")
                .value
                .trim();

        try {

            const response = await apiFetch(
                "/stripe/connect/customers",
                {
                    method: "POST",
                    body: {
                        name,
                        email,
                        phone: phone || null
                    }
                }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de créer le client"
                );
            }

            showToast(
                "Client créé avec succès",
                "success"
            );

            form.reset();

            createModal.classList.remove("open");

            await loadCustomers();

        } catch (error) {

            console.error(error);

            showToast(
                error.message ||
                "Erreur lors de la création du client",
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
        <div class="page-header">

            <div>
                <h1>Produits</h1>
                <p>Gérez les produits et les tarifs de votre activité.</p>
            </div>

            <button
                type="button"
                class="create-client-btn"
                id="open-create-product"
            >
                + Créer un produit
            </button>

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

                        <div class="form-group">

                            <label>Intervalle</label>

                            <select id="product-interval">

                                <option value="month">
                                    Mensuel
                                </option>

                                <option value="year">
                                    Annuel
                                </option>

                                <option value="week">
                                    Hebdomadaire
                                </option>

                            </select>

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


            if (!products.length) {

                list.innerHTML = `
                    <div class="commerce-card">
                        <p>
                            Aucun produit pour le moment.
                        </p>
                    </div>
                `;

                return;

            }


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
                                ${products.length} produit(s)
                            </div>
                        </div>
                    </div>
                    <div id="customers-scroll-box">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Produit</th>
                                    <th>Identifiant</th>
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
                                ${products.map(product => {
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
                                                            : interval;
                                        } else {
                                            recurringText =
                                                `Tous les ${count} ${interval}`;
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
                                                <code class="customer-id">
                                                    ${product.id || "—"}
                                                </code>
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
                                                ${price?.type || "—"}
                                            </td>
                                            <td>
                                                ${recurringText}
                                            </td>
                                            <td>
                                                ${
                                                    product.created
                                                        ? new Date(
                                                            product.created * 1000
                                                        ).toLocaleString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }
                                            </td>
                                            <td>
                                                ${
                                                    product.updated
                                                        ? new Date(
                                                            product.updated * 1000
                                                        ).toLocaleString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }
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
                                                <button
                                                    type="button"
                                                    class="customer-details-btn product-details-btn"
                                                    data-product-id="${product.id}"
                                                >
                                                    Détails
                                                </button>
                                            </td>
                                        </tr>
                                    `;
                                }).join("")}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            /* =================================================
               BOUTONS DÉTAILS
            ================================================= */

            list
                .querySelectorAll(".product-details-btn")
                .forEach(button => {

                    button.addEventListener(
                        "click",
                        () => {

                            const product =
                                products.find(
                                    item =>
                                        item.id ===
                                        button.dataset.productId
                                );


                            if (!product) return;


                            showProductDetails(product);

                        }
                    );

                });


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
                        ${
                            product.created
                                ? new Date(
                                    product.created * 1000
                                ).toLocaleString("fr-FR")
                                : "—"
                        }
                    </strong>

                </div>


                <div class="customer-detail-item">

                    <span>Modifié le</span>

                    <strong>
                        ${
                            product.updated
                                ? new Date(
                                    product.updated * 1000
                                ).toLocaleString("fr-FR")
                                : "—"
                        }
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
                                                price.recurring
                                                    ? `${price.recurring.interval} × ${price.recurring.interval_count || 1}`
                                                    : "—"
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

        `;


        detailsModal.classList.add("open");

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
                                        : null
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
        <div class="page-header">

            <div>
                <h1>Abonnements</h1>
                <p>Créez et gérez les abonnements de vos clients.</p>
            </div>

            <button
                type="button"
                class="create-client-btn"
                id="open-create-subscription-modal"
            >
                + Créer un abonnement
            </button>

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


    createModal.addEventListener(
        "click",
        event => {

            if (
                event.target === createModal
            ) {

                createModal.classList.remove("open");

            }

        }
    );


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
                                        : interval;

                    } else {

                        recurringText =
                            `Tous les ${intervalCount} ${interval}`;

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


            if (!subscriptions.length) {

                list.innerHTML = `
                    <div class="commerce-card">

                        <p>
                            Aucun abonnement pour le moment.
                        </p>

                    </div>
                `;

                return;

            }


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

                                ${subscriptions.length}
                                abonnement(s)

                            </div>

                        </div>

                    </div>


                    <div id="customers-scroll-box">

                        <table class="table">

                            <thead>

                                <tr>

                                    <th>Client</th>

                                    <th>Identifiant</th>

                                    <th>Montant</th>

                                    <th>Fréquence</th>

                                    <th>Statut</th>

                                    <th>Mode de paiement</th>

                                    <th>Début</th>

                                    <th>Prochaine échéance</th>

                                    <th>Créé le</th>

                                </tr>

                            </thead>


                            <tbody>

                                ${subscriptions.map(subscription => {

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
                                                ${customerName}
                                            </td>


                                            <td>

                                                <code class="customer-id">
                                                    ${subscription.id}
                                                </code>

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

                                                <span
                                                    class="status-badge ${statusClass}"
                                                >
                                                    ${statusText}
                                                </span>

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

                                                ${
                                                    subscription.start_date
                                                        ? new Date(
                                                            subscription.start_date * 1000
                                                        ).toLocaleDateString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }

                                            </td>


                                            <td>

                                                ${
                                                    subscription.items?.data?.[0]?.current_period_end

                                                        ? new Date(
                                                            subscription.items.data[0].current_period_end * 1000
                                                        ).toLocaleDateString(
                                                            "fr-FR"
                                                        )

                                                        : "—"
                                                }

                                            </td>


                                            <td>

                                                ${
                                                    subscription.created

                                                        ? new Date(
                                                            subscription.created * 1000
                                                        ).toLocaleString(
                                                            "fr-FR"
                                                        )

                                                        : "—"
                                                }

                                            </td>

                                        </tr>

                                    `;

                                }).join("")}

                            </tbody>

                        </table>

                    </div>

                </div>

            `;


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
        <div class="page-header">
            <div>
                <h1>Factures</h1>
                <p>Créez et gérez les factures de vos clients.</p>
            </div>
            <button
                type="button"
                class="create-client-btn"
                id="open-create-invoice-modal"
            >
                + Créer une facture
            </button>
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
    createModal.addEventListener("click", (event) => {
        if (event.target === createModal) {
            createModal.classList.remove("open");
        }
    });

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

                    if (price.active) {

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
            if (!response.ok) {
                throw new Error(
                    response.status === 401
                        ? "Votre session a expiré. Veuillez vous reconnecter."
                        : data.detail || "Impossible de récupérer les factures"
                );
            }
            const invoices =
                data.data || [];
            if (!invoices.length) {
                list.innerHTML = `
                    <div class="commerce-card">
                        <p>
                            Aucune facture pour le moment.
                        </p>
                    </div>
                `;
                return;
            }
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
                                ${invoices.length}
                                facture(s)
                            </div>

                        </div>

                    </div>


                    <div id="customers-scroll-box">

                        <table class="table">

                            <thead>

                                <tr>

                                    <th>Client</th>

                                    <th>Facture</th>

                                    <th>Montant dû</th>

                                    <th>Montant payé</th>

                                    <th>Statut</th>

                                    <th>Encaissement</th>

                                    <th>Échéance</th>

                                    <th>Créée le</th>

                                    <th></th>

                                </tr>

                            </thead>


                            <tbody>

                                ${invoices.map(invoice => {

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

                                                ${invoice.customer || "—"}

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

                                                <span
                                                    class="status-badge ${statusClass}"
                                                >
                                                    ${statusText}
                                                </span>

                                            </td>


                                            <td>
                                                ${
                                                    invoice.collection_method ||
                                                    "—"
                                                }
                                            </td>


                                            <td>

                                                ${
                                                    invoice.due_date
                                                        ? new Date(
                                                            invoice.due_date * 1000
                                                        ).toLocaleDateString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }

                                            </td>


                                            <td>

                                                ${
                                                    invoice.created
                                                        ? new Date(
                                                            invoice.created * 1000
                                                        ).toLocaleString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }

                                            </td>


                                            <td>

                                                ${
                                                    invoice.hosted_invoice_url
                                                        ? `
                                                            <a
                                                                href="${invoice.hosted_invoice_url}"
                                                                target="_blank"
                                                                rel="noopener noreferrer"
                                                                class="customer-details-btn"
                                                            >
                                                                Voir
                                                            </a>
                                                        `
                                                        : "—"
                                                }

                                            </td>

                                        </tr>

                                    `;

                                }).join("")}

                            </tbody>

                        </table>

                    </div>

                </div>

            `;


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
        <div class="page-header">
            <div>
                <h1>Moyens de paiement</h1>
                <p>
                    Configuration des moyens de paiement de votre compte Stripe connecté.
                </p>
            </div>
        </div>

        <!-- KPI : ZONE INDÉPENDANTE DU TABLEAU -->
        <div id="payment-methods-summary"></div>

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

        function renderTable(filter = "all") {

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

                                        ? filteredMethods.map(
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
            `;
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
        <div class="page-header">
            <div>
                <h1>Risque</h1>
                <p>
                    Litiges et alertes de risque envoyés par Stripe
                    pour votre compte connecté.
                </p>
            </div>
        </div>

        <div id="risk-list"></div>
    `;

    async function loadRisk() {

        const list = container.querySelector("#risk-list");

        list.innerHTML = `
            <div class="commerce-card">
                <p>Chargement des données de risque...</p>
            </div>
        `;

        try {

            const response = await apiFetch(
                "/stripe/connect/risk"
            );

            const data = await response.json();

            console.log(
                "DONNÉES STRIPE — RISQUE :",
                data
            );

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    "Impossible de récupérer les données de risque"
                );
            }

            const disputes = data.data || [];

            if (!disputes.length) {

                list.innerHTML = `
                    <div class="commerce-card">
                        <p>
                            Aucun litige ni alerte de risque pour le moment.
                        </p>
                    </div>
                `;

                return;
            }

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

            const SUCCESS_STATUSES = [
                "won",
                "warning_closed",
                "charge_refunded"
            ];

            list.innerHTML = `
                <div class="table-wrap">

                    <div class="d-flex justify-content-between align-items-center mb-3">

                        <div>
                            <div class="table-title">
                                Litiges
                            </div>

                            <div class="page-subtitle">
                                ${disputes.length} litige(s)
                            </div>
                        </div>

                    </div>

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

                                    const amount =
                                        dispute.amount != null
                                            ? (
                                                dispute.amount / 100
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
                                            dispute.currency || ""
                                        ).toUpperCase();

                                    const statusClass =
                                        SUCCESS_STATUSES.includes(
                                            dispute.status
                                        )
                                            ? "status-success"
                                            : "status-danger";

                                    const evidenceDueBy =
                                        dispute.evidence_details?.due_by;

                                    return `
                                        <tr>

                                            <td>
                                                <code class="customer-id">
                                                    ${dispute.id || "—"}
                                                </code>
                                            </td>

                                            <td>
                                                <code class="customer-id">
                                                    ${
                                                        dispute.charge || "—"
                                                    }
                                                </code>
                                            </td>

                                            <td>
                                                <span class="amount-cell">
                                                    ${amount}
                                                </span>

                                                <span class="amount-currency">
                                                    ${currency}
                                                </span>
                                            </td>

                                            <td>
                                                ${dispute.reason || "—"}
                                            </td>

                                            <td>
                                                <span class="status-badge ${
                                                    statusClass
                                                }">
                                                    ${
                                                        STATUS_LABELS[
                                                            dispute.status
                                                        ]
                                                        ||
                                                        dispute.status
                                                        ||
                                                        "—"
                                                    }
                                                </span>
                                            </td>

                                            <td>
                                                ${
                                                    dispute.created
                                                        ? new Date(
                                                            dispute.created * 1000
                                                        ).toLocaleString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }
                                            </td>

                                            <td>
                                                ${
                                                    evidenceDueBy
                                                        ? new Date(
                                                            evidenceDueBy * 1000
                                                        ).toLocaleString(
                                                            "fr-FR"
                                                        )
                                                        : "—"
                                                }
                                            </td>

                                        </tr>
                                    `;

                                }).join("")}

                            </tbody>

                        </table>

                    </div>

                </div>
            `;

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