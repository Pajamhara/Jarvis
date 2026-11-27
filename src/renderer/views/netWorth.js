// Évolution du patrimoine = solde initial + cumul (revenus − dépenses)
(function (A) {
  A.views.netWorth = {
    async render(el) {
      const series = await A.api("monthlySeries");
      const initial = A.state.config.initialBalance || 0;

      el.innerHTML = `
        <div class="card-head"><h2>Évolution du patrimoine</h2>
          <label class="muted" style="display:flex;align-items:center;gap:8px">Solde de départ
            <input id="initial" type="number" step="0.01" value="${initial}" style="width:130px" /></label></div>
        <div id="body"></div>`;
      const body = A.$("#body", el);
      A.$("#initial", el).onchange = async (e) => {
        const v = parseFloat(String(e.target.value).replace(",", "."));
        A.state.config = await A.api("setConfig", { initialBalance: Number.isFinite(v) ? v : 0 });
        A.refresh();
      };

      if (!series.length) { body.innerHTML = A.emptyState("Ajoute des transactions pour suivre ton patrimoine."); return; }

      const months = A.monthRange(series[0].month, A.currentMonth() > series.at(-1).month ? A.currentMonth() : series.at(-1).month);
      let acc = initial;
      const values = months.map((m) => {
        const s = series.find((x) => x.month === m);
        acc += s ? s.income - s.expense : 0;
        return acc;
      });
      const delta = values.at(-1) - initial;

      body.innerHTML = `
        <div class="kpis" style="grid-template-columns:repeat(2,1fr)">
          <div class="kpi"><div class="label">Patrimoine actuel</div><div class="value">${A.money(values.at(-1))}</div></div>
          <div class="kpi savings"><div class="label">Variation depuis le début</div><div class="value">${delta >= 0 ? "+" : ""}${A.money(delta)}</div></div>
        </div>
        <div class="chart" id="chart"></div>`;
      A.charts.line(A.$("#chart", body), {
        labels: months.map((m) => `${A.monthShort(m)} ${m.slice(2, 4)}`),
        series: [{ name: "Patrimoine", color: A.cssVar("--accent"), values }],
        tooltip: (i) => {
          const s = series.find((x) => x.month === months[i]);
          return `<div class="tt-title">${A.esc(A.monthLabel(months[i]))}</div>` + A.ttLine("Patrimoine", A.money(values[i])) +
            (s ? A.ttLine("Variation du mois", A.money(s.income - s.expense)) : "");
        },
      });
    },
  };
})(window.Astra);
