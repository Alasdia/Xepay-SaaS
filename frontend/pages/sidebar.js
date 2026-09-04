async function initSidebar() {
  const container = document.getElementById("sidebar-container");
  const html = await fetch("sidebar.html").then(r => r.text());
  container.innerHTML = html;

  // Lien actif selon la page courante
  const currentPage = document.body.dataset.page;
  document.querySelectorAll("#sidebar a[data-page]").forEach(a => {
    if (a.dataset.page === currentPage) a.classList.add("active-link");
  });

  // Ajouter workspace_id à tous les liens
  document.querySelectorAll('#sidebar a[href$=".html"]').forEach(link => {
    const url = new URL(link.getAttribute("href"), window.location.origin);
    url.searchParams.set("workspace_id", localStorage.getItem("workspace_id"));
    link.setAttribute("href", url.pathname + url.search);
  });

  // Badge plan
  loadUser();

  // Bouton upgrade
  document.querySelectorAll(".upgrade-btn").forEach(btn => {
    btn.addEventListener("click", () => showUpgradeModal());
  });

  // Hamburger mobile (le code que tu as déjà, dupliqué sur chaque page)
  setupHamburger();
}

function setupHamburger() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  const overlay = document.createElement("div");
  overlay.className = "sidebar-overlay";
  document.body.appendChild(overlay);
  const btn = document.createElement("button");
  btn.className = "dash-hamburger";
  btn.innerHTML = "<span></span><span></span><span></span>";
  document.body.appendChild(btn);
  const open = () => { sidebar.classList.add("open"); overlay.classList.add("active"); btn.classList.add("open"); document.body.style.overflow = "hidden"; };
  const close = () => { sidebar.classList.remove("open"); overlay.classList.remove("active"); btn.classList.remove("open"); document.body.style.overflow = ""; };
  btn.addEventListener("click", () => sidebar.classList.contains("open") ? close() : open());
  overlay.addEventListener("click", close);
  sidebar.querySelectorAll("a").forEach(a => a.addEventListener("click", close));
}

async function loadUser() {
  const token = localStorage.getItem("token");
  const res = await fetch("https://api.alasdia.com/me/user-plan", {
    headers: { Authorization: "Bearer " + token, "X-Workspace-Id": localStorage.getItem("workspace_id") }
  });
  const user = await res.json();
  localStorage.setItem("plan", user.plan);
  updatePlanUI(user.plan);
}

function updatePlanUI(plan) {
  const badge = document.getElementById("badge-plan");
  badge.classList.remove("bg-success", "bg-warning", "bg-danger");
  if (plan === "free") { badge.innerHTML = "🟢 Free"; badge.classList.add("bg-success"); }
  else if (plan === "pro") { badge.innerHTML = "🟡 Pro"; badge.classList.add("bg-warning"); }
  else if (plan === "business") { badge.innerHTML = "🔴 Business"; badge.classList.add("bg-danger"); }
}

document.addEventListener("DOMContentLoaded", initSidebar);