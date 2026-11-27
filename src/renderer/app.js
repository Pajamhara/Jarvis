// Point d'entrée du renderer : navigation, thème, version, mises à jour
(function (A) {
  const NAV = [
    ["dashboard", "🏠", "Tableau de bord"],
    ["transactions", "🧾", "Transactions"],
    ["stats", "📊", "Statistiques"],
    ["goals", "🎯", "Objectifs"],
    ["search", "🔍", "Recherche"],
    ["categories", "🏷️", "Catégories"],
  ];

  A.loadCategories = async () => { A.state.categories = await A.api("listCategories"); };

  A.refresh = async () => {
    const root = A.$("#view");
    A.tooltip.hide();
    try {
      await A.loadCategories();
      await A.views[A.state.view].render(root);
    } catch (err) {
      console.error(err);
      root.innerHTML = `<div class="card"><div class="empty">Impossible d'afficher cette page : ${A.esc(A.errMsg(err))}</div></div>`;
    }
    document.querySelectorAll("#nav .side-link").forEach((b) => b.classList.toggle("active", b.dataset.view === A.state.view));
  };

  A.go = (view) => { A.state.view = view; A.refresh(); };

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    A.$("#btn-theme").textContent = theme === "dark" ? "🌞 Mode clair" : "🌙 Mode sombre";
  }

  async function init() {
    A.state.config = await A.api("getConfig");
    A.state.month = A.currentMonth();
    applyTheme(A.state.config.theme);

    const version = await A.api("version");
    const vBtn = A.$("#version");
    vBtn.textContent = `Astra v${version}`;
    vBtn.onclick = () => A.api("checkUpdates");

    const nav = A.$("#nav");
    nav.innerHTML = NAV.map(([id, icon, label]) => `<button class="side-link" data-view="${id}">${icon} ${label}</button>`).join("");
    nav.addEventListener("click", (e) => {
      const b = e.target.closest("[data-view]");
      if (b) A.go(b.dataset.view);
    });

    A.$("#btn-theme").onclick = async () => {
      const next = A.state.config.theme === "dark" ? "light" : "dark";
      A.state.config = await A.api("setConfig", { theme: next });
      applyTheme(next);
      A.refresh(); // redessine les graphiques avec les nouvelles couleurs
    };
    A.$("#btn-backup").onclick = async () => { if (await A.api("backup")) A.toast("Sauvegarde enregistrée"); };
    A.$("#btn-restore").onclick = () => A.api("restore");

    // Progression du téléchargement d'une mise à jour
    const banner = A.$("#update-banner");
    window.astra.onUpdateStatus((s) => {
      if (s.state === "downloading") {
        banner.hidden = false;
        banner.innerHTML = `<span>Téléchargement de la mise à jour… ${s.percent} %</span><span class="bar"><i style="width:${s.percent}%"></i></span>`;
      } else banner.hidden = true;
    });

    let t;
    window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(A.refresh, 200); });

    A.refresh();
  }

  document.addEventListener("DOMContentLoaded", init);
})(window.Astra);
