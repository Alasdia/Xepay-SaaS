// Vue "API Access" — port fidèle de API.html + API.js.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";

const TEMPLATE = `
<div id="featureLock" class="feature-lock d-none">
  <div class="feature-lock-card">
    <div class="lock-icon"><i class="fa-solid fa-lock"></i></div>
    <h2>API Access</h2>
    <p>Débloquez les clés API, webhooks et logs temps réel avec le plan Pro.</p>
    <button class="btn btn-warning fw-bold" onclick="upgrade('pro')">⚡ Passer au Pro</button>
  </div>
</div>
<div id="api-content">
<div class="mb-4">
  <h1 style="font-size:24px;font-weight:700;"><i class="fa-solid fa-code"></i> API Access <span class="badge pro">PRO</span></h1>
  <p class="muted" style="font-size:14px;margin-top:6px;">Gérez vos clés API et configurez vos webhooks pour intégrer Xepay dans vos applications.</p>
</div>
<div class="row g-3 mb-4">
  <div class="col-md-4">
    <div class="card-dark">
      <div class="card-title-small">Appels API </div>
      <div class="stat-value cyan" id="callsThisMonth"></div>
      <div class="muted" id="growthText"></div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card-dark">
      <div class="card-title-small">Taux de succès</div>
      <div class="stat-value green" id="successRate">0%</div>
      <div class="muted" id="errorsText" style="font-size:12px;margin-top:4px;"></div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card-dark">
      <div class="card-title-small">Webhooks actifs</div>
      <div class="stat-value yellow" id="activeWebhooks"></div>
      <div class="muted" id="webhookText"></div>
    </div>
  </div>
</div>
<div class="row g-3 mb-4">
  <div class="col-md-6">
    <div class="card-dark">
      <div class="card-title-small"><i class="fa-solid fa-key"></i> Clés API</div>
      <div class="key-row">
        <span class="key-label">Publique</span>
        <span class="key-value" id="pubKey">Chargement...</span>
        <button class="icon-btn" onclick="copyKey('pubKey')"><i class="fa-regular fa-copy"></i></button>
      </div>
      <div class="key-row">
        <span class="key-label">Secrète</span>
        <span class="key-value secret" id="secKey">••••••••••••••••</span>
        <button class="icon-btn" id="toggleBtn" onclick="toggleSecret()"><i class="fa-regular fa-eye"></i></button>
        <button class="icon-btn" onclick="copyKey('secKey')"><i class="fa-regular fa-copy"></i></button>
      </div>
      <div class="d-flex gap-2 mt-3">
        <button class="btn-api btn-blue" onclick="regenKey()"><i class="fa-solid fa-rotate"></i> Régénérer</button>
        <button class="btn-api btn-out" onclick="copyKey('pubKey')"><i class="fa-regular fa-copy"></i> Copier</button>
      </div>
      <div style="margin-top:14px;padding-top:12px;border-top:1px solid #2a2f5e;font-size:12px;">
        <span class="muted">Dernière utilisation :</span><br>
        <span id="lastUsedTime">—</span> — IP <code id="lastUsedIp">—</code>
      </div>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card-dark">
      <div class="card-title-small"><i class="fa-regular fa-copy"></i> Logs récents</div>
      <div id="logsContainer"></div>
      <button onclick="toggleLogs()" id="toggleLogsBtn" class="btn-logs">Voir tous les logs →</button>
    </div>
  </div>
</div>
<div class="card-dark">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div class="card-title-small mb-0"><i class="fa-solid fa-link"></i> Webhooks</div>
    <button class="btn-api btn-blue" onclick="openModal()" style="padding:7px 14px;font-size:12px;">+ Ajouter</button>
  </div>
  <div class="table-wrapper">
    <table class="wh-table">
      <thead><tr><th>URL</th><th>Événements</th><th>Statut</th><th>Dernier envoi</th><th>Actions</th></tr></thead>
      <tbody id="webhookTable"><tr><td colspan="5" class="text-center muted">Chargement des webhooks...</td></tr></tbody>
    </table>
  </div>
</div>
<div class="card-dark doc-card" style="margin-top:24px; padding:28px; border-radius:18px;">
  <h2 style="margin-bottom:8px;"><i class="fa-solid fa-satellite-dish"></i> Webhook API</h2>
  <p style="opacity:0.75; margin-bottom:24px;">Recevez des événements Xepay en temps réel.</p>
  <h3><i class="fa-solid fa-location-dot"></i>  Endpoint</h3>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code class="language-http">POST https://api.alasdia.com/webhooks</code></pre>
  </div>
  <h3><i class="fa-solid fa-box"></i> Headers</h3>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code class="language-http">Content-Type: application/json
  X-Xepay-Signature: &lt;hmac_sha256_signature&gt;
  X-Xepay-Event: &lt;event_type&gt;
  X-Xepay-Timestamp: &lt;unix_timestamp&gt;</code></pre>
  </div>
  <h3><i class="fa-solid fa-lock"></i> Webhook Secret</h3>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code id="webhookSecretExample">Votre secret apparaît lors de la création du webhook.</code></pre>
  </div>
  <h3><i class="fa-solid fa-shield"></i> Signature</h3>
  <p style="opacity:0.8; margin-bottom:14px;">Chaque webhook est signé par Xepay avec le secret associé au webhook. La signature HMAC SHA256 est calculée sur le corps exact de la requête HTTP.</p>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code>HMAC-SHA256(webhook.secret, raw_request_body)</code></pre>
  </div>
  <div class="security-box"><i class="fa-brands fa-python"></i>Vérifiez toujours la signature avant de traiter un paiement.</div>
  <h3 style="margin-top:28px;"><i class="fa-solid fa-file-code"></i> Payload</h3>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code class="language-json">{
    "id": "evt_&lt;event_id&gt;",
    "timestamp": "&lt;unix_timestamp&gt;",
    "event": "payment.success",
    "data": {
      "amount": "&lt;payment_amount&gt;",
      "currency": "&lt;payment_currency&gt;",
      "user_id": "&lt;user_id&gt;",
      "link_id": "&lt;link_id&gt;"
    }
  }</code></pre>
  </div>
  <h3><i class="fa-brands fa-node-js"></i> Vérification (Node.js)</h3>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code class="language-javascript">const crypto = require("crypto");
  // rawBody doit être le Buffer brut reçu dans la requête
  const rawBody = req.rawBody;
  const signature = req.headers["x-xepay-signature"];
  const expected = crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(rawBody)
    .digest("hex");
  if (
    !signature ||
    !crypto.timingSafeEqual(
      Buffer.from(signature, "hex"),
      Buffer.from(expected, "hex")
    )
  ) {
    throw new Error("Invalid signature");
  }
  res.status(200).json({
    received: true
  });</code></pre>
  </div>
  <h3><i class="fa-brands fa-python"></i> Vérification (Python)</h3>
  <div class="code-block">
    <button class="copy-btn" onclick="copyCode(this)">Copy</button>
    <pre><code class="language-python">import hmac
  import hashlib
  # raw_body : corps brut de la requête HTTP (bytes)
  signature = request.headers.get("X-Xepay-Signature")
  expected = hmac.new(
    WEBHOOK_SECRET.encode("utf-8"),
    raw_body,
    hashlib.sha256
  ).hexdigest()
  if not signature or not hmac.compare_digest(expected, signature):
    raise ValueError("Invalid signature")
  return {
    "received": True
  }</code></pre>
  </div>
  <h3><i class="fa-solid fa-rotate"></i> Retries automatiques</h3>
  <p style="opacity:0.8;">Xepay tente automatiquement de renvoyer les webhooks échoués jusqu'à 3 fois avec un court délai entre chaque tentative.</p>
  <h3 style="margin-top:28px;"><i class="fa-solid fa-file-lines"></i> Réponses HTTP</h3>
  <table class="retry-table">
    <tr><th>Code</th><th>Description</th></tr>
    <tr><td>200</td><td>Webhook reçu</td></tr>
    <tr><td>400</td><td>Signature invalide</td></tr>
    <tr><td>500</td><td>Erreur serveur</td></tr>
  </table>
  <h3 style="margin-top:28px;">⚡ Événements disponibles</h3>
  <table class="retry-table">
    <tr><th>Event</th><th>Description</th></tr>
    <tr><td>payment.success</td><td>Paiement confirmé</td></tr>
    <tr><td>payment.failed</td><td>Paiement échoué</td></tr>
    <tr><td>withdrawal.done</td><td>Retrait envoyé</td></tr>
    <tr><td>refund.issued</td><td>Remboursement effectué</td></tr>
  </table>
  <h3 style="margin-top:28px;"><i class="fa-solid fa-flask"></i> Test rapide</h3>
  <p style="opacity:0.8;">Utilisez <strong>webhook.site</strong> pour tester et inspecter les requêtes webhook.</p>
</div>
</div>
<div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
  <div class="modal-box">
    <h5 style="font-weight:700;margin-bottom:6px;">➕ Ajouter un webhook</h5>
    <p style="font-size:13px;color:#7b82b0;margin-bottom:18px;">Entrez l'URL et choisissez les événements.</p>
    <div class="mb-3">
      <label style="font-size:11px;font-weight:600;color:#7b82b0;text-transform:uppercase;display:block;margin-bottom:6px;">URL</label>
      <input class="form-ctrl" id="whUrl" type="url" placeholder="Exemple : https://votre-site.com/api/webhook/ePay"/>
    </div>
    <div class="mb-3">
      <label style="font-size:11px;font-weight:600;color:#7b82b0;text-transform:uppercase;display:block;margin-bottom:6px;">Événements</label>
      <label class="check-label"><input type="checkbox" id="ev1" checked/> payment.success</label>
      <label class="check-label"><input type="checkbox" id="ev2"/> payment.failed</label>
      <label class="check-label"><input type="checkbox" id="ev3"/> withdrawal.done</label>
      <label class="check-label"><input type="checkbox" id="ev4"/> refund.issued</label>
    </div>
    <div class="d-flex gap-2 justify-content-end mt-3">
      <button class="btn-api btn-out" onclick="closeModal()">Annuler</button>
      <button class="btn-api btn-blue" onclick="addWebhook()">✓ Enregistrer</button>
    </div>
  </div>
</div>
<div class="toast-msg" id="toast"><span id="toastMsg"></span></div>
<div id="secretModal" class="secret-modal hidden">
  <div class="secret-modal-content">
    <h3>🔐 Secret Webhook</h3>
    <p class="warning">⚠️ Ce secret est visible une seule fois. Copiez-le maintenant.</p>
    <div class="secret-box">
      <input id="secretValue" readonly />
      <button onclick="copySecret()">📋 Copier</button>
    </div>
    <button class="btn" onclick="closeSecretModal()">J'ai copié</button>
  </div>
</div>
`;

const PRISM_SCRIPTS = [
  "https://cdn.jsdelivr.net/npm/prismjs/prism.js",
  "https://cdn.jsdelivr.net/npm/prismjs/components/prism-python.min.js",
  "https://cdn.jsdelivr.net/npm/prismjs/components/prism-json.min.js",
  "https://cdn.jsdelivr.net/npm/prismjs/components/prism-http.min.js",
];

let prismLoadingPromise = null;
function ensurePrism() {
  if (window.Prism) return Promise.resolve();
  if (prismLoadingPromise) return prismLoadingPromise;
  prismLoadingPromise = PRISM_SCRIPTS.reduce(
    (chain, src) =>
      chain.then(
        () =>
          new Promise((resolve, reject) => {
            const s = document.createElement("script");
            s.src = src;
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
          })
      ),
    Promise.resolve()
  );
  return prismLoadingPromise;
}

export async function mount(container) {
  await setViewStyles(["API.css"]);
  if (!document.getElementById("prism-theme-link")) {
    const link = document.createElement("link");
    link.id = "prism-theme-link";
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/prismjs/themes/prism-tomorrow.css";
    document.head.appendChild(link);
  }
  container.innerHTML = TEMPLATE;

  let secretVisible = false;
  let showAllLogs = false;

  function escapeHTML(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function copyCode(button) {
    const code = button.parentElement.querySelector("code").innerText;
    navigator.clipboard.writeText(code);
    button.innerText = "Copied";
    setTimeout(() => (button.innerText = "Copy"), 1500);
  }

  function toggleSecret() {
    const el = document.getElementById("secKey");
    if (secretVisible) {
      el.textContent = "••••••••••••";
      secretVisible = false;
    } else {
      el.textContent = el.dataset.real;
      secretVisible = true;
      setTimeout(() => {
        el.textContent = "sk_live_••••••••";
        secretVisible = false;
      }, 3000);
    }
  }

  function copyKey(id) {
    const el = document.getElementById(id);
    const text = el.dataset.real || el.textContent;
    navigator.clipboard.writeText(text);
  }

  async function loadWebhooks() {
    try {
      const res = await apiFetch("/webhooks-api");
      if (!res.ok) throw new Error("Impossible de charger les webhooks");
      const data = await res.json();
      const tbody = document.getElementById("webhookTable");
      tbody.innerHTML = "";
      if (!data.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="muted" style="text-align:center;padding:25px;">Aucun webhook configuré</td></tr>`;
        return;
      }
      data.forEach((w) => {
        const tr = document.createElement("tr");
        const eventsHTML = w.events.map((event) => `<span class="event-tag">${event}</span>`).join("");
        const lastTriggered = w.last_triggered
          ? new Date(w.last_triggered).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" })
          : "Jamais";
        tr.innerHTML = `
          <td class="url-mono">${escapeHTML(w.url)}</td>
          <td>${eventsHTML}</td>
          <td><span class="${w.is_active ? "badge-active" : "badge-inactive"}">● ${w.is_active ? "Actif" : "Inactif"}</span></td>
          <td class="muted" style="font-size:12px;">${lastTriggered}</td>
          <td>
            <button class="icon-btn" onclick="testWebhook('${w.id}')" title="Tester"><i class="fa-solid fa-vial"></i></button>
            <button class="icon-btn" onclick="deleteWebhook('${w.id}', this)" title="Supprimer"><i class="fa-solid fa-trash"></i></button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    } catch (error) {
      console.error("Erreur loadWebhooks:", error);
      document.getElementById("webhookTable").innerHTML = `
        <tr><td colspan="5" style="text-align:center;color:#ff4757;padding:20px;">Impossible de charger les webhooks</td></tr>
      `;
    }
  }

  async function addWebhook() {
    const url = document.getElementById("whUrl").value.trim();
    if (!url) {
      alert("URL requise");
      return;
    }
    const events = ["ev1", "ev2", "ev3", "ev4"]
      .filter((id) => document.getElementById(id).checked)
      .map((id) => ({ ev1: "payment.success", ev2: "payment.failed", ev3: "withdrawal.done", ev4: "refund.issued" }[id]));
    if (!events.length) {
      alert("Sélectionnez un événement");
      return;
    }
    try {
      const res = await apiFetch("/webhooks-api", { method: "POST", body: { url, events } });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Erreur lors de la création du webhook");
      if (result.secret) showSecret(result.secret);
      closeModal();
      document.getElementById("whUrl").value = "";
      document.querySelectorAll("#modalOverlay input[type='checkbox']").forEach((input) => (input.checked = false));
      document.getElementById("ev1").checked = true;
      showToast("Webhook ajouté !", "#00e676");
      await loadWebhooks();
      await loadStats();
    } catch (error) {
      console.error("Erreur création webhook:", error);
      alert(error.message);
    }
  }

  async function deleteWebhook(id, btn) {
    if (!confirm("Supprimer ?")) return;
    await apiFetch(`/webhooks-api/${id}`, { method: "DELETE" });
    btn.closest("tr").remove();
    showToast("🗑 Supprimé", "#ff4757");
  }

  async function testWebhook(id) {
    try {
      const res = await apiFetch(`/webhooks-api/${id}/test`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Échec du test webhook");
      if (data.success) {
        showToast(`Test réussi — HTTP ${data.status_code}`, "#00e676");
      } else {
        showToast(`Échec — HTTP ${data.status_code || "inconnu"} : ${data.error || "Erreur"}`, "#ff4757");
      }
      await loadWebhooks();
    } catch (error) {
      console.error("Erreur test webhook :", error);
      showToast(error.message, "#ff4757");
    }
  }

  function openModal() {
    document.getElementById("modalOverlay").classList.add("open");
  }
  function closeModal(e) {
    if (!e || e.target === document.getElementById("modalOverlay")) {
      document.getElementById("modalOverlay").classList.remove("open");
    }
  }
  function showToast(msg, color) {
    const t = document.getElementById("toast");
    document.getElementById("toastMsg").textContent = msg;
    t.style.borderColor = color || "#00d4ff";
    t.style.color = color || "#00d4ff";
    t.classList.add("show");
    setTimeout(() => t.classList.remove("show"), 2800);
  }

  async function loadApiKeys() {
    const res = await apiFetch("/api-keys");
    const data = await res.json();
    document.getElementById("pubKey").textContent = data.public_key;
    document.getElementById("pubKey").dataset.real = data.public_key;
    const el = document.getElementById("secKey");
    if (data.secret_key) {
      el.dataset.real = data.secret_key;
      el.textContent = "••••••••••••";
    } else {
      el.textContent = "sk_live_••••••••";
    }
  }

  function formatLastLogin(date) {
    if (!date) return "Jamais";
    const last = new Date(date);
    const now = new Date();
    const diff = Math.floor((now - last) / 1000);
    if (diff < 60) return "À l'instant";
    const minutes = Math.floor(diff / 60);
    if (minutes < 60) return `Il y a ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `Il y a ${hours} h`;
    const days = Math.floor(hours / 24);
    if (days === 1) return `Hier à ${last.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
    return last.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  async function loadCurrentUser() {
    const res = await apiFetch("/me");
    const user = await res.json();
    localStorage.setItem("plan", user.plan);
    if (user.session) {
      document.getElementById("lastUsedTime").textContent = formatLastLogin(user.session.last_seen);
      document.getElementById("lastUsedIp").textContent = user.session.ip || "—";
    }
    return user;
  }

  async function regenKey() {
    if (!confirm("Régénérer la clé secrète ?")) return;
    const res = await apiFetch("/api-keys/regenerate", { method: "POST" });
    const data = await res.json();
    showSecretPopup(data.secret_key);
    document.getElementById("pubKey").textContent = data.public_key;
    document.getElementById("secKey").dataset.real = data.secret_key;
    if (secretVisible) document.getElementById("secKey").textContent = data.secret_key;
    showToast("🔄 Nouvelle clé générée !", "#f5c518");
  }

  function showSecret(secret) {
    document.getElementById("secretValue").value = secret;
    document.getElementById("secretModal").classList.remove("hidden");
  }
  function closeSecretModal() {
    document.getElementById("secretModal").classList.add("hidden");
  }
  function copySecret() {
    const input = document.getElementById("secretValue");
    input.select();
    document.execCommand("copy");
    showToast("Copié !", "#00e676");
    closeSecretModal();
  }

  async function loadLogs() {
    const limit = showAllLogs ? 50 : 5;
    const res = await apiFetch(`/logs?limit=${limit}`);
    const logs = await res.json();
    const container = document.getElementById("logsContainer");
    container.innerHTML = "";
    logs.forEach((log) => {
      const div = document.createElement("div");
      div.className = "log-row";
      div.innerHTML = `
        <span class="log-method ${log.method.toLowerCase()}">${log.method}</span>
        <span class="${log.status === 200 ? "log-status-ok" : "log-status-err"}">${log.status}</span>
        <span>${log.path}</span>
      `;
      container.appendChild(div);
    });
  }
  function toggleLogs() {
    showAllLogs = !showAllLogs;
    const btn = document.getElementById("toggleLogsBtn");
    btn.textContent = showAllLogs ? "Voir moins" : "Voir tous les logs →";
    loadLogs();
  }

  async function loadStats() {
    try {
      const res = await apiFetch("/logs/stats");
      if (!res.ok) throw new Error("Erreur chargement statistiques");
      const data = await res.json();
      document.getElementById("callsThisMonth").textContent = data.calls_this_month ?? 0;
      document.getElementById("successRate").textContent = `${Number(data.success_rate ?? 0).toFixed(1)}%`;
      document.getElementById("activeWebhooks").textContent = data.active_webhooks ?? 0;
      document.getElementById("webhookText").textContent = `${data.total_webhooks ?? 0} endpoints configurés`;
      document.getElementById("errorsText").textContent = `${data.errors ?? 0} erreurs`;
      const growth = Number(data.growth ?? 0);
      document.getElementById("growthText").textContent =
        growth > 0 ? `+${growth}% vs mois dernier` : growth < 0 ? `${growth}% vs mois dernier` : "Stable vs mois dernier";
    } catch (error) {
      console.error("Erreur statistiques :", error);
    }
  }

  function showSecretPopup(secret) {
    const modal = document.createElement("div");
    Object.assign(modal.style, {
      position: "fixed", top: "0", left: "0", width: "100vw", height: "100vh",
      background: "rgba(0,0,0,0.8)", zIndex: "999999", display: "flex",
      alignItems: "center", justifyContent: "center",
    });
    const box = document.createElement("div");
    Object.assign(box.style, {
      background: "#111", color: "white", padding: "20px", borderRadius: "10px",
      minWidth: "300px", textAlign: "center",
    });
    const title = document.createElement("h3");
    title.textContent = "🔐 Clé secrète";
    const content = document.createElement("div");
    content.style.margin = "10px 0";
    const code = document.createElement("code");
    code.textContent = secret;
    code.style.display = "block";
    code.style.wordBreak = "break-all";
    const copyBtn = document.createElement("button");
    copyBtn.textContent = "📋 Copier";
    Object.assign(copyBtn.style, {
      marginTop: "10px", padding: "8px 12px", border: "none", borderRadius: "6px",
      background: "#4CAF50", color: "white", cursor: "pointer", fontWeight: "bold",
    });
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(secret);
      copyBtn.textContent = "✅ Copié";
      setTimeout(() => {
        modal.style.opacity = "0";
        modal.style.transition = "opacity 0.3s";
        setTimeout(() => modal.remove(), 300);
      }, 800);
    };
    content.appendChild(code);
    content.appendChild(copyBtn);
    box.appendChild(title);
    box.appendChild(content);
    modal.appendChild(box);
    document.body.appendChild(modal);
  }

  function showLockedOverlay() {
    document.getElementById("featureLock").classList.remove("d-none");
  }

  async function initPlan() {
    const user = await loadCurrentUser();
    if (user.plan === "free") {
      document.body.classList.add("locked-page");
      showLockedOverlay();
    }
  }

  const onShownUpgrade = (e) => {
    if (e.target.id === "modalUpgrade") {
      document.querySelectorAll("#modalUpgrade .reveal").forEach((el, index) => {
        setTimeout(() => el.classList.add("visible"), index * 100);
      });
    }
  };
  document.addEventListener("shown.bs.modal", onShownUpgrade);

  window.copyCode = copyCode;
  window.toggleSecret = toggleSecret;
  window.copyKey = copyKey;
  window.regenKey = regenKey;
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.addWebhook = addWebhook;
  window.testWebhook = testWebhook;
  window.deleteWebhook = deleteWebhook;
  window.toggleLogs = toggleLogs;
  window.copySecret = copySecret;
  window.closeSecretModal = closeSecretModal;
  // window.upgrade est exposé globalement par app.js (modale partagée persistante)

  ensurePrism().then(() => window.Prism?.highlightAllUnder(container));
  loadWebhooks();
  loadApiKeys();
  loadLogs();
  loadStats();
  initPlan();

  return {
    unmount() {
      document.body.classList.remove("locked-page");
      document.removeEventListener("shown.bs.modal", onShownUpgrade);
      delete window.copyCode;
      delete window.toggleSecret;
      delete window.copyKey;
      delete window.regenKey;
      delete window.openModal;
      delete window.closeModal;
      delete window.addWebhook;
      delete window.testWebhook;
      delete window.deleteWebhook;
      delete window.toggleLogs;
      delete window.copySecret;
      delete window.closeSecretModal;
    },
  };
}
