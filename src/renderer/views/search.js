// Recherche d'une opération (description, catégorie, date, montant)
(function (A) {
  A.views.search = {
    async render(root) {
      const q = A.state.searchQuery || "";
      const type = A.state.searchType || "";
      root.innerHTML = `
        <div class="page-head"><h1>Recherche</h1></div>
        <section class="card">
          <div class="row" style="margin-bottom:14px">
            <input type="search" id="q" placeholder="Description, catégorie, date (2026-11) ou montant…" value="${A.esc(q)}" style="flex:3" />
            <select id="type" style="flex:1">
              <option value="">Tout</option>
              <option value="expense" ${type === "expense" ? "selected" : ""}>Dépenses</option>
              <option value="income" ${type === "income" ? "selected" : ""}>Revenus</option>
            </select>
          </div>
          <div id="results"></div>
        </section>`;
      const input = A.$("#q", root), sel = A.$("#type", root), out = A.$("#results", root);
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);

      let timer, seq = 0;
      const run = async () => {
        const mine = ++seq;
        A.state.searchQuery = input.value;
        A.state.searchType = sel.value;
        if (!input.value.trim()) { out.innerHTML = `<div class="empty">Tape quelques lettres ou un montant pour retrouver une opération.</div>`; return; }
        const rows = await A.api("searchTransactions", { q: input.value, type: sel.value });
        if (mine !== seq) return;
        if (!rows.length) { out.innerHTML = `<div class="empty">Aucune opération ne correspond à « ${A.esc(input.value)} ».</div>`; return; }
        const total = rows.reduce((s, r) => s + (r.type === "income" ? r.amount : -r.amount), 0);
        out.innerHTML = `<div class="muted" style="margin-bottom:8px">${rows.length}${rows.length === 200 ? "+" : ""} résultat(s) · solde ${A.money(total)}</div>` + A.txTable(rows);
        A.bindTxTable(out, rows);
      };
      input.oninput = () => { clearTimeout(timer); timer = setTimeout(run, 180); };
      sel.onchange = run;
      run();
    },
  };
})(window.Astra);
