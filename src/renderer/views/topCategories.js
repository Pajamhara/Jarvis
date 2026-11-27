// Catégories les plus coûteuses sur une période
(function (A) {
  const PERIODS = {
    month: "Ce mois", m3: "3 derniers mois", m12: "12 derniers mois", year: "Cette année", all: "Tout",
  };

  function range(key) {
    const cur = A.currentMonth();
    const end = A.lastDayOf(cur);
    switch (key) {
      case "month": return [`${cur}-01`, end];
      case "m3": return [`${A.shiftMonth(cur, -2)}-01`, end];
      case "m12": return [`${A.shiftMonth(cur, -11)}-01`, end];
      case "year": return [`${cur.slice(0, 4)}-01-01`, `${cur.slice(0, 4)}-12-31`];
      default: return ["0000-01-01", "9999-12-31"];
    }
  }

  A.views.topCategories = {
    async render(el) {
      const key = A.state.topPeriod || "m12";
      const [from, to] = range(key);
      const rows = await A.api("topCategories", from, to);
      const total = d3.sum(rows, (r) => r.total);

      el.innerHTML = `
        <div class="card-head"><h2>Catégories les plus coûteuses</h2>
          <select id="period" style="width:auto">${Object.entries(PERIODS).map(([k, v]) => `<option value="${k}" ${k === key ? "selected" : ""}>${v}</option>`).join("")}</select></div>
        ${rows.length ? `<div class="muted" style="margin-bottom:8px">Total ${A.money(total)}</div><div id="bars"></div>` : A.emptyState("Aucune dépense sur cette période.")}`;
      A.$("#period", el).onchange = (e) => { A.state.topPeriod = e.target.value; A.refresh(); };
      if (!rows.length) return;

      A.charts.hbars(A.$("#bars", el), rows.map((r) => ({
        label: `${r.emoji} ${r.name}`, color: r.color, value: r.total,
        tip: `<div class="tt-title">${A.esc(r.emoji)} ${A.esc(r.name)}</div>` +
          A.ttLine("Total", A.money(r.total)) + A.ttLine("Part des dépenses", A.pct((r.total / total) * 100)) +
          A.ttLine("Transactions", r.count) + A.ttLine("Moyenne", A.money(r.total / r.count)) +
          A.ttLine("Plus grosse dépense", A.money(r.biggest)),
      })));
    },
  };
})(window.Astra);
