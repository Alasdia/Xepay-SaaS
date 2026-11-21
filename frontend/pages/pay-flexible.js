// Page publique de paiement à montant libre - atteinte par redirection
// depuis GET /pay/{token} (backend/routes/lien.py) quand le lien n'a pas
// de montant fixe (Link.amount IS NULL). Jamais de session, jamais de
// cookie : le token dans l'URL est la seule identification du lien, comme
// pour un lien à montant fixe classique.
(function () {
  const BASE_URL = "https://api.xepay.finance";

  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");

  const loadingEl = document.getElementById("pf-loading");
  const errorEl = document.getElementById("pf-error");
  const formEl = document.getElementById("pf-form");
  const nameEl = document.getElementById("pf-name");
  const hintEl = document.getElementById("pf-hint");
  const amountInput = document.getElementById("pf-amount");
  const currencyEl = document.getElementById("pf-currency");
  const formErrorEl = document.getElementById("pf-form-error");
  const submitBtn = document.getElementById("pf-submit");

  const ERROR_MESSAGES = {
    invalid: "Ce lien de paiement n'existe pas ou plus.",
    not_flexible: "Ce lien de paiement n'est pas configuré pour un montant libre.",
    already_paid: "Ce lien de paiement a déjà été utilisé.",
    exhausted: "Ce lien de paiement a atteint son nombre maximal de paiements.",
    expired: "Ce lien de paiement a expiré.",
    invalid_amount: "Montant invalide.",
    amount_too_low: "Le montant saisi est inférieur au minimum autorisé.",
    amount_too_high: "Le montant saisi dépasse le maximum autorisé.",
    "user not found": "Ce lien de paiement n'est plus disponible.",
  };

  function showError(key) {
    loadingEl.classList.add("pf-hidden");
    formEl.classList.add("pf-hidden");
    errorEl.classList.remove("pf-hidden");
    errorEl.textContent = ERROR_MESSAGES[key] || "Ce lien de paiement n'est pas disponible.";
  }

  if (!token) {
    showError("invalid");
    return;
  }

  fetch(`${BASE_URL}/pay/${encodeURIComponent(token)}/info`)
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        showError(data.error);
        return;
      }
      loadingEl.classList.add("pf-hidden");
      formEl.classList.remove("pf-hidden");
      nameEl.textContent = data.name || "Paiement Xepay";
      currencyEl.textContent = data.currency;
      if (data.min_amount != null) amountInput.min = data.min_amount;
      if (data.max_amount != null) amountInput.max = data.max_amount;
      if (data.min_amount != null && data.max_amount != null) {
        hintEl.textContent = `Entre ${data.min_amount} et ${data.max_amount} ${data.currency}`;
      } else if (data.min_amount != null) {
        hintEl.textContent = `Minimum ${data.min_amount} ${data.currency}`;
      } else if (data.max_amount != null) {
        hintEl.textContent = `Maximum ${data.max_amount} ${data.currency}`;
      }
    })
    .catch(() => showError("invalid"));

  formEl.addEventListener("submit", (event) => {
    event.preventDefault();
    formErrorEl.classList.add("pf-hidden");
    const amount = parseFloat(amountInput.value);
    if (isNaN(amount) || amount <= 0) {
      formErrorEl.textContent = "Montant invalide.";
      formErrorEl.classList.remove("pf-hidden");
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "Redirection...";
    fetch(`${BASE_URL}/pay/${encodeURIComponent(token)}/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.error || !data.url) {
          formErrorEl.textContent = ERROR_MESSAGES[data.error] || "Impossible de créer le paiement.";
          formErrorEl.classList.remove("pf-hidden");
          submitBtn.disabled = false;
          submitBtn.textContent = "Payer →";
          return;
        }
        window.location.href = data.url;
      })
      .catch(() => {
        formErrorEl.textContent = "Erreur de connexion, réessayez.";
        formErrorEl.classList.remove("pf-hidden");
        submitBtn.disabled = false;
        submitBtn.textContent = "Payer →";
      });
  });
})();
