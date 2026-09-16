function copyCode(button) {
  const code =
    button.parentElement.querySelector("code").innerText;
  navigator.clipboard.writeText(code);
  button.innerText = "Copied";
  setTimeout(() => {
    button.innerText = "Copy";
  }, 1500);
}
let secretVisible = false;
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
async function loadWebhooks() {
  const token = localStorage.getItem("token")
  const res = await fetch("https://api.alasdia.com/webhooks-api", {
    headers: { Authorization: "Bearer " + token }
  })
  const data = await res.json()
  const tbody = document.getElementById("webhookTable")
  tbody.innerHTML = ""
  data.forEach(w => {
    const tr = document.createElement("tr")
    tr.innerHTML = `
      <td class="url-mono">${w.url}</td>
      <td>${w.events.map(e => `<span class="event-tag">${e}</span>`).join("")}</td>
      <td>
        <span class="${w.is_active ? 'badge-active' : 'badge-inactive'}">
          ${w.is_active ? 'Actif' : 'Inactif'}
        </span>
      </td>
      <td class="muted" style="font-size:12px">
        ${
          w.last_triggered
            ? new Date(w.last_triggered).toLocaleString("fr-FR", {
                dateStyle: "short",
                timeStyle: "medium"
              })
            : "Jamais"
        }
      </td>
      <td>
        <button class="icon-btn" onclick="testWebhook(${w.id})">▶</button>
        <button class="icon-btn" onclick="deleteWebhook(${w.id}, this)">🗑</button>
      </td>
    `
    tbody.appendChild(tr)
  })
}
async function addWebhook() {
  const url = document.getElementById('whUrl').value.trim()
  if (!url) return alert('URL requise')
  const events = ['ev1','ev2','ev3','ev4']
    .filter(id => document.getElementById(id).checked)
    .map(id => ({'ev1':'payment.success','ev2':'payment.failed','ev3':'withdrawal.done','ev4':'refund.issued'}[id]))
  if (!events.length) return alert('Sélectionnez un événement')
  const token = localStorage.getItem("token")
  const res = await fetch("https://api.alasdia.com/webhooks-api", {
    method: "POST",
    headers: { 
      Authorization: "Bearer " + token, 
      "Content-Type": "application/json",
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    },
    body: JSON.stringify({ url, events })
  })
  const result = await res.json()
  showSecret(result.secret)
  if (!res.ok) return alert("Erreur")
  closeModal()
  showToast('✅ Webhook ajouté !', '#00e676')
  document.getElementById('whUrl').value = ''
  loadWebhooks()
}
async function deleteWebhook(id, btn) {
  if (!confirm('Supprimer ?')) return
  const token = localStorage.getItem("token")
  await fetch(`https://api.alasdia.com/webhooks-api/${id}`, {
    method: "DELETE",
    headers: { 
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  btn.closest('tr').remove()
  showToast('🗑 Supprimé', '#ff4757')
}
async function testWebhook(id) {
  const token = localStorage.getItem("token")
  await fetch(`https://api.alasdia.com/webhooks-api/${id}/test`, {
    method: "POST",
    headers: { 
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  showToast('🧪 Test envoyé !', '#00d4ff')
}
function openModal() { document.getElementById('modalOverlay').classList.add('open') }
function closeModal(e) { if (!e || e.target === document.getElementById('modalOverlay')) document.getElementById('modalOverlay').classList.remove('open') }
function showToast(msg, color) {
  const t = document.getElementById('toast')
  document.getElementById('toastMsg').textContent = msg
  t.style.borderColor = color || '#00d4ff'
  t.style.color = color || '#00d4ff'
  t.classList.add('show')
  setTimeout(() => t.classList.remove('show'), 2800)
}
loadWebhooks()
async function loadApiKeys() {
  const token = localStorage.getItem("token")
  const res = await fetch("https://api.alasdia.com/api-keys", {
    headers: { 
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  const data = await res.json()
  document.getElementById("pubKey").textContent = data.public_key
  const el = document.getElementById("secKey")
  if (data.secret_key) {
    el.dataset.real = data.secret_key
    el.textContent = "••••••••••••"
  } else {
    el.textContent = "sk_live_••••••••"
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
  if (days === 1) {
    return `Hier à ${last.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }
  return last.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}
async function loadCurrentUser() {
  const token = localStorage.getItem("token")
  const res = await fetch("https://api.alasdia.com/me", {
    headers: {
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  const user = await res.json()
  localStorage.setItem("plan", user.plan)
  if (user.session) {
    document.getElementById("lastUsedTime").textContent =
      formatLastLogin(user.session.last_seen)
    document.getElementById("lastUsedIp").textContent =
      user.session.ip || "—"
  }
  return user
}
async function regenKey() {
  if (!confirm("Régénérer la clé secrète ?")) return
  const token = localStorage.getItem("token")
  const res = await fetch("https://api.alasdia.com/api-keys/regenerate", {
    method: "POST",
    headers: { 
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  const data = await res.json()
  showSecretPopup(data.secret_key)
  console.log("POPUP TEST")
  document.getElementById("pubKey").textContent = data.public_key
  document.getElementById("secKey").dataset.real = data.secret_key
  if (secretVisible) {
    document.getElementById("secKey").textContent = data.secret_key
  }
  showToast("🔄 Nouvelle clé générée !", "#f5c518")
}
loadApiKeys()
function showSecret(secret) {
  document.getElementById("secretValue").value = secret
  document.getElementById("secretModal").classList.remove("hidden")
}
function closeSecretModal() {
  document.getElementById("secretModal").classList.add("hidden")
}
function copySecret() {
  const input = document.getElementById("secretValue")
  input.select()
  document.execCommand("copy")
  showToast("Copié !", "#00e676")
  closeSecretModal()
}
let showAllLogs = false;
async function loadLogs() {
  const token = localStorage.getItem("token")
  const limit = showAllLogs ? 50 : 5;
  const res = await fetch(`https://api.alasdia.com/logs?limit=${limit}`, {
    headers: { 
      Authorization: "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  const logs = await res.json()
  const container = document.getElementById("logsContainer")
  container.innerHTML = ""
  logs.forEach(log => {
    const div = document.createElement("div")
    div.className = "log-row"
    div.innerHTML = `
      <span class="log-method ${log.method.toLowerCase()}">${log.method}</span>
      <span class="${log.status === 200 ? 'log-status-ok' : 'log-status-err'}">${log.status}</span>
      <span>${log.path}</span>
    `
    container.appendChild(div)
  })
}
loadLogs()
function toggleLogs() {
  showAllLogs = !showAllLogs;
  console.log("showAllLogs =", showAllLogs);
  const btn = document.getElementById("toggleLogsBtn");
  btn.textContent = showAllLogs
    ? "Voir moins"
    : "Voir tous les logs →";
  loadLogs();
}
async function loadStats() {
  const token = localStorage.getItem("token")
  console.log("TOKEN 👉", token)
  const res = await fetch("https://api.alasdia.com/logs/stats", {
      method: "GET",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
  })
  const data = await res.json()
  console.log("STATS:", data)
  if (!data || typeof data.calls_this_month === "undefined") return
  document.querySelector(".stat-value.cyan").innerText =
    data.calls_this_month
  document.querySelector(".stat-value.green").innerText =
    (data.success_rate ?? 0).toFixed(1) + "%"
  document.querySelector(".stat-value.yellow").innerText =
    data.active_webhooks
  document.getElementById("webhookText").innerText =
  `${data.total_webhooks} endpoints configurés`
  document.getElementById("errorsText").innerText =
  `${data.errors} erreurs sur ${data.calls_this_month}`
  const g = data.growth ?? 0
  const growthEl = document.getElementById("growthText")
  if (g > 0) {
    growthEl.innerText = `+${g}% vs mois dernier`
  } else if (g < 0) {
    growthEl.innerText = `${g}% vs mois dernier`
  } else {
    growthEl.innerText = "Stable vs mois dernier"
  }
}
loadStats()
function showSecretPopup(secret) {
    const modal = document.createElement("div");
    modal.style.position = "fixed";
    modal.style.top = "0";
    modal.style.left = "0";
    modal.style.width = "100vw";
    modal.style.height = "100vh";
    modal.style.background = "rgba(0,0,0,0.8)";
    modal.style.zIndex = "999999";
    modal.style.display = "flex";
    modal.style.alignItems = "center";
    modal.style.justifyContent = "center";
    const box = document.createElement("div");
    box.style.background = "#111";
    box.style.color = "white";
    box.style.padding = "20px";
    box.style.borderRadius = "10px";
    box.style.minWidth = "300px";
    box.style.textAlign = "center";
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
    copyBtn.style.marginTop = "10px";
    copyBtn.style.padding = "8px 12px";
    copyBtn.style.border = "none";
    copyBtn.style.borderRadius = "6px";
    copyBtn.style.background = "#4CAF50";
    copyBtn.style.color = "white";
    copyBtn.style.cursor = "pointer";
    copyBtn.style.fontWeight = "bold";
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
function renderPlanBadge(plan) {
  const el = document.getElementById("badge-plan")
  if (plan === "pro") {
    el.className = "badge pro"
    el.textContent = "PRO"
  } else if (plan === "business") {
    el.className = "badge business"
    el.textContent = "BUSINESS"
  } else {
    el.className = "badge free"
    el.textContent = "FREE"
  }
}
async function initPlan() {
  const user = await loadCurrentUser();
  if (user.plan === "free") {
      document.body.classList.add("locked-page");
      showLockedOverlay("pro");
  }
}
initPlan();
function checkApiAccess(event) {
    const plan = localStorage.getItem("plan");
    if (plan === "free") {
        sessionStorage.setItem("openApiUpgrade", "true");
    }
}
function checkMultiUsersAccess(event) {
    const plan = localStorage.getItem("plan");
    if (plan !== "business") {
        sessionStorage.setItem(
            "openMultiUsersUpgrade",
            "true"
        );
    }
}
function copyPopupSecret() {
    const text = document.getElementById("popupSecret").textContent
    navigator.clipboard.writeText(text)
}
function closePopup() {
    document.querySelector(".webhook-modal-overlay").remove()
}
function showUpgradeModal(feature = null) {
  document.querySelectorAll(".plan-card")
    .forEach(card => {
      card.classList.remove("plan-disabled");
    });
  if (feature === "API.html") {
    document.querySelector(".plan-starter")
        .classList.add("plan-disabled");
  } else if (feature === "multi-users") {
    document.querySelector(".plan-starter")
        .classList.add("plan-disabled");
    document.querySelector(".plan-pro")
        .classList.add("plan-disabled");
  } else {
    const plan = localStorage.getItem("plan");
    if (plan === "free") {
        document.querySelector(".plan-starter")
            .classList.add("plan-disabled");
    }
    if (plan === "pro") {
        document.querySelector(".plan-pro")
            .classList.add("plan-disabled");
    }
    if (plan === "business") {
        document.querySelector(".plan-business")
            .classList.add("plan-disabled");
    }
  }
  const modal = new bootstrap.Modal(
    document.getElementById("modalUpgrade")
  );
  modal.show();
}
function showLockedOverlay(plan){
  document
    .getElementById("featureLock")
    .classList.remove("d-none");
}
async function upgrade(plan) {
  const token = localStorage.getItem("token");
  const res = await fetch(
    "https://api.alasdia.com/create-checkout-session",
    {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        plan: plan
      })
    }
  );
  const data = await res.json();
  if (!res.ok || !data.url) {
    alert("Erreur lors de l'ouverture de Stripe");
    return;
  }
  window.location.href = data.url;
}
document
  .getElementById("modalUpgrade")
  .addEventListener("shown.bs.modal", () => {
    document.querySelectorAll("#modalUpgrade .reveal")
      .forEach((el, index) => {
        setTimeout(() => {
          el.classList.add("visible");
        }, index * 100);
      });
});