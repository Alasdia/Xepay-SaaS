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
let toggleBtnEl = null;
let badgeEl = null;

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

// Consomme le flux NDJSON de POST /alhu/chat (demande du 2026-11-27 :
// "montrer que le marchand réfléchit... les réponses défilent ligne
// par ligne... voir que la réflexion est en cours" pendant un appel
// d'outil) - fetch()+ReadableStream, jamais res.json() (qui attendrait
// la fin complète de la réponse avant d'afficher quoi que ce soit) ni
// EventSource (GET uniquement, incompatible avec X-CSRF-Token sur ce
// POST). Chaque ligne est un évènement JSON : "status" (un outil est en
// cours d'exécution, ex. "💰 Je consulte votre solde..."), "delta" (un
// morceau de texte de la réponse finale, affiché au fur et à mesure),
// "done" (texte complet, poussé dans l'historique) ou "error".
async function handleSubmit(e) {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  messages.push({ role: "user", content: text });
  appendMessageBubble("user", text);
  inputEl.value = "";
  inputEl.disabled = true;
  sendBtnEl.disabled = true;
  const typingBubble = appendMessageBubble("assistant", "Alhu réfléchit...");
  typingBubble.classList.add("alhu-bubble--status");

  let fullText = "";
  let sawDelta = false;

  try {
    const res = await apiFetch("/alhu/chat", { method: "POST", body: { messages } });
    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Alhu n'est pas disponible pour le moment.");
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Dernière entrée = ligne potentiellement incomplète (coupée en
      // plein milieu par un chunk réseau) - remise en attente du
      // prochain morceau, jamais parsée telle quelle.
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        const evt = JSON.parse(line);
        if (evt.type === "status") {
          if (!sawDelta) typingBubble.innerHTML = escapeHtml(evt.text);
        } else if (evt.type === "delta") {
          if (!sawDelta) {
            sawDelta = true;
            typingBubble.classList.remove("alhu-bubble--status");
          }
          fullText += evt.text;
          typingBubble.innerHTML = escapeHtml(fullText).replace(/\n/g, "<br>");
          messagesEl.scrollTop = messagesEl.scrollHeight;
        } else if (evt.type === "done") {
          fullText = evt.reply ?? fullText;
          typingBubble.classList.remove("alhu-bubble--status");
          typingBubble.innerHTML = escapeHtml(fullText).replace(/\n/g, "<br>");
          messages.push({ role: "assistant", content: fullText });
        } else if (evt.type === "error") {
          throw new Error(evt.message || "Erreur de connexion à Alhu.");
        }
      }
    }
  } catch (err) {
    typingBubble.classList.remove("alhu-bubble--status");
    typingBubble.innerHTML = escapeHtml(err.message || "Erreur de connexion à Alhu.");
    // Jamais poussé dans messages (demande normale : seul le handler
    // "done" ci-dessus ajoute une vraie réponse complète à l'historique
    // - un échec, même après un début de texte affiché, ne doit jamais
    // polluer le contexte envoyé au prochain appel).
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
  if (willOpen) {
    inputEl.focus();
    // Le marchand vient de voir la conversation : le badge n'a plus de
    // raison d'être, qu'il ait été posé par un message proactif ou non.
    badgeEl.style.display = "none";
  }
}

// Message proactif (demande du 2026-11-27, ex: Paramètres > Compte
// Stripe Connect quand le statut n'est pas "actif") - Alhu parle le
// premier, sans question préalable du marchand. Poussé dans `messages`
// comme un VRAI tour "assistant" (pas juste affiché visuellement) :
// sinon un "oui" de réponse du marchand n'aurait aucun contexte côté
// modèle au prochain appel, qui ignorerait tout de cette suggestion.
// La déduplication "une seule fois par visite" est de la responsabilité
// de l'appelant (ex. un flag module-level dans parametres.js) - ce
// widget ne sait rien de QUAND il est pertinent de reproposer, il
// affiche juste ce qu'on lui demande d'afficher.
export function alhuProactiveMessage(text, { openPanel = true } = {}) {
  if (!messagesEl) return;
  messages.push({ role: "assistant", content: text });
  appendMessageBubble("assistant", text);
  if (openPanel) {
    togglePanel(true);
  } else {
    // Panneau fermé (demande du 2026-11-27, moins intrusif qu'une
    // ouverture forcée) : un badge sur le bouton flottant signale qu'il
    // s'est passé quelque chose, sans interrompre le marchand.
    badgeEl.style.display = "block";
  }
}

export function initAlhuWidget() {
  if (document.getElementById("alhu-widget-toggle")) return;

  document.body.insertAdjacentHTML(
    "beforeend",
    `
    <button type="button" id="alhu-widget-toggle" title="Alhu, votre assistant Xepay">
      <i class="fa-solid fa-robot"></i>
      <span id="alhu-widget-badge" style="display:none;"></span>
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
  toggleBtnEl = document.getElementById("alhu-widget-toggle");
  badgeEl = document.getElementById("alhu-widget-badge");

  appendMessageBubble("assistant", "Bonjour, je suis Alhu. Je peux répondre à vos questions sur votre solde, vos transactions récentes ou votre dossier de création de société (LLC) - je ne peux rien modifier.");

  // Ouvre toujours (demande du 2026-11-27) - ce bouton ne referme plus
  // le panneau s'il est déjà ouvert, seul #alhu-widget-close le fait.
  toggleBtnEl.addEventListener("click", () => togglePanel(true));
  document.getElementById("alhu-widget-close").addEventListener("click", () => togglePanel(false));
  formEl.addEventListener("submit", handleSubmit);
}
