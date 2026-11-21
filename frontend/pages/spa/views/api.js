// Vue "API Access" — port fidèle de API.html + API.js.
import { apiFetch } from "../core/apiClient.js";
import { setViewStyles } from "../core/styleLoader.js";

const TEMPLATE = `
<div id="api-content">
<div class="mb-4">
  <h1 class="page-title"><i class="fa-solid fa-code"></i> API Access</h1>
  <p class="page-subtitle">Gérez vos clés API et configurez vos webhooks pour intégrer Xepay dans vos applications.</p>
</div>
<div class="mb-5">
  <div class="params-subsection-header">
    <h6 class="params-subsection-title mb-0">Clés API</h6>
    <button type="button" class="create-client-btn" onclick="regenKey()">Régénérer</button>
  </div>
  <p class="params-subsection-sub">Vos identifiants pour authentifier les requêtes à l'API Xepay.</p>
  <div class="params-row-list">
    <div class="params-info-row">
      <span>Clé publique</span>
      <div class="params-row-right">
        <strong id="pubKey">Chargement...</strong>
        <button type="button" class="params-edit-btn" onclick="copyKey('pubKey')">Copier</button>
      </div>
    </div>
    <div class="params-info-row">
      <span>Clé secrète</span>
      <div class="params-row-right">
        <strong id="secKey">••••••••••••••••</strong>
        <button type="button" class="params-edit-btn" id="toggleBtn" onclick="toggleSecret()">Afficher</button>
        <button type="button" class="params-edit-btn" onclick="copyKey('secKey')">Copier</button>
      </div>
    </div>
    <div class="params-info-row">
      <span>Dernière utilisation</span>
      <div class="params-row-right">
        <strong id="lastUsedTime">—</strong>
        <span class="text-muted" style="font-size:12px;">IP <code id="lastUsedIp">—</code></span>
      </div>
    </div>
  </div>
</div>
<div class="table-wrap mb-4">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <span class="table-title">Webhooks</span>
    <div class="d-flex align-items-center gap-2">
      <span id="nbWebhooks" class="count-badge">0 webhook</span>
      <button type="button" class="create-client-btn" onclick="openModal()">+ Ajouter</button>
    </div>
  </div>
  <table class="table table-hover align-middle">
    <thead><tr><th>URL</th><th>Événements</th><th>Statut</th><th>Dernier envoi</th><th></th></tr></thead>
    <tbody id="webhookTable"><tr><td colspan="5" class="text-center muted">Chargement des webhooks...</td></tr></tbody>
  </table>
</div>
<div class="table-wrap">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <span class="table-title">Logs</span>
    <span id="nbLogs" class="count-badge">0 appel</span>
  </div>
  <table class="table table-hover align-middle">
    <thead><tr><th>Méthode</th><th>Statut</th><th>Chemin</th><th>Date</th></tr></thead>
    <tbody id="logsTable"><tr><td colspan="4" class="text-center muted">Chargement des logs...</td></tr></tbody>
  </table>
  <button type="button" onclick="toggleLogs()" id="toggleLogsBtn" class="params-edit-btn mt-2">Voir tous les logs →</button>
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

export async function mount(container) {
  await setViewStyles(["API.css", "transactions.css", "parametres.css"]);
  container.innerHTML = TEMPLATE;

  let secretVisible = false;
  let showAllLogs = false;

  function escapeHTML(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function toggleSecret() {
    const el = document.getElementById("secKey");
    const btn = document.getElementById("toggleBtn");
    if (secretVisible) {
      el.textContent = "••••••••••••";
      btn.textContent = "Afficher";
      secretVisible = false;
    } else {
      el.textContent = el.dataset.real;
      btn.textContent = "Masquer";
      secretVisible = true;
      setTimeout(() => {
        el.textContent = "sk_live_••••••••";
        btn.textContent = "Afficher";
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
      document.getElementById("nbWebhooks").textContent = `${data.length} webhook${data.length > 1 ? "s" : ""}`;
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
          <td><span class="status-pill ${w.is_active ? "badge-success" : "badge-danger"}">${w.is_active ? "Actif" : "Inactif"}</span></td>
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
    await loadWebhooks();
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
    const tbody = document.getElementById("logsTable");
    tbody.innerHTML = "";
    document.getElementById("nbLogs").textContent = `${logs.length} appel${logs.length > 1 ? "s" : ""}`;
    if (!logs.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="muted" style="text-align:center;padding:25px;">Aucun appel enregistré</td></tr>`;
      return;
    }
    logs.forEach((log) => {
      const tr = document.createElement("tr");
      const time = log.time
        ? new Date(log.time).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" })
        : "—";
      tr.innerHTML = `
        <td><span class="log-method ${log.method.toLowerCase()}">${log.method}</span></td>
        <td><span class="${log.status === 200 ? "log-status-ok" : "log-status-err"}">${log.status}</span></td>
        <td class="url-mono">${escapeHTML(log.path)}</td>
        <td class="muted" style="font-size:12px;">${time}</td>
      `;
      tbody.appendChild(tr);
    });
  }
  function toggleLogs() {
    showAllLogs = !showAllLogs;
    const btn = document.getElementById("toggleLogsBtn");
    btn.textContent = showAllLogs ? "Voir moins" : "Voir tous les logs →";
    loadLogs();
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

  loadWebhooks();
  loadApiKeys();
  loadLogs();
  loadCurrentUser();

  return {
    unmount() {
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
