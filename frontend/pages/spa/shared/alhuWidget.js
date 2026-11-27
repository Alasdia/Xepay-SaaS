// Widget flottant Alhu — assistant marchand en lecture seule (demandé
// le 2026-11-27), monté UNE SEULE FOIS par app.js (comme la sidebar/le
// bandeau du haut), survit à toute navigation interne - contrairement
// aux modals des vues, qui sont recréés/détruits à chaque montage de
// vue. Historique de conversation gardé en mémoire ici (perdu au
// rechargement de la page) : voir backend/services/alhu_service.py,
// rien n'est persisté côté serveur pour ce premier chantier - le client
// renvoie tout l'historique à chaque appel.
import { apiFetch } from "../core/apiClient.js";

let messages = [];
let panelEl = null;
let messagesEl = null;
let formEl = null;
let inputEl = null;
let sendBtnEl = null;

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function appendMessageBubble(role, text) {
  const bubble = document.createElement("div");
  bubble.className = `alhu-bubble alhu-bubble--${role}`;
  bubble.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

async function handleSubmit(e) {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  messages.push({ role: "user", content: text });
  appendMessageBubble("user", text);
  inputEl.value = "";
  inputEl.disabled = true;
  sendBtnEl.disabled = true;
  const typingBubble = appendMessageBubble("assistant", "...");

  try {
    const res = await apiFetch("/alhu/chat", { method: "POST", body: { messages } });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Alhu n'est pas disponible pour le moment.");
    typingBubble.innerHTML = escapeHtml(data.reply).replace(/\n/g, "<br>");
    messages.push({ role: "assistant", content: data.reply });
  } catch (err) {
    typingBubble.innerHTML = escapeHtml(err.message || "Erreur de connexion à Alhu.");
    // Message d'erreur retiré de l'historique envoyé au serveur (demande
    // normale : un échec réseau ne doit jamais polluer le contexte de la
    // conversation avec un rôle "assistant" factice).
    messages.pop();
  } finally {
    inputEl.disabled = false;
    sendBtnEl.disabled = false;
    inputEl.focus();
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }
}

function togglePanel(forceOpen) {
  const willOpen = forceOpen ?? panelEl.style.display === "none";
  panelEl.style.display = willOpen ? "flex" : "none";
  if (willOpen) inputEl.focus();
}

export function initAlhuWidget() {
  if (document.getElementById("alhu-widget-toggle")) return;

  document.body.insertAdjacentHTML(
    "beforeend",
    `
    <button type="button" id="alhu-widget-toggle" title="Alhu, votre assistant Xepay">
      <i class="fa-solid fa-robot"></i>
    </button>
    <div id="alhu-widget-panel" style="display:none;">
      <div id="alhu-widget-header">
        <span>Alhu</span>
        <button type="button" id="alhu-widget-close" aria-label="Fermer">×</button>
      </div>
      <div id="alhu-widget-messages"></div>
      <form id="alhu-widget-form">
        <input type="text" id="alhu-widget-input" placeholder="Posez une question sur votre compte..." autocomplete="off">
        <button type="submit" id="alhu-widget-send" aria-label="Envoyer"><i class="fa-solid fa-paper-plane"></i></button>
      </form>
    </div>
    `
  );

  panelEl = document.getElementById("alhu-widget-panel");
  messagesEl = document.getElementById("alhu-widget-messages");
  formEl = document.getElementById("alhu-widget-form");
  inputEl = document.getElementById("alhu-widget-input");
  sendBtnEl = document.getElementById("alhu-widget-send");

  appendMessageBubble("assistant", "Bonjour, je suis Alhu. Je peux répondre à vos questions sur votre solde, vos transactions récentes ou votre dossier de création de société (LLC) - je ne peux rien modifier.");

  // Ouvre toujours (demande du 2026-11-27) - ce bouton ne referme plus
  // le panneau s'il est déjà ouvert, seul #alhu-widget-close le fait.
  document.getElementById("alhu-widget-toggle").addEventListener("click", () => togglePanel(true));
  document.getElementById("alhu-widget-close").addEventListener("click", () => togglePanel(false));
  formEl.addEventListener("submit", handleSubmit);
}
