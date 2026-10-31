// Bloc "Consultez vos rapports financiers" : bascule entre les périodes
// (onglets) puis ouvre un aperçu du PDF dans un modal au clic — les
// données sont fictives, on ne propose donc pas un vrai téléchargement,
// juste une consultation en place (iframe pointant sur le vrai PDF
// généré par make_reports.py).

const REPORTS = {
  hebdo: {
    title: "Rapport hebdomadaire — 20 au 26 oct. 2026",
    fileName: "Rapport_hebdomadaire_Xepay_20-26oct2026.pdf",
    file: "/assets/rapport-hebdomadaire-xepay-20-26-octobre-2026.pdf",
    meta: "20–26 oct. 2026 · 7 Ko",
  },
  mensuel: {
    title: "Rapport mensuel — Octobre 2026",
    fileName: "Rapport_mensuel_Xepay_Octobre2026.pdf",
    file: "/assets/rapport-mensuel-xepay-octobre-2026.pdf",
    meta: "Octobre 2026 · 6 Ko",
  },
  trimestriel: {
    title: "Rapport trimestriel — T4 2026",
    fileName: "Rapport_trimestriel_Xepay_T4-2026.pdf",
    file: "/assets/rapport-trimestriel-xepay-t4-2026.pdf",
    meta: "Août – oct. 2026 · 6 Ko",
  },
  semestriel: {
    title: "Rapport semestriel — Mai à octobre 2026",
    fileName: "Rapport_semestriel_Xepay_S2-2026.pdf",
    file: "/assets/rapport-semestriel-xepay-s2-2026.pdf",
    meta: "Mai – oct. 2026 · 7 Ko",
  },
  annuel: {
    title: "Rapport annuel — Nov. 2025 à oct. 2026",
    fileName: "Rapport_annuel_Xepay_2026.pdf",
    file: "/assets/rapport-annuel-xepay-2026.pdf",
    meta: "Nov. 2025 – oct. 2026 · 6 Ko",
  },
};

export function mountReports(root) {
  const tabs = Array.from(root.querySelectorAll("[data-xp-report-tab]"));
  const fileButton = root.querySelector("[data-xp-report-file]");
  const nameEl = root.querySelector("[data-xp-report-name]");
  const metaEl = root.querySelector("[data-xp-report-meta]");
  const modal = root.querySelector("[data-xp-report-modal]");
  const modalTitle = root.querySelector("[data-xp-report-modal-title]");
  const modalFrame = root.querySelector("[data-xp-report-modal-frame]");
  const modalCloseEls = Array.from(root.querySelectorAll("[data-xp-report-modal-close]"));
  if (!tabs.length || !fileButton || !nameEl || !metaEl || !modal || !modalFrame) return () => {};

  let activePeriod = "mensuel";

  function select(period) {
    const report = REPORTS[period];
    if (!report) return;
    activePeriod = period;
    tabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.xpReportTab === period);
    });
    nameEl.textContent = report.fileName;
    metaEl.textContent = report.meta;
  }

  function openModal() {
    const report = REPORTS[activePeriod];
    if (!report) return;
    modalTitle.textContent = report.title;
    modalFrame.src = report.file;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    modal.hidden = true;
    modalFrame.src = "";
    document.body.style.overflow = "";
  }

  function onTabClick(e) {
    select(e.currentTarget.dataset.xpReportTab);
  }
  function onFileClick() {
    openModal();
  }
  function onKeydown(e) {
    if (e.key === "Escape" && !modal.hidden) closeModal();
  }

  tabs.forEach((tab) => tab.addEventListener("click", onTabClick));
  fileButton.addEventListener("click", onFileClick);
  modalCloseEls.forEach((el) => el.addEventListener("click", closeModal));
  document.addEventListener("keydown", onKeydown);

  select("mensuel");

  return function cleanup() {
    tabs.forEach((tab) => tab.removeEventListener("click", onTabClick));
    fileButton.removeEventListener("click", onFileClick);
    modalCloseEls.forEach((el) => el.removeEventListener("click", closeModal));
    document.removeEventListener("keydown", onKeydown);
    closeModal();
  };
}
