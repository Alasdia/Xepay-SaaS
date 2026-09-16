let users = []
async function checkBusinessAccess() {
  const res = await fetch("https://api.alasdia.com/me", {
    headers: {
      Authorization: "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  });
  const user = await res.json();
  const lock = document.getElementById("businessLock");
  const main = document.querySelector("main");
  if (user.plan !== "business") {
    main.classList.add("workspace-locked");
    lock.classList.remove("d-none");
    return false;
  }
  main.classList.remove("workspace-locked");
  lock.classList.add("d-none");
  return true;
}
async function loadUsers() {
  try {
    const workspaceId = localStorage.getItem("workspace_id")
    console.log("WORKSPACE ACTIVE =", workspaceId)
    const res = await fetch("https://api.alasdia.com/users", {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": workspaceId
      }
    })
    const data = await res.json()
    console.log("USERS LOADED:", data)
    users = data
    const now = new Date()
    const time = now.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit"
    })
    document.getElementById("stat-last").textContent = time
    document.getElementById("stat-last-label").textContent = "Maintenant"
    renderTable()
  } catch (err) {
    console.error("Erreur loadUsers:", err)
  }
}
async function loadInvites() {
  const res = await fetch("https://api.alasdia.com/invites", {
    headers: {
      Authorization: "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  });
  const invites = await res.json();
  console.log("DATA INVITES:", invites)
  document.getElementById("stat-pending").textContent = invites.length;
  const sub = document.querySelector("#stat-pending")
    .parentElement
    .querySelector(".stat-sub");
  if (invites.length > 0) {
    const expiresAt = new Date(invites[0].expires_at);
    function updateCountdown() {
      const now = new Date();
      let diff = expiresAt - now;
      if (diff <= 0) {
        sub.textContent = "Invitation expirée";
        clearInterval(timer);
        return;
      }
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      diff %= 1000 * 60 * 60 * 24;
      const hours = Math.floor(diff / (1000 * 60 * 60));
      diff %= 1000 * 60 * 60;
      const minutes = Math.floor(diff / (1000 * 60));
      diff %= 1000 * 60;
      const seconds = Math.floor(diff / 1000);
      sub.textContent =
        `Expire dans ${days}j ${hours}h ${minutes}m ${seconds}s`;
    }
    updateCountdown();
    const timer = setInterval(updateCountdown, 1000);
  } else {
    sub.textContent = "Aucune invitation";
  }
}
async function sendInvite() {
  console.log("🚀 FETCH VERSION")
  const email = document.getElementById("f-email").value
  const role = document.getElementById("f-role").value
  const res = await fetch("https://api.alasdia.com/invites", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    },
    body: JSON.stringify({ email, role })
  })
  const data = await res.json()
  console.log("INVITE:", data)
  if (data.invite_link) {
    alert("Lien:\n" + data.invite_link)
    closeModal() 
    await loadInvites();
  } else {
    alert(data.detail || "Erreur inconnue")
  }
}
function handleSubmit(e) {
  e.preventDefault();
  sendInvite()
  const data = {
    name: document.getElementById('f-name').value,
    email: document.getElementById('f-email').value,
    role: document.getElementById('f-role').value
  };
  console.log("INVITATION:", data);
}
let filter = "all";
let mode = "create";
function renderTable() {
  const q = document.getElementById("search").value.toLowerCase();
  const tbody = document.getElementById("tbody");
  const rows = users
    .filter(u => filter === "all" || u.role === filter)
    .filter(u => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--text-muted);">Aucun utilisateur trouvé.</td></tr>`;
  } else {
    tbody.innerHTML = rows.map((u, i) => {
      const idx = users.indexOf(u);
      const initials = u.name.split(' ').map(s => s[0]).slice(0,2).join('').toUpperCase();
      const statusLabel = u.status === "active" ? "Actif" : u.status === "pending" ? "En attente" : "Suspendu";
      return `
        <tr>
          <td>
            <div class="user-cell">
              <div class="avatar" style="background:${u.color};">${initials}</div>
              <div>
                <div class="user-name">${u.name}</div>
                <div class="user-email">${u.email}</div>
              </div>
            </div>
          </td>
          <td><span class="role-pill role-${u.role.toLowerCase()}">${u.role}</span></td>
          <td><span class="status-dot status-${u.status}">${statusLabel}</span></td>
          <td style="color:var(--text-dim);">${formatLastLogin(u.last)}</td>
          <td>
            <div class="actions">
              <button class="icon-btn" title="Modifier le rôle" onclick="cycleRole(${idx})">🎚</button>
              <button class="icon-btn" title="${u.status==='suspended'?'Réactiver':'Suspendre'}" onclick="toggleSuspend(${idx})">${u.status==='suspended'?'▶':'⏸'}</button>
              <button class="icon-btn danger" title="Supprimer" onclick="deleteUser(${idx})">🗑</button>
            </div>
          </td>
        </tr>`;
    }).join('');
  }
  document.getElementById('stat-active').textContent  = users.filter(u => u.status === 'active').length;
  document.getElementById('stat-admins').textContent  = users.filter(u => u.role === 'Admin').length;
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
      return `Hier à ${last.toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit"
      })}`;
  }
  return last.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
  });
}
function setFilter(el) {
  document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  filter = el.dataset.role;
  renderTable();
}
const roles = ['Admin', 'Manager', 'Membre', 'Lecteur'];
function openModal() {
  document.getElementById('modal').classList.add('show');
}
function closeModal() {
  document.getElementById('modal').classList.remove('show');
  document.getElementById('user-form').reset();
}
document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});
renderTable();
async function cycleRole(i) {
  const u = users[i]
  const roles = ['Admin', 'Manager', 'Membre', 'Lecteur']
  const newRole = roles[(roles.indexOf(u.role) + 1) % roles.length]
  await fetch(`https://api.alasdia.com/users/${u.id}/role`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    },
    body: JSON.stringify({ role: newRole })
  })
  loadUsers()
}
async function toggleSuspend(i) {
  const u = users[i]
  await fetch(`https://api.alasdia.com/users/${u.id}/toggle`, {
    method: "POST",
    headers: {
      Authorization: "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  loadUsers()
}
async function loadCurrentUser() {
  try {
    const res = await fetch("https://api.alasdia.com/me", {
      headers: {
        Authorization: "Bearer " + localStorage.getItem("token"),
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    })
    const user = await res.json()
    console.log("CURRENT USER:", user)
    console.log("PLAN USER =", user.plan)
    renderPlanBadge(user.plan)
  } catch (err) {
    console.error("Erreur user:", err)
  }
}
function renderPlanBadge(plan) {
  const el = document.getElementById("badge-plan")
  el.className = "badge-web3"
  if (plan === "pro") {
    el.classList.add("pro")
    el.textContent = "PRO"
  } 
  else if (plan === "business") {
    el.classList.add("business")
    el.textContent = "BUSINESS"
  } 
  else {
    el.classList.add("free")
    el.textContent = "FREE"
    el.style.opacity = "0.6"
  }
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
      users = []
      renderTable()
      await loadCurrentUser();
      const allowed = await checkBusinessAccess();
      if (allowed) {
        await loadUsers();
      }
    })
  } catch (err) {
    console.error("Erreur loadWorkspaces:", err)
  }
}
async function deleteUser(i) {
  const u = users[i]
  if (!confirm(`Supprimer ${u.name} ?`)) return
  await fetch(`https://api.alasdia.com/users/${u.id}`, {
    method: "DELETE",
    headers: {
      Authorization: "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  loadUsers()
}
async function submitUser(e) {
  e.preventDefault()
  const name = document.getElementById("f-name").value
  const email = document.getElementById("f-email").value
  const role = document.getElementById("f-role").value
  try {
    const res = await fetch("https://api.alasdia.com/users", {
      method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer " + localStorage.getItem("token"),
          "X-Workspace-Id": localStorage.getItem("workspace_id")
        },
        body: JSON.stringify({
          name: name,
          email: email,
          role: role
        })
    })
    const data = await res.json()
    console.log("RESPONSE:", data)
    if (!res.ok) {
      console.error("Erreur API", res.status)
      return
    }
    closeModal()
    loadUsers()
  } catch (err) {
    console.error("Erreur:", err)
  }
}
const params = new URLSearchParams(window.location.search);
const token = params.get("token");
const workspaceId = params.get("workspace_id");
if (token) {
  localStorage.setItem("token", token);
}
if (workspaceId) {
  localStorage.setItem("workspace_id", workspaceId);
}
async function init() {
  await loadWorkspaces()
  await loadCurrentUser();
  const allowed = await checkBusinessAccess();
  if (allowed) {
    await loadUsers();
    await loadInvites();
  }
}
init();
setInterval(() => {
  const now = new Date()
  document.getElementById("stat-last").textContent =
    now.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit"
    })
  }, 60000)
function showUpgradeModal() {
  const modalEl = document.getElementById("modalUpgrade");
  modalEl.querySelectorAll(".reveal").forEach(el => {
    el.classList.remove("visible");
  });
  const modal = new bootstrap.Modal(modalEl, {
    backdrop: true,
    keyboard: true
  });
  modal.show();
  setTimeout(() => {
    modalEl.querySelectorAll(".reveal").forEach((el, index) => {
      setTimeout(() => {
        el.classList.add("visible");
      }, index * 150);
    });
  }, 300);
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