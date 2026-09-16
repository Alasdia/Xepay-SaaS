document.addEventListener("DOMContentLoaded", async () => {
  const token = localStorage.getItem("token")
  if (!token) {
    window.location.href = "login.html"
    return
  }
  const res = await fetch("https://api.alasdia.com/me", {
    headers: {
      "Authorization": "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    }
  })
  const user = await res.json()
  if (user.plan === "free") {
    document.body.classList.add("locked-page");
    const lock = document.getElementById("links-lock");
    lock.classList.remove("d-none");
    return;
  }
})
let links = []
let offset = 0;
const limit = 10;
let isLoading = false;
  const currencySymbols = {
    XOF: "FCFA",
    USD: "$",
    EUR: "€",
}
async function chargerLiens() {
  const listeLiens = document.getElementById("liste-liens");
  const compteur = document.getElementById("compteur-liens");
  const barre = document.getElementById("barre-liens");
  const aucun = document.getElementById("aucun-lien");
  if (!listeLiens) return;
  if (isLoading) return;
  isLoading = true;
    const token = localStorage.getItem("token")
    console.log("TOKEN =", token)
    if (!token) {
      window.location.href = "login.html"
      return
    }
    const res = await fetch(
      `https://api.alasdia.com/links?limit=${limit}&offset=${offset}`, 
      { headers: { 
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      } } 
    );
    if (!res.ok) {
      const error = await res.text()
      console.error("❌ Erreur API :", error)        
      if (error.includes("Token expiré")) {
        localStorage.clear()
        window.location.href = "login.html"
      }
      return
    }
    const liens = await res.json();
    const totalLiens = offset + liens.length;
    if (compteur) {
      compteur.innerText = `${totalLiens}/${limit}`;
    }
    if (barre) {
      barre.style.width = `${(totalLiens / limit) * 100}%`;
    }
    console.log("LIENS =", liens)
    console.log("REPONSE BACKEND =", liens)
    if (liens.length === 0 && offset === 0) {
      aucun.classList.remove("d-none")
      isLoading = false
      return
    }else {
      aucun.classList.add("d-none")
    }
    offset += liens.length;
  function getStatusLabel(lien) {
    if (lien.status === "paid") return "Payé";
    if (!lien.active) return "Expiré";
    if (lien.status === "pending") return "En attente";
    return "Actif";
  }
  function getStatusClass(lien) {
    if (lien.status === "paid") return "status-paid";
    if (!lien.active) return "status-expired";
    if (lien.status === "pending") return "status-pending";
    return "status-active";
  }
    liens
      .filter(lien => !lien.archived)
      .forEach(lien => {
       console.log(lien)
       console.log(lien.status)
       const name = lien.name && lien.name.trim() !== ""
        ? lien.name
        : "Lien de paiement"
       const currency = lien.currency || "XOF";
       const amount = typeof lien.amount === "number"
        ? `${new Intl.NumberFormat('fr-FR').format(lien.amount)} ${lien.currency}`
        : "Montant invalide"
       const div = document.createElement("div");
       div.className = "lien-card";
       div.setAttribute("data-id", lien.id);
       const exp = new Date(lien.expires_at)
       const now = new Date()
       const diff = exp - now
       const minutes = Math.floor(diff / 60000)
       const seconds = Math.floor((diff % 60000) / 1000)
       const heure = exp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
       let expirationLabel = ""
       let color = "orange"
       if (diff <= 0) {
        expirationLabel = "Expiré"
        color = "red"
       }
       else if (minutes === 0) {
        expirationLabel = `expire dans ${seconds}s`
        color = "#ff4d4d"
       }
       else {
        expirationLabel = `expire dans ${minutes} min (${heure})`
       }
       div.innerHTML = `
        <div class="lien-content">
          <div class="lien-header ">
            <div class="lien-infos">
              <h6>${lien.name}</h6>
              <small style="color:${color}; font-weight:500;">
                ${expirationLabel}
              </small>
              <div class="montant">${amount}</div>
              </div>
              <div class="lien-status ${getStatusClass(lien)}">
                ${getStatusLabel(lien)}
              </div>
            </div>
          </div>
          <div class="lien-url ${getStatusClass(lien)}">
            ${lien.url}
          </div>
          <div class="actions">
            ${
              lien.status === "pending"
                ? `
                  <button
                    class="btn-copy-actif"
                    onclick="copier('${lien.url}')"
                  >
                    Copier
                  </button>
                `
                : ""
            }
            ${
              lien.status === "paid"
                ? `
                  <button
                    class="btn-delete-neutral"
                    onclick="archiverLien('${lien.id}')"
                  >
                    Archiver
                  </button>
                `
                : `
                  <button
                    class="${
                      lien.status === 'expired'
                        ? "btn-delete-actif"
                        : "btn-delete-neutral"
                    }"
                    onclick="supprimer('${lien.id}')"
                  >
                    Supprimer
                  </button>
                `
            }
          </div>
        </div>
      `;
        listeLiens.appendChild(div);
    });
    isLoading = false;
}
function closeModalCleanly(modalId) {
  const modalEl = document.getElementById(modalId);
  const modal = bootstrap.Modal.getInstance(modalEl);
  if (modal) modal.hide();
    setTimeout(() => {
    document.body.classList.remove("modal-open");
    document.body.style.removeProperty("overflow");
    document.body.style.removeProperty("padding-right");
    document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
  }, 300);
}
async function genererLien() {
  const name = document.getElementById("nom-lien").value || "Lien de paiement"
  const rawAmount = document.getElementById("montant-lien").value 
  const errorBox = document.getElementById("error-box")
  if (!rawAmount) {
    errorBox.innerText = "Le montant est obligatoire"
    errorBox.style.display = "block"
    return
  }
  const amount = parseFloat(rawAmount)
  if (isNaN(amount)) {
    alert("Montant invalide")
  }
  const currency = document.getElementById("devise-lien").value
  console.log("🔥 genererLien EXECUTE")
  const email = localStorage.getItem("email")
  const token = localStorage.getItem("token")
  console.log("TOKEN =", token)
  console.log({
    email,
    name,
    amount,
    currency,
    type_amount: typeof amount
  })
  const payload = {
    amount: amount,
    currency: currency,
    source: "links"
  }
  if (name) {
    payload.name = name
  }
  console.log("PAYLOAD ENVOYÉ:", JSON.stringify(payload));
  const res = await fetch("https://api.alasdia.com/links", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + token,
      "X-Workspace-Id": localStorage.getItem("workspace_id")
    },
    body: JSON.stringify(payload)
  })
  if (!res.ok) {
    const err = await res.json();
    alert(err.detail || "Impossible de créer le lien");
    return;
  }
  console.log("EMAIL ENVOYÉ =", email)
  console.log("NAME =", name)
  const data = await res.json();
  console.log(data);
  const successBox = document.getElementById("success-msg")
  successBox.innerText = "Lien créé avec succès ✅"
  successBox.style.display = "block"
  const modalEl = document.getElementById('modalCreationLien');
  if (modalEl) {
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
  }
  document.getElementById("nom-lien").value = "";
  document.getElementById("montant-lien").value = "";
  errorBox.style.display = "none";
  offset = 0;
  document.getElementById("liste-liens").innerHTML = "";
  await chargerLiens();
}
chargerLiens();
window.supprimer = async function supprimer(id) {
  const token = localStorage.getItem("token");
  const carte = document.querySelector(`[data-id="${id}"]`);
  if (carte) carte.remove();
  try {
    await fetch(`https://api.alasdia.com/links/${id}`, {
      method: "DELETE",
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    chargerLiens();
  } catch (e) {
    if (carte) carte.style.opacity = "1";
    alert("Erreur suppression");
  }
};
function copier(url) {
  navigator.clipboard.writeText(url);
  alert("Lien copié !");
}
window.archiverLien = async function archiverLien(id) {
  const token = localStorage.getItem("token");
  const carte = document.querySelector(`[data-id="${id}"]`);
  if (carte) {
    carte.style.opacity = "0.4";
    carte.style.pointerEvents = "none";
  }
  try {
    const response = await fetch(`https://api.alasdia.com/archive/${id}`, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "X-Workspace-Id": localStorage.getItem("workspace_id")
      }
    });
    if (!response.ok) {
      throw new Error("Erreur archivage");
    }
    if (carte) {
      carte.style.transition = "all 0.25s ease";
      carte.style.height = carte.offsetHeight + "px";
      requestAnimationFrame(() => {
        carte.style.opacity = "0";
        carte.style.height = "0";
        carte.style.margin = "0";
        carte.style.padding = "0";
        carte.style.overflow = "hidden";
      });
      setTimeout(() => {
        carte.remove();
      }, 250);
    }
  } catch (error) {
    if (carte) {
      carte.style.opacity = "1";
      carte.style.pointerEvents = "auto";
    }
    alert("Impossible d’archiver ce lien");
  }
};
const scrollBox = document.getElementById("liste-liens-container");
  scrollBox.addEventListener("scroll", () => {
    const scrollTop = scrollBox.scrollTop;
    const visibleHeight = scrollBox.clientHeight;
    const totalHeight = scrollBox.scrollHeight;
    if (scrollTop + visibleHeight >= totalHeight - 50) {
      chargerLiens();
    }
});
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
function showUpgradeModal(feature = null) {
  const plan = window.GLOBAL_PLAN?.plan;
  updateUpgradeModal(plan, feature);
  const modal = new bootstrap.Modal(
    document.getElementById("modalUpgrade")
  );
  modal.show();
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