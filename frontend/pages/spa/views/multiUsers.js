// Vue "Multi-utilisateurs" — port fidèle de multi-users.html + multi-users.js.
// La consommation de ?token=&workspace_id= (atterrissage depuis le lien
// d'invitation envoyé par email, backend users.py /invites/accept) est
// traitée au niveau du shell (spa/app.js), pas ici.
import { apiFetch } from "../core/apiClient.js";
import { getWorkspaceId, setWorkspaceId } from "../core/state.js";
import { setViewStyles } from "../core/styleLoader.js";
import { refreshPlanBadge } from "../sidebar.js";

const TEMPLATE = `
<div id="businessLock" class="feature-lock d-none">
  <div class="feature-lock-card">
    <div class="lock-icon"><i class="fa-solid fa-lock"></i></div>
    <h2>Multi-utilisateurs</h2>
    <p>Invitez des collaborateurs, gérez les rôles, les permissions et plusieurs espaces de travail.</p>
    <div class="lock-features">
      <span>✓ Équipes</span><span>✓ Permissions</span><span>✓ Workspaces</span><span>✓ Collaboration</span>
    </div>
    <button class="btn btn-warning fw-bold" onclick="upgrade('business')">⚡ Passer à Business</button>
  </div>
</div>
<main>
  <div class="header">
    <div>
      <div class="header-title text-muted"><i class="fa-solid fa-users"></i> Multi-utilisateurs <span class="badge-web3 business">BUSINESS</span></div>
      <p>Gérez votre équipe, les rôles et les permissions d'accès à votre espace marchand.</p>
    </div>
    <div style="display:flex; gap:10px;">
      <select id="workspaceSwitcher"></select>
      <button class="btn btn-primary" onclick="openModal()">＋ Ajouter un utilisateur</button>
    </div>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-label">Utilisateurs actifs</div>
      <div class="stat-value" id="stat-active">0</div>
      <div class="stat-sub">sur 10 inclus</div>
    </div>
    <div class="stat">
      <div class="stat-label">Invitations en attente</div>
      <div class="stat-value yellow" id="stat-pending">0</div>
      <div class="stat-sub">expire sous 7 jours</div>
    </div>
    <div class="stat">
      <div class="stat-label">Administrateurs</div>
      <div class="stat-value pink" id="stat-admins">0</div>
      <div class="stat-sub">accès complet</div>
    </div>
    <div class="stat">
      <div class="stat-label">Dernière activité</div>
      <div class="stat-value green" id="stat-last" style="font-size:20px;">14:32</div>
      <div class="stat-sub" id="stat-last-label">--</div>
    </div>
  </div>
  <div class="toolbar">
    <div class="search"><input type="text" id="search" placeholder="Rechercher par nom ou email…" /></div>
    <div class="filter-chip-row">
      <button class="filter-chip active" data-role="all">Tous</button>
      <button class="filter-chip" data-role="Admin">Admin</button>
      <button class="filter-chip" data-role="Manager">Manager</button>
      <button class="filter-chip" data-role="Membre">Membre</button>
      <button class="filter-chip" data-role="Lecteur">Lecteur</button>
    </div>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Utilisateur</th><th>Rôle</th><th>Statut</th><th>Dernière connexion</th><th style="text-align:right;">Actions</th></tr></thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</main>
<div class="invite-modal-backdrop" id="modal">
  <div class="custom-modal">
    <h2 id="modal-title">Inviter un utilisateur</h2>
    <p class="subtitle">L'utilisateur recevra un email pour rejoindre votre espace.</p>
    <form id="user-form">
      <div class="field"><label>Nom complet</label><input type="text" id="f-name" required placeholder="Jean Dupont" /></div>
      <div class="field"><label>Email</label><input type="email" id="f-email" required placeholder="jean@entreprise.com" /></div>
      <div class="field">
        <label>Rôle</label>
        <select id="f-role"><option>Admin</option><option selected>Manager</option><option>Membre</option><option>Lecteur</option></select>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-ghost" onclick="closeModal()">Annuler</button>
        <button type="submit" class="btn btn-primary" id="submit-btn">Envoyer l'invitation</button>
      </div>
    </form>
  </div>
</div>
`;

export function mount(container) {
  setViewStyles(["multi-users.css"]);
  container.innerHTML = TEMPLATE;

  let users = [];
  let filter = "all";
  const boundListeners = [];
  function on(target, type, fn) {
    target.addEventListener(type, fn);
    boundListeners.push({ target, type, fn });
  }

  async function checkBusinessAccess() {
    const res = await apiFetch("/me");
    const user = await res.json();
    const lock = document.getElementById("businessLock");
    const main = container.querySelector("main");
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
      const res = await apiFetch("/users");
      users = await res.json();
      const now = new Date();
      document.getElementById("stat-last").textContent = now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
      document.getElementById("stat-last-label").textContent = "Maintenant";
      renderTable();
    } catch (err) {
      console.error("Erreur loadUsers:", err);
    }
  }

  async function loadInvites() {
    const res = await apiFetch("/invites");
    const invites = await res.json();
    document.getElementById("stat-pending").textContent = invites.length;
    const sub = document.querySelector("#stat-pending").parentElement.querySelector(".stat-sub");
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
        sub.textContent = `Expire dans ${days}j ${hours}h ${minutes}m ${seconds}s`;
      }
      updateCountdown();
      const timer = setInterval(updateCountdown, 1000);
      timers.push(timer);
    } else {
      sub.textContent = "Aucune invitation";
    }
  }

  async function sendInvite() {
    const email = document.getElementById("f-email").value;
    const role = document.getElementById("f-role").value;
    const res = await apiFetch("/invites", { method: "POST", body: { email, role } });
    const data = await res.json();
    if (data.invite_link) {
      alert("Lien:\n" + data.invite_link);
      closeModal();
      await loadInvites();
    } else {
      alert(data.detail || "Erreur inconnue");
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendInvite();
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

  function renderTable() {
    const q = document.getElementById("search").value.toLowerCase();
    const tbody = document.getElementById("tbody");
    const rows = users.filter((u) => filter === "all" || u.role === filter).filter((u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q));
    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:40px; color:var(--text-muted);">Aucun utilisateur trouvé.</td></tr>`;
    } else {
      tbody.innerHTML = rows
        .map((u) => {
          const idx = users.indexOf(u);
          const initials = u.name.split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
          const statusLabel = u.status === "active" ? "Actif" : u.status === "pending" ? "En attente" : "Suspendu";
          return `
          <tr>
            <td>
              <div class="user-cell">
                <div class="avatar" style="background:${u.color};">${initials}</div>
                <div><div class="user-name">${u.name}</div><div class="user-email">${u.email}</div></div>
              </div>
            </td>
            <td><span class="role-pill role-${u.role.toLowerCase()}">${u.role}</span></td>
            <td><span class="status-dot status-${u.status}">${statusLabel}</span></td>
            <td style="color:var(--text-dim);">${formatLastLogin(u.last)}</td>
            <td>
              <div class="actions">
                <button class="icon-btn" title="Modifier le rôle" onclick="cycleRole(${idx})">🎚</button>
                <button class="icon-btn" title="${u.status === "suspended" ? "Réactiver" : "Suspendre"}" onclick="toggleSuspend(${idx})">${u.status === "suspended" ? "▶" : "⏸"}</button>
                <button class="icon-btn danger" title="Supprimer" onclick="deleteUser(${idx})">🗑</button>
              </div>
            </td>
          </tr>`;
        })
        .join("");
    }
    document.getElementById("stat-active").textContent = users.filter((u) => u.status === "active").length;
    document.getElementById("stat-admins").textContent = users.filter((u) => u.role === "Admin").length;
  }

  function setFilter(el) {
    container.querySelectorAll(".filter-chip").forEach((c) => c.classList.remove("active"));
    el.classList.add("active");
    filter = el.dataset.role;
    renderTable();
  }

  function openModal() {
    document.getElementById("modal").classList.add("show");
  }
  function closeModal() {
    document.getElementById("modal").classList.remove("show");
    document.getElementById("user-form").reset();
  }

  async function cycleRole(i) {
    const u = users[i];
    const roles = ["Admin", "Manager", "Membre", "Lecteur"];
    const newRole = roles[(roles.indexOf(u.role) + 1) % roles.length];
    await apiFetch(`/users/${u.id}/role`, { method: "PUT", body: { role: newRole } });
    loadUsers();
  }

  async function toggleSuspend(i) {
    const u = users[i];
    await apiFetch(`/users/${u.id}/toggle`, { method: "POST" });
    loadUsers();
  }

  async function deleteUser(i) {
    const u = users[i];
    if (!confirm(`Supprimer ${u.name} ?`)) return;
    await apiFetch(`/users/${u.id}`, { method: "DELETE" });
    loadUsers();
  }

  async function loadWorkspaces() {
    try {
      const res = await apiFetch("/workspaces/me");
      const workspaces = await res.json();
      const select = document.getElementById("workspaceSwitcher");
      select.innerHTML = workspaces.map((w) => `<option value="${w.id}">${w.name}</option>`).join("");
      const savedWorkspace = getWorkspaceId();
      if (savedWorkspace && workspaces.some((w) => String(w.id) === savedWorkspace)) {
        select.value = savedWorkspace;
      } else if (workspaces.length > 0) {
        select.value = workspaces[0].id;
        setWorkspaceId(workspaces[0].id);
        await loadUsers();
      }
      on(select, "change", async () => {
        setWorkspaceId(select.value);
        users = [];
        renderTable();
        await refreshPlanBadge();
        const allowed = await checkBusinessAccess();
        if (allowed) await loadUsers();
      });
    } catch (err) {
      console.error("Erreur loadWorkspaces:", err);
    }
  }

  const timers = [];

  container.querySelectorAll(".filter-chip").forEach((chip) => on(chip, "click", () => setFilter(chip)));
  on(document.getElementById("search"), "input", renderTable);
  on(document.getElementById("user-form"), "submit", handleSubmit);
  on(document.getElementById("modal"), "click", (e) => {
    if (e.target.id === "modal") closeModal();
  });

  window.openModal = openModal;
  window.closeModal = closeModal;
  window.cycleRole = cycleRole;
  window.toggleSuspend = toggleSuspend;
  window.deleteUser = deleteUser;
  // window.upgrade est exposé globalement par app.js (modale partagée persistante)

  const clockTimer = setInterval(() => {
    const now = new Date();
    document.getElementById("stat-last").textContent = now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  }, 60000);
  timers.push(clockTimer);

  (async () => {
    await loadWorkspaces();
    await refreshPlanBadge();
    const allowed = await checkBusinessAccess();
    if (allowed) {
      await loadUsers();
      await loadInvites();
    }
  })();

  return {
    unmount() {
      timers.forEach(clearInterval);
      boundListeners.forEach(({ target, type, fn }) => target.removeEventListener(type, fn));
      delete window.openModal;
      delete window.closeModal;
      delete window.cycleRole;
      delete window.toggleSuspend;
      delete window.deleteUser;
    },
  };
}
