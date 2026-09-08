async function initSidebar() {
  const container = document.getElementById("sidebar-container");
  container.innerHTML = await fetch("sidebar.html").then(r => r.text());
  document.querySelectorAll("#sidebar a[data-page]").forEach(a => {
    if (a.dataset.page === document.body.dataset.page) a.classList.add("active-link");
  });
  document.querySelectorAll('#sidebar a[href$=".html"]').forEach(link => {
    const url = new URL(link.getAttribute("href"), window.location.origin);
    url.searchParams.set("workspace_id", localStorage.getItem("workspace_id"));
    link.setAttribute("href", url.pathname + url.search);
  });
  await loadUser();
  document.querySelectorAll(".upgrade-btn").forEach(btn =>
    btn.addEventListener("click", () => showUpgradeModal())
  );
  setupHamburger();
}
async function loadUser() {
  const res = await fetch("https://api.alasdia.com/me/user-plan", {
    headers: {
      Authorization: "Bearer " + localStorage.getItem("token"),
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  });
  const user = await res.json();
  localStorage.setItem("plan", user.plan);
  updatePlanUI(user.plan);
}
function logout() {
  localStorage.removeItem("token");
  window.location.href = "login.html";
}
function setupHamburger() { /* garde la version existante, une seule fois ici */ }
document.addEventListener("DOMContentLoaded", initSidebar);
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
  window.GLOBAL_PLAN = user;
  localStorage.setItem("plan", user.plan);
  updatePlanUI(user.plan);
}
function updatePlanUI(plan) {
  const badge = document.getElementById("badge-plan");
  badge.className = "badge " + plan; 
  badge.textContent = plan.toUpperCase();
}