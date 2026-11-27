// Page Statistiques : onglets vers les différentes vues
(function (A) {
  const TABS = [
    ["monthly", "Dépenses / mois"],
    ["yearly", "Dépenses / année"],
    ["topCategories", "Catégories"],
    ["netWorth", "Patrimoine"],
    ["income", "Revenus"],
  ];

  A.views.stats = {
    async render(root) {
      const tab = A.state.statsTab;
      root.innerHTML = `
        <div class="page-head"><h1>Statistiques</h1></div>
        <div class="tabs" role="tablist">${TABS.map(([k, l]) => `<button role="tab" data-tab="${k}" class="${k === tab ? "on" : ""}">${l}</button>`).join("")}</div>
        <section class="card" id="stats-body"></section>`;
      root.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { A.state.statsTab = b.dataset.tab; A.refresh(); }));
      await A.views[tab].render(A.$("#stats-body", root));
    },
  };
})(window.Astra);
