// Dépenses par année
(function (A) {
  A.views.yearly = {
    async render(el) {
      const rows = await A.api("yearlySeries");
      if (!rows.length) { el.innerHTML = `<div class="card-head"><h2>Dépenses par année</h2></div>` + A.emptyState("Aucune donnée pour l'instant."); return; }
      const labels = rows.map((r) => r.year);
      const series = [
        { name: "Revenus", color: A.cssVar("--accent"), values: rows.map((r) => r.income) },
        { name: "Dépenses", color: A.cssVar("--danger"), values: rows.map((r) => r.expense) },
      ];
      el.innerHTML = `
        <div class="card-head"><h2>Dépenses par année</h2></div>
        <div class="chart" id="chart"></div>${A.charts.legend(series)}
        <table style="margin-top:14px">
          <thead><tr><th>Année</th><th class="num">Revenus</th><th class="num">Dépenses</th><th class="num">Épargne</th><th class="num">Taux</th></tr></thead>
          <tbody>${rows.slice().reverse().map((r) => {
            const s = r.income - r.expense;
            return `<tr><td>${r.year}</td><td class="num">${A.money(r.income)}</td><td class="num">${A.money(r.expense)}</td>
              <td class="num ${s >= 0 ? "pos" : ""}">${A.money(s)}</td><td class="num">${r.income > 0 ? A.pct((s / r.income) * 100) : "—"}</td></tr>`;
          }).join("")}</tbody>
        </table>`;
      A.charts.bars(A.$("#chart", el), {
        labels, series, height: 280,
        tooltip: (i) => `<div class="tt-title">${labels[i]}</div>` + A.ttLine("Revenus", A.money(rows[i].income)) +
          A.ttLine("Dépenses", A.money(rows[i].expense)) + A.ttLine("Épargne", A.money(rows[i].income - rows[i].expense)),
      });
    },
  };
})(window.Astra);
