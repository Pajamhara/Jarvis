// Dépenses par mois (empilées par catégorie) pour une année donnée
(function (A) {
  A.views.monthly = {
    async render(el) {
      const series = await A.api("monthlySeries");
      const years = [...new Set(series.map((s) => s.month.slice(0, 4)).concat(A.currentMonth().slice(0, 4)))].sort().reverse();
      const year = A.state.statsYear && years.includes(A.state.statsYear) ? A.state.statsYear : years[0];
      A.state.statsYear = year;

      const rows = await A.api("monthlyByCategory", year);
      const months = Array.from({ length: 12 }, (_, i) => `${year}-${String(i + 1).padStart(2, "0")}`);
      const cats = [...new Map(rows.map((r) => [r.name, r])).values()];
      const data = cats.map((c) => ({
        name: `${c.emoji} ${c.name}`, color: c.color,
        values: months.map((m) => rows.find((r) => r.month === m && r.name === c.name)?.total || 0),
      }));
      const totals = months.map((_, i) => d3.sum(data, (s) => s.values[i]));
      const total = d3.sum(totals);
      const active = totals.filter((t) => t > 0).length;

      el.innerHTML = `
        <div class="card-head"><h2>Dépenses par mois</h2>
          <select id="year-select" style="width:auto">${years.map((y) => `<option ${y === year ? "selected" : ""}>${y}</option>`).join("")}</select></div>
        <div class="muted" style="margin-bottom:8px">Total ${A.money(total)} · moyenne ${A.money(active ? total / active : 0)} / mois</div>
        ${total ? `<div class="chart" id="chart"></div>${A.charts.legend(data)}` : A.emptyState(`Aucune dépense en ${year}.`)}`;
      A.$("#year-select", el).onchange = (e) => { A.state.statsYear = e.target.value; A.refresh(); };
      if (!total) return;

      A.charts.bars(A.$("#chart", el), {
        labels: months.map(A.monthShort), series: data, stacked: true,
        tooltip: (i) => {
          let h = `<div class="tt-title">${A.esc(A.monthLabel(months[i]))}</div>`;
          h += data.filter((s) => s.values[i] > 0).sort((a, b) => b.values[i] - a.values[i]).map((s) => A.ttLine(s.name, A.money(s.values[i]))).join("");
          return h + `<div class="tt-sep"></div>` + A.ttLine("Total", `<b>${A.money(totals[i])}</b>`);
        },
      });
    },
  };
})(window.Astra);
