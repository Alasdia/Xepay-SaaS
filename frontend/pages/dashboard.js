const oauthParams = new URLSearchParams(window.location.search);
const urlToken = oauthParams.get("token");
const workspaceId = oauthParams.get("workspace_id");
console.log("Workspace ID reçu dans l'URL :", workspaceId);
console.log("Est null ?", workspaceId === null);
if (urlToken) {
  localStorage.clear();
  localStorage.setItem("token", urlToken);
  if (workspaceId) {
    localStorage.setItem("workspace_id", workspaceId);
  }
  window.history.replaceState({}, document.title, `/dashboard.html?workspace_id=${workspaceId}`);
  console.log("URL =", window.location.href);
  console.log("urlToken =", urlToken);
  console.log("workspaceId =", workspaceId);
}
const token = localStorage.getItem("token");
if (!token) {
  window.location.replace("login.html");
}
async function loadProfileHeader() {
  console.log(localStorage.getItem("token"))
  try {
    const res = await fetch("https://api.alasdia.com/profile", {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    if (res.status === 401) {
      console.log("TOKEN =", localStorage.getItem("token"))
      console.log("401 FROM /profile")
      return
    }
    if (!res.ok) {
      console.warn("API /profile failed")
      return
    }
    const user = await res.json()
    const name =
      user.full_name?.split(" ")[0] ||
      user.email ||
        "Utilisateur"
        document.getElementById("welcomeText").innerText =
          "Bonjour, " + name + " 👋"
      } catch (err) {
        console.error(err)
        document.getElementById("welcomeText").innerText =
          "Bonjour 👋"
      }
}
loadProfileHeader();
async function loadPlan() {
  try {
    const token = localStorage.getItem("token");
    const res = await fetch("https://api.alasdia.com/me/plan", {
      headers: {
        Authorization: "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await res.json();
    const planLabel = document.getElementById("plan-label");
    if (planLabel) planLabel.innerText = data.plan.charAt(0).toUpperCase() + data.plan.slice(1);
    handleFreeLimit(data)
    console.log("PLAN:", data.plan)
    console.log("PAID:", data.paid_count)
    console.log("Plan user :", data);
  } catch (error) {
    console.error("Erreur chargement plan :", error);
  }
}
loadPlan();
function handleFreeLimit(data) {
  const createBtn = document.getElementById("createBtn")
  if (!createBtn) return
  createBtn.onclick = (e) => {
    e.preventDefault()
    if (data.plan === "free" && data.paid_count >= 10) {
      const createModal = bootstrap.Modal.getInstance(
        document.getElementById("createLinkModal")
      )
      createModal.hide()
      const upgradeModal = bootstrap.getOrCreateInstance(
        document.getElementById("modalUpgrade")
      )
      upgradeModal.show()
    } else {
      createLink()
    }
  }
}
async function loadKPI() {
  try {
    const token = localStorage.getItem("token")
    const res = await fetch("https://api.alasdia.com/stats", {
      headers: {
        Authorization: "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    const data = await res.json()
    console.log("KPI:", data)
    document.getElementById("total-xof").innerText =
        (data.total_received || 0).toLocaleString("fr-FR") + " XOF"
    const planRes = await fetch("https://api.alasdia.com/me/plan", {
      headers: {
        Authorization: "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    const planData = await planRes.json()
    console.log("PLAN DATA FRONT:", planData)
    const visibleLinks = document.querySelectorAll("#links-container > div")
    const displayUsed = visibleLinks.length
    const displayLimit = 10
    const percent = (displayUsed / displayLimit) * 100
    const bar = document.querySelector(".progress-bar-custom")
    if (bar) {
      bar.style.width = percent + "%"
    }
    const usage = document.getElementById("plan-usage")
    if (usage) {
      usage.innerText = `${displayUsed} / ${displayLimit}`
    }
  } catch (err) {
    console.error("Erreur KPI:", err)
  }
}
loadKPI()
let lockedCountdownTimer = null;
async function chargerWallet() {
  try {
    const res = await fetch("https://api.alasdia.com/wallet/me", {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await res.json();
    const balanceEl = document.getElementById("wallet-balance");
    balanceEl.innerText =
      Number(data.available || 0).toLocaleString("fr-FR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }) + " XOF";
    const lockedEl = document.getElementById("locked-amount");
    if (lockedEl) {
      lockedEl.innerText =
        Number(data.locked_amount || 0).toLocaleString("fr-FR", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        }) + " XOF";
    }
    if (lockedCountdownTimer) {
      clearInterval(lockedCountdownTimer);
      lockedCountdownTimer = null;
    }
    if (data.next_available_at) {
      startCountdown(data.next_available_at);
    } else {
      const el = document.getElementById("nextAvailableText");
      if (el) el.innerText = "Aucun montant verrouillé";
    }
  } catch (err) {
    console.error("Erreur wallet:", err);
  }
}
chargerWallet()
function startCountdown(nextAvailableAt) {
  const el = document.getElementById("nextAvailableText");
  const btn = document.getElementById("withdrawBtn");
  function update() {
    const now = new Date();
    const future = new Date(nextAvailableAt);
    const diff = future - now;
    if (diff <= 0) {
      if (el) el.innerText = "✅ Disponible maintenant";
      if (btn) btn.disabled = false;
      if (lockedCountdownTimer) {
        clearInterval(lockedCountdownTimer);
        lockedCountdownTimer = null;
      }
      return;
    }
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor(diff / (1000 * 60 * 60)) % 24;
    const minutes = Math.floor(diff / (1000 * 60)) % 60;
    const seconds = Math.floor(diff / 1000) % 60;
    let text = "";
    if (days > 0) text += `${days}j `;
    if (hours > 0 || days > 0) text += `${hours}h `;
    if (minutes > 0 || hours > 0) text += `${minutes}min `;
    text += `${seconds}s`;
    if (el) el.innerText = "Disponible dans " + text;
  }
  lockedCountdownTimer = setInterval(update, 1000);
  update();
}
async function createLink() {
  const amount = document.getElementById("amount").value
  const currency = document.getElementById("currency").value
  const res = await fetch("https://api.alasdia.com/links", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    },
    body: JSON.stringify({
      amount: amount,
      currency: currency,
      source: "dashboard"
    })
  })
  const data = await res.json()
  console.log("ERROR:", data)
  if (!res.ok) {
    console.log("DATA:", data)
    if (data.detail && data.detail.upgrade === true) {
      const modal = bootstrap.getOrCreateInstance(document.getElementById("modalUpgrade"))
      modal.show()
      return
    }
    alert(data.detail || data.message || "Erreur lors de la création")
    return
  }
  console.log("CREATED:", data)
  loadLinks()
  const modalEl = document.getElementById('createLinkModal')
  const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl)
  modal.hide()
}
function loadLinks() {
  const container = document.getElementById("links-container");
  if (!container) return;
  fetch("https://api.alasdia.com/links/dashboard", {
    headers: {
      "Authorization": "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  .then(res => res.json())
  .then(data => {
    console.log("LINKS:", data);
    const progressText = document.getElementById("progress-text");
    if (progressText) {
      progressText.innerText = `${data.paid_this_month}/10`;
    }
    container.innerHTML = "";
    if (!data.links || data.links.length == 0) {
      container.innerHTML = `<p class="text-muted">Aucun lien pour le moment</p>`;
      return;
    }
    data.links.forEach(link => {
      console.log('champs du lien:', Object.keys(link), link);
      const paymentUrl = link.url;
      container.innerHTML += getLinkHTML(link, paymentUrl);
    });
  });
}
function getLinkHTML(link, paymentUrl) {
  const status = link.status;
  let urlColor, copyBtn, archiveBtn;
  if (status === 'paid') {
    urlColor = '#4ade80';
    copyBtn = '';
    archiveBtn = `<button style="background:rgba(74,222,128,0.15);border:none;color:rgba(255,255,255,0.4);font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="archivedLink('${link.id}')">Archiver</button>`;
  } else if (status === 'pending') {
    urlColor = '#facc15';
    copyBtn = `<button style="background:rgba(74,222,128,0.15);border:none;color:#4ade80;font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="copierLien('${paymentUrl}')" data-url="${paymentUrl}">Copier</button>`;
    archiveBtn = `<button style="background:rgba(248,113,113,0.15);border:none;color:#f87171;font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="deleteLink('${link.id}')">Supprimer</button>`;
  } else if (status === 'expired') {
    urlColor = '#f87171';
    copyBtn = '';
    archiveBtn = `<button style="background:rgba(248,113,113,0.15);border:none;color:#f87171;font-size:0.72rem;padding:5px 12px;border-radius:6px;cursor:pointer;" onclick="deleteLink('${link.id}')">Supprimer</button>`;
  } else {
    urlColor = 'rgba(255,255,255,0.6)';
    copyBtn = '';
    archiveBtn = '';
  }
  return `
    <div id="link-${link.id}" style="width:100%;display:flex;align-items:center;gap:12px;padding:10px 14px;margin-bottom:8px;background:rgba(255,255,255,0.07);border-radius:10px;border:1px solid rgba(255,255,255,0.1);">
      <span style="color:${urlColor};font-size:0.78rem;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:monospace;">${paymentUrl}</span>
        ${copyBtn}
        ${archiveBtn}
    </div>
  `;
}
loadLinks();
function copierLien(url) {
  navigator.clipboard.writeText(url);
  alert("Lien copié !");
}
async function archiveLink(id) {
  const token = localStorage.getItem("token");
  try {
    const res = await fetch(`https://api.alasdia.com/archive/${id}`, {
      method: "POST",
      headers: { "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    if (!res.ok) throw new Error("Erreur archivage");
      loadLinks();
  } catch (e) {
    alert("Erreur archivage");
  }
}
async function deleteLink(id) {
  const token = localStorage.getItem("token");
  try {
    const res = await fetch(`https://api.alasdia.com/links/${id}`, {
      method: "DELETE",
      headers: { 
        "Authorization": "Bearer " + token, 
        "X-Workspace-Id": localStorage.getItem("workspace_id") 
      }
    });
    if (!res.ok) throw new Error("Erreur suppression");
      loadLinks(); 
  } catch (e) {
    alert("Erreur suppression");
  }
}
const createBtn = document.getElementById("createBtn")
  const withdrawBtn = document.getElementById("withdrawBtn")
  withdrawBtn.addEventListener("click", (e) => {
    e.preventDefault()
    if (window.user === "free") {
      const upgradeModal = bootstrap.getOrCreateInstance(
        document.getElementById("modalUpgrade")
      )
      upgradeModal.show()
    } else {
      const withdrawModal = new bootstrap.Modal(
        document.getElementById("withdrawModal")
      )
      withdrawModal.show()
    }
})
document.querySelectorAll(".upgrade-btn").forEach(btn => {
  btn.addEventListener("click", showUpgradeModal);
});
function showUpgradeModal(feature = null) {
  const plan = localStorage.getItem("plan");
  updateUpgradeModal(plan, feature);
  const modal = bootstrap.getOrCreateInstance(
    document.getElementById("modalUpgrade")
  );
  modal.show();
}
async function loadWorkspaces() {
  try {
    const res = await fetch("https://api.alasdia.com/workspaces/me", {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    const workspaces = await res.json()
    console.log("WORKSPACES:", workspaces)
    const select = document.getElementById("workspaceSwitcher")
    select.innerHTML = workspaces.map(w => `
      <option value="${w.id}">
        ${w.name}
      </option>
    `).join("")
    const savedWorkspace = localStorage.getItem("workspace_id")
    if (
      savedWorkspace &&
      workspaces.some(w => String(w.id) === savedWorkspace)
    ) {
      select.value = savedWorkspace
    } else if (workspaces.length > 0) {
      select.value = workspaces[0].id
      localStorage.setItem("workspace_id", workspaces[0].id)
      await loadUsers()
    }
    select.addEventListener("change", async () => {
      const workspaceId = select.value
      console.log("SWITCH TO:", workspaceId)
      localStorage.setItem("workspace_id", workspaceId)
      const url = new URL(window.location.href)
      url.searchParams.set("workspace_id", workspaceId)
      window.history.replaceState({}, document.title, url.pathname + url.search)
      await Promise.all([
        loadProfileHeader(),
        loadPlan(),
        loadKPI(),
        chargerWallet(),
        loadLinks(),
        loadUser()
      ])
    })
  } catch (err) {
    console.error("Erreur loadWorkspaces:", err)
  }
}
loadWorkspaces();
async function submitWithdraw() {
  const btn = document.getElementById("confirmWithdrawBtn");
  btn.innerText = "Envoi...";
  btn.disabled = true;
  try {
    const res = await fetch("https://api.alasdia.com/withdraw", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      },
      body: JSON.stringify({
        amount: parseFloat(document.getElementById("withdrawAmount").value)
      })
    });
    const data = await res.json();
    console.log("RESPONSE /withdraw:", data);
    if (!res.ok) {
      console.log("DETAIL:", data.detail);
      let message = "Impossible d'effectuer ce retrait";
      if (data.detail === "Permission insuffisante") {
        message = "Seul le propriétaire du compte peut effectuer un retrait";
      } else if (typeof data.detail === "string") {
        message = data.detail;
      }
      if (data.detail?.next_available_at) {
        const date = new Date(data.detail.next_available_at);
        message += `\n⏳ Disponible le ${date.toLocaleDateString("fr-FR")}`;
      }
      showToast(message, "error");
      btn.innerText = "Confirmer";
      btn.disabled = false;
      return;
    }
    if (!data.id) {
      console.error("❌ ID manquant :", data);
      showToast("Erreur: ID retrait manquant");
      btn.innerText = "Confirmer";
      btn.disabled = false;
      return;
    }
    const withdrawId = data.id;
    console.log("WITHDRAW ID:", withdrawId);
    const res2 = await fetch(`https://api.alasdia.com/withdraw/${withdrawId}/process`, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data2 = await res2.json();
    if (!res2.ok) {
      showToast(data2.detail || "Erreur process");
      return;
    }
    showToast("Retrait envoyé !");
    const modalEl = document.getElementById("withdrawModal");
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.hide();
    btn.innerText = "Confirmer";
    btn.disabled = false;
  } catch (err) {
    console.error(err);
    showToast("Erreur serveur")
    btn.innerText = "Confirmer";
    btn.disabled = false;
  }
}
window.archivedLink = async function(id) {
  try {
    const res = await fetch(`https://api.alasdia.com/archive/${id}`, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.detail || "Erreur");
      return;
    }
    showToast("Lien archivé ✅");
    const el = document.getElementById(`link-${id}`);
    if (el) {
      el.remove();
    }
  } catch (err) {
    console.error(err);
    alert("Erreur serveur");
  }
}
async function upgrade(plan) {
  const token = localStorage.getItem("token")
  const res = await fetch("https://api.alasdia.com/create-checkout-session", {
    method: "POST",
    headers: {
      "Authorization": "Bearer " + token,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
        plan: plan 
    })
  })
   console.log("STATUS:", res.status)
   const data = await res.json()
   console.log("RESPONSE =", data)
   if (!data.url) {
     alert("Erreur backend")
     return
   }
   window.location.href = data.url
}
const params = new URLSearchParams(window.location.search)
if (params.get("upgrade") === "1") {
    console.log("LIMIT REACHED")
    upgrade("pro")
}
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
function updateUpgradeModal(plan, feature) {
  document.querySelectorAll(".plan-card")
    .forEach(card => {
      card.classList.remove("plan-disabled");
    });
  if (feature === "multi-users") {
    document.querySelector(".plan-starter")
      .classList.add("plan-disabled");
    document.querySelector(".plan-pro")
      .classList.add("plan-disabled");
    return;
  }
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
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const icons = { success: "✅", error: "⚠️", warning: "⏳" };
  const toast = document.createElement("div");
  toast.className = `toast-notif-item ${type}`;
  toast.innerHTML = `<span class="icon">${icons[type] || icons.success}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}