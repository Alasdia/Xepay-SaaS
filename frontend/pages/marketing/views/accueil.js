export const title = "Xepay — Paiements fintech, de l'Afrique de l'Ouest au monde";

export function render() {
  return `
<!-- ─── HERO ─── -->
<section class="hero">
  <div class="hero-inner">
    <!-- TEXT -->
    <div class="hero-text reveal">
      <div class="hero-eyebrow">Né en Afrique de l'Ouest, connecté au monde</div>
      <h1>
        Centralisez vos flux.<br>
        <mark>Automatisez</mark> le reste.
      </h1>
      <p class="hero-desc">
        Xepay donne aux marchands ouest-africains les outils d'une
        plateforme fintech mondiale : recevez des paiements en XOF, USD
        ou EUR et connectez votre business au reste du monde.
      </p>
      <div class="hero-actions">
        <a href="/signup" class="btn-primary">Commencer gratuitement</a>
        <a href="/fonctionnalite" class="btn-ghost">▷ Voir les fonctionnalités</a>
      </div>
      <div class="hero-stats">

        <div class="hero-stat">
          <div class="label">UEMOA → Monde</div>
        </div>

        <div class="hero-stat">
          <div class="label">XOF · USD · EUR</div>
        </div>

        <div class="hero-stat">
          <div class="label">Propulsé par Stripe Connect</div>
        </div>

      </div>
    </div>

    <!-- MOCKUP -->
    <div class="hero-visual reveal" style="transition-delay:0.15s">
      <div class="hero-halo"></div>
      <div class="hero-card">
        <div class="hcard-topbar">
          <div class="hcard-dots">
            <span></span><span></span><span></span>
          </div>
          <div class="hcard-title">app.xepay.finance / dashboard</div>
          <div style="width:60px"></div>
        </div>
        <div class="hcard-body">
          <div class="hcard-balance-label">SOLDE TOTAL</div>
          <div class="hcard-balance"><sub>xof</sub>65 300<span style="font-size:28px;font-family:var(--font-mono)"></span></div>
          <div class="hcard-change">Disponible dans 6j</div>
          <div class="mini-chart">
            <svg viewBox="0 0 320 56" fill="none" preserveAspectRatio="none">
              <defs>
                <linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#f59e0b" stop-opacity="0.35"/>
                  <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <path d="M0,50 C20,45 40,42 60,30 C80,18 100,35 120,28 C140,20 160,32 180,18 C200,6 220,22 240,12 C260,4 280,16 320,8" stroke="#f59e0b" stroke-width="1.5" stroke-linecap="round"/>
              <path d="M0,50 C20,45 40,42 60,30 C80,18 100,35 120,28 C140,20 160,32 180,18 C200,6 220,22 240,12 C260,4 280,16 320,8 L320,56 L0,56Z" fill="url(#cg)"/>
            </svg>
          </div>
          <div class="hcard-txns">
            <div class="hcard-txn">
              <div class="hcard-txn-left">
                <div class="hcard-txn-icon" style="background:rgba(245,158,11,0.12)">🌍</div>
                <div>
                  <div class="hcard-txn-name">Paiement EU</div>
                  <div class="hcard-txn-sub">Il y a 2 min</div>
                </div>
              </div>
              <div class="hcard-txn-amount amt-green">+€1,250.00</div>
            </div>
            <div class="hcard-txn">
              <div class="hcard-txn-left">
                <div class="hcard-txn-icon" style="background:rgba(107,114,128,0.12)">🔁</div>
                <div>
                  <div class="hcard-txn-name">Abonnement SaaS</div>
                  <div class="hcard-txn-sub">Il y a 18 min</div>
                </div>
              </div>
              <div class="hcard-txn-amount amt-green">15500 xof</div>
            </div>
            <div class="hcard-txn">
              <div class="hcard-txn-left">
                <div class="hcard-txn-icon" style="background:rgba(245,158,11,0.12)">↗</div>
                <div>
                  <div class="hcard-txn-name">Virement sortant</div>
                  <div class="hcard-txn-sub">Il y a 1h</div>
                </div>
              </div>
              <div class="hcard-txn-amount amt-red">−€450.00</div>
            </div>
          </div>
          <div class="link-pill">
            <div class="link-pill-text">app.xepay.finance/pay/studio-noé</div>
            <div class="link-pill-copy">COPIER</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ─── CHIFFRES + BARRE DE CONFIANCE ─── -->
<div class="stats-bar">
  <div class="counters-row reveal">
    <div class="counter-item">
      <div class="counter-num"><span class="counter-value" data-target="8">0</span></div>
      <div class="counter-label">pays UEMOA</div>
    </div>
    <div class="counter-item">
      <div class="counter-num"><span class="counter-value" data-target="3">0</span></div>
      <div class="counter-label">devises — XOF · USD · EUR</div>
    </div>
    <div class="counter-item">
      <div class="counter-num"><span class="counter-value" data-target="13">0</span></div>
      <div class="counter-label">moyens de paiement</div>
    </div>
  </div>
  <div class="trust-bar">
    <span class="trust-label">Propulsé par <strong>Stripe</strong></span>
    <div class="trust-logos">
      <img src="/assets/visa.svg" alt="Visa" class="trust-logo">
      <img src="/assets/mastercard.svg" alt="Mastercard" class="trust-logo">
      <img src="/assets/apple-pay.svg" alt="Apple Pay" class="trust-logo">
      <img src="/assets/google-pay.svg" alt="Google Pay" class="trust-logo">
      <img src="/assets/cashapp.svg" alt="Cash App" class="trust-logo">
    </div>
  </div>
</div>

<!-- ─── FEATURE 1 : LIENS DE PAIEMENT ─── -->
<section class="feature-section reveal">
  <div class="feature-text">
    <div class="section-tag">Paiements</div>
    <h2>Créez vos liens <mark>en secondes</mark>.</h2>
    <p>
      Générez des liens de paiement personnalisés, partagez-les 
      partout et encaissez en temps réel — sans intégration technique.
    </p>
    <ul class="feature-checklist">
      <li>Liens multi-devises et multi-pays</li>
      <li>Paiements internationaux instantanés</li>
      <li>Expirations et montants fixes ou libres</li>
      <li>Webhook en temps réel à chaque paiement</li>
    </ul>
    <a href="/signup" class="btn-primary" style="display:inline-flex">Créer un lien →</a>
    <a href="/fonctionnalite" class="guide-link">Lire le guide ›</a>
  </div>
  <div class="feature-mockup">
    <div class="feature-mockup-inner">
      <div class="fmock-header">
        <div class="fmock-title">MES LIENS DE PAIEMENT</div>
        <div class="fmock-status" id="lnk-counter">3 / 10</div>
      </div>
      <div class="fmock-body">
        <form class="lnk-demo-form" id="lnk-demo-form">
          <div class="lnk-demo-field">
            <label for="lnk-amount">Montant</label>
            <input type="number" id="lnk-amount" inputmode="numeric" min="1" step="1" value="150000" required>
          </div>
          <div class="lnk-demo-field lnk-demo-field-currency">
            <label for="lnk-currency">Devise</label>
            <select id="lnk-currency">
              <option value="XOF" selected>XOF</option>
              <option value="EUR">EUR</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <button type="submit" class="lnk-demo-btn" id="lnk-demo-btn">Générer</button>
        </form>
        <div class="lnk-quota">
          <div class="lnk-quota-top"><span>Liens utilisés</span><strong id="lnk-quota-label">3/10</strong></div>
          <div class="lnk-quota-bar"><div class="lnk-quota-fill" id="lnk-quota-fill" style="width:30%"></div></div>
        </div>
        <div class="lnk-list" id="lnk-list">
          <div class="lnk-row lnk-pending">
            <span class="lnk-dot"></span>
            <span class="lnk-url">app.xepay.finance/pay/pl_vbl0qzddig7i…</span>
            <i class="lnk-chevron">›</i>
          </div>
          <div class="lnk-row lnk-paid">
            <span class="lnk-dot"></span>
            <span class="lnk-url">app.xepay.finance/pay/pl_qi4x1zhg3m5…</span>
            <i class="lnk-chevron">›</i>
          </div>
          <div class="lnk-row lnk-pending">
            <span class="lnk-dot"></span>
            <span class="lnk-url">app.xepay.finance/pay/pl_1dqmll3jqlf…</span>
            <i class="lnk-chevron">›</i>
          </div>
        </div>
      </div>
    </div>
    <div class="code-snippet">
      <div class="code-snippet-header">
        <span class="code-dot"></span><span class="code-dot"></span><span class="code-dot"></span>
        <span class="code-snippet-lang">JavaScript</span>
      </div>
      <pre class="code-snippet-body"><code id="lnk-code-body">xepay.paymentLink.create({
  <span class="code-key">amount</span>: <span class="code-val">150000</span>,
  <span class="code-key">currency</span>: <span class="code-str">"XOF"</span>
});</code></pre>
    </div>
  </div>
</section>

<div class="section-glow"></div>

<!-- ─── FEATURE 2 : TRANSACTIONS ─── -->
<section class="feature-section reverse reveal">
  <div class="feature-text">
    <div class="section-tag">Transactions</div>
    <h2>Suivez vos revenus <mark>en direct</mark>.</h2>
    <p>
      Analysez chaque flux financier avec des graphiques
      dynamiques, des filtres avancés et des exports
      comptables automatiques.
    </p>
    <ul class="feature-checklist">
      <li>Dashboard temps réel avec filtres</li>
      <li>Export CSV / PDF pour la comptabilité</li>
      <li>Alertes email configurables</li>
      <li>Historique complet de vos transactions</li>
    </ul>
    <a href="/signup" class="btn-ghost" style="display:inline-flex">Voir un rapport →</a>
  </div>
  <div class="feature-mockup reverse-p">
    <div class="feature-mockup-inner">
      <div class="fmock-header">
        <div class="fmock-title">PAIEMENTS</div>
        <div class="fmock-status">8 transactions</div>
      </div>
      <div class="fmock-body">
        <div class="txn-kpis">
          <div class="txn-kpi active"><span>Tous</span><strong>8</strong></div>
          <div class="txn-kpi"><span>Réussis</span><strong>8</strong></div>
          <div class="txn-kpi"><span>En échec</span><strong>0</strong></div>
        </div>
        <div class="txn-table">
          <div class="txn-thead"><span>Client</span><span>Moyen</span><span>Brut</span><span>Net</span></div>
          <div class="txn-trow">
            <span class="txn-client">alasndia04@gmail.com</span>
            <span class="txn-method"><span class="txn-card txn-card-mc"></span>···4444</span>
            <span class="txn-amount">23,00 USD</span>
            <span class="txn-net">21,62 USD</span>
          </div>
          <div class="txn-trow">
            <span class="txn-client">leona.bravo@exemple.com</span>
            <span class="txn-method"><span class="txn-card txn-card-visa"></span>···4242</span>
            <span class="txn-amount">180,00 USD</span>
            <span class="txn-net">169,20 USD</span>
          </div>
          <div class="txn-trow">
            <span class="txn-client">leona.bravo@exemple.com</span>
            <span class="txn-method"><span class="txn-card txn-card-cash"></span>Cash App</span>
            <span class="txn-amount">78,00 USD</span>
            <span class="txn-net">73,32 USD</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<div class="section-glow"></div>

<!-- ─── FEATURE 3 : SOLDE & RETRAITS ─── -->
<section class="feature-section reveal">
  <div class="feature-text">
    <div class="section-tag">Solde</div>
    <h2>Pilotez votre solde <mark>en temps réel</mark>.</h2>
    <p>
      Visualisez vos fonds disponibles et verrouillés, détaillés par
      source de paiement, et retirez-les vers votre compte bancaire
      quand vous le décidez.
    </p>
    <ul class="feature-checklist">
      <li>Détail par source : liens, abonnements, factures</li>
      <li>Montant verrouillé vs disponible, en un coup d'œil</li>
      <li>Retrait à la demande vers votre compte Europe ou US</li>
      <li>Historique complet de chaque retrait</li>
    </ul>
    <a href="/signup" class="btn-primary" style="display:inline-flex">Voir mon solde →</a>
  </div>
  <div class="feature-mockup">
    <div class="feature-mockup-inner">
      <div class="fmock-header">
        <div class="fmock-title">SOLDE</div>
        <div class="fmock-status">USD</div>
      </div>
      <div class="fmock-body">
        <div class="bal-sources">
          <div class="bal-source-row active"><span>Solde principal</span><strong>1 847,30 $US</strong></div>
          <div class="bal-source-row"><span>Paiements par liens</span><strong>1 240,00 $US</strong></div>
          <div class="bal-source-row"><span>Abonnements</span><strong>512,50 $US</strong></div>
          <div class="bal-source-row"><span>Factures</span><strong>94,80 $US</strong></div>
        </div>
        <div class="bal-main">
          <div class="bal-amount">1 847,30 $US</div>
          <div class="bal-bar"><div class="bal-bar-available" style="width:78%"></div><div class="bal-bar-locked" style="width:22%"></div></div>
          <div class="bal-row"><span><span class="bal-dot bal-dot-locked"></span>Montant verrouillé</span><strong>406,40 $US</strong></div>
          <div class="bal-row"><span><span class="bal-dot bal-dot-available"></span>Montant disponible</span><strong>1 440,90 $US</strong></div>
          <button class="bal-withdraw-btn">Retirer des fonds</button>
        </div>
      </div>
    </div>
  </div>
</section>

<div class="section-glow"></div>

<!-- ─── FEATURE 4 : COMMERCE ─── -->
<section class="feature-section reverse reveal">
  <div class="feature-text">
    <div class="section-tag">Commerce</div>
    <h2>Facturez vos <mark>propres clients</mark>.</h2>
    <p>
      Au-delà de votre propre abonnement Xepay, créez le vôtre pour vos
      clients : fiches clients, catalogue produits, abonnements
      récurrents et factures — une vraie suite commerciale intégrée.
    </p>
    <ul class="feature-checklist">
      <li>Fiches clients avec historique de paiement</li>
      <li>Catalogue de produits et tarifs</li>
      <li>Abonnements récurrents pour vos propres clients</li>
      <li>Alertes de fraude et litiges Stripe Radar</li>
    </ul>
    <a href="/signup" class="btn-ghost" style="display:inline-flex">Découvrir Commerce →</a>
  </div>
  <div class="feature-mockup reverse-p">
    <div class="feature-mockup-inner">
      <div class="fmock-header">
        <div class="fmock-title">CLIENTS</div>
        <div class="fmock-status">3 client(s)</div>
      </div>
      <div class="fmock-body">
        <div class="txn-kpis">
          <div class="txn-kpi active"><span>Tous</span><strong>3</strong></div>
          <div class="txn-kpi"><span>Soldes restants</span><strong>0</strong></div>
        </div>
        <div class="txn-table">
          <div class="txn-thead"><span>Client</span><span>Pays</span><span>Dépensé</span><span>Paiements</span></div>
          <div class="txn-trow">
            <span class="txn-client">Moussa Ndiaye</span>
            <span class="txn-method">US</span>
            <span class="txn-amount">0,00</span>
            <span class="txn-net">0</span>
          </div>
          <div class="txn-trow">
            <span class="txn-client">Malick Ly</span>
            <span class="txn-method">SN</span>
            <span class="txn-amount">0,00 USD</span>
            <span class="txn-net">0</span>
          </div>
          <div class="txn-trow">
            <span class="txn-client">Leona Bravo</span>
            <span class="txn-method">—</span>
            <span class="txn-amount">1 021,00 USD</span>
            <span class="txn-net">7</span>
          </div>
        </div>
        <div class="fmock-add-btn">+ Créer un client</div>
      </div>
    </div>
  </div>
</section>

<div class="section-glow"></div>

<!-- ─── GRILLE FONCTIONNALITÉS ─── -->
<section class="highlights-section reveal">
  <div class="highlights-label">
    <div class="section-tag">Plateforme</div>
    <h3>Tout ce dont vous avez besoin.</h3>
  </div>
  <div class="highlights-grid">
    <div class="highlight-card">
      <div class="hl-icon">⚡</div>
      <div class="hl-title">Paiements confirmés instantanément</div>
      <div class="hl-desc">Le paiement de votre client est validé en quelques secondes. Retirez vos fonds à la demande vers votre compte bancaire.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-icon">👥</div>
      <div class="hl-title">Équipe & rôles</div>
      <div class="hl-desc">Invitez votre équipe avec des rôles définis (admin, manager, lecture) — accès tracés et sécurisés.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-icon">🔐</div>
      <div class="hl-title">Sécurité du compte</div>
      <div class="hl-desc">Double authentification, clés d'accès (passkeys) et connexion Google pour protéger votre compte.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-icon">🛡️</div>
      <div class="hl-title">Sécurité des paiements</div>
      <div class="hl-desc">Paiements traités par Stripe, certifié PCI DSS niveau 1. 3D Secure et détection de fraude Stripe Radar.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-icon">⚙️</div>
      <div class="hl-title">Webhooks</div>
      <div class="hl-desc">Recevez vos événements de paiement en temps réel pour vos propres intégrations.</div>
    </div>
    <div class="highlight-card">
      <div class="hl-icon">🏛️</div>
      <div class="hl-title">Pas encore de société US ?</div>
      <div class="hl-desc">Formez votre LLC via Firstbase ou Stripe Atlas, directement depuis vos paramètres Xepay.</div>
    </div>
  </div>
</section>

<!-- ─── CTA ─── -->
<section class="cta-section">
  <div class="cta-inner reveal">
    <h2>Prêt à <mark>encaisser le monde</mark> ?</h2>
    <p>Rejoignez les marchands qui font confiance à Xepay pour encaisser leurs paiements à travers l'UEMOA. Inscription gratuite, sans engagement.</p>
    <div class="cta-actions">
      <a href="/signup" class="btn-primary" style="font-size:15px;padding:17px 34px">Créer mon compte — Gratuit</a>
      <a href="mailto:support@alasdia.com" class="btn-ghost" style="font-size:14px;padding:16px 28px">Contacter l'équipe</a>
    </div>
  </div>
</section>
`;
}

// Démo interactive de la Feature 1 (Liens) - purement côté client,
// aucun appel réseau : génère un faux lien + met à jour le quota et
// l'extrait de code en direct à partir du formulaire.
const LINK_LIMIT = 10;
let linkCount = 3;

function randomLinkId() {
  return "pl_" + Array.from({ length: 13 }, () => "0123456789abcdefghijklmnopqrstuvwxyz"[Math.floor(Math.random() * 36)]).join("");
}

function updateCodeSnippet(root, amount, currency) {
  const code = root.querySelector("#lnk-code-body");
  if (!code) return;
  code.innerHTML = `xepay.paymentLink.create({
  <span class="code-key">amount</span>: <span class="code-val">${amount}</span>,
  <span class="code-key">currency</span>: <span class="code-str">"${currency}"</span>
});`;
}

// Compteur animé des chiffres sous le hero - se déclenche une seule
// fois, au moment où la ligne entre dans le viewport.
function animateCounters(root) {
  const items = root.querySelectorAll(".counter-value");
  if (!items.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.target, 10) || 0;
      const duration = 900;
      const start = performance.now();
      function step(now) {
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = Math.round(eased * target);
        if (t < 1) requestAnimationFrame(step);
        else el.textContent = target;
      }
      requestAnimationFrame(step);
      io.unobserve(el);
    });
  }, { threshold: 0.4 });
  items.forEach((el) => io.observe(el));
}

export function mount(root) {
  animateCounters(root);

  const form = root.querySelector("#lnk-demo-form");
  const amountInput = root.querySelector("#lnk-amount");
  const currencySelect = root.querySelector("#lnk-currency");
  const btn = root.querySelector("#lnk-demo-btn");
  const list = root.querySelector("#lnk-list");
  const counter = root.querySelector("#lnk-counter");
  const quotaLabel = root.querySelector("#lnk-quota-label");
  const quotaFill = root.querySelector("#lnk-quota-fill");
  if (!form || !list) return;

  linkCount = 3;

  function syncCode() {
    const amount = amountInput.value || "0";
    updateCodeSnippet(root, amount, currencySelect.value);
  }

  function syncQuota() {
    const label = `${linkCount}/${LINK_LIMIT}`;
    counter.textContent = `${linkCount} / ${LINK_LIMIT}`;
    quotaLabel.textContent = label;
    quotaFill.style.width = `${Math.min(100, (linkCount / LINK_LIMIT) * 100)}%`;
    if (linkCount >= LINK_LIMIT) {
      btn.disabled = true;
      btn.textContent = "Limite atteinte";
    } else {
      btn.disabled = false;
      btn.textContent = "Générer";
    }
  }

  amountInput.addEventListener("input", syncCode);
  currencySelect.addEventListener("change", syncCode);

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (linkCount >= LINK_LIMIT) return;

    const row = document.createElement("div");
    row.className = "lnk-row lnk-pending lnk-row-new";
    row.innerHTML = `
      <span class="lnk-dot"></span>
      <span class="lnk-url">app.xepay.finance/pay/${randomLinkId()}…</span>
      <i class="lnk-chevron">›</i>
    `;
    list.prepend(row);

    linkCount += 1;
    syncQuota();
  });

  syncCode();
  syncQuota();
}
