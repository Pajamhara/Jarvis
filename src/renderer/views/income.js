// Graphique des revenus (12 derniers mois)
(function (A) {
  A.views.income = {
    async render(el) {
      const series = await A.api("monthlySeries");
      const cur = A.currentMonth();
      const months = A.monthRange(A.shiftMonth(cur, -11), cur);
      const values = months.map((m) => series.find((s) => s.month === m)?.income || 0);
      const total = d3.sum(values);
      const active = values.filter((v) => v > 0).length;

      el.innerHTML = `
        <div class="card-head"><h2>Revenus</h2><span class="muted">12 derniers mois</span></div>
        <div class="muted" style="margin-bottom:8px">Total ${A.money(total)} · moyenne ${A.money(active ? total / active : 0)} / mois</div>
        ${total ? `<div class="chart" id="chart"></div>` : A.emptyState("Aucun revenu enregistré sur les 12 derniers mois.")}`;
      if (!total) return;
      A.charts.bars(A.$("#chart", el), {
        labels: months.map((m) => `${A.monthShort(m)} ${m.slice(2, 4)}`),
        series: [{ name: "Revenus", color: A.cssVar("--accent"), values }],
        tooltip: (i) => `<div class="tt-title">${A.esc(A.monthLabel(months[i]))}</div>` + A.ttLine("Revenus", A.money(values[i])),
      });
    },
  };
})(window.Astra);
