// Liste des transactions du mois
(function (A) {
  A.views.transactions = {
    async render(root) {
      const month = A.state.month;
      const rows = await A.api("listTransactions", { month });
      const inc = rows.filter((r) => r.type === "income").reduce((s, r) => s + r.amount, 0);
      const exp = rows.filter((r) => r.type === "expense").reduce((s, r) => s + r.amount, 0);

      root.innerHTML = `
        <div class="page-head">
          <h1>Transactions</h1>
          <div class="head-actions">${A.monthNavHtml(month)}<button class="btn primary" id="add-tx">＋ Transaction</button></div>
        </div>
        <section class="card">
          <div class="card-head"><h2>${rows.length} opération(s)</h2>
            <span class="muted">Revenus <b class="pos">${A.money(inc)}</b> · Dépenses <b>${A.money(exp)}</b></span></div>
          ${rows.length ? A.txTable(rows) : A.emptyState("Aucune opération ce mois-ci.", "＋ Ajouter une transaction", "empty-add")}
        </section>`;

      A.bindMonthNav(root);
      A.$("#add-tx", root).onclick = () => A.openTransactionForm();
      const empty = A.$("#empty-add", root);
      if (empty) empty.onclick = () => A.openTransactionForm();
      A.bindTxTable(root, rows);
    },
  };

  // Tableau partagé avec la recherche
  A.txTable = (rows) => `
    <table>
      <thead><tr><th>Date</th><th>Description</th><th>Catégorie</th><th class="num">Montant</th><th></th></tr></thead>
      <tbody>
        ${rows.map((r) => `
          <tr data-id="${r.id}">
            <td class="muted">${A.esc(A.fmtDate(r.date))}</td>
            <td>${A.esc(r.description || "—")}</td>
            <td>${r.type === "income" ? A.catChip("Revenu", "💼", A.cssVar("--accent")) : A.catChip(r.category_name, r.category_emoji, r.category_color)}</td>
            <td class="num ${r.type === "income" ? "pos" : "neg"}">${r.type === "income" ? "+" : "−"} ${A.money(r.amount)}</td>
            <td class="actions">
              <button class="icon-btn" data-edit aria-label="Modifier">✏️</button>
              <button class="icon-btn danger" data-del aria-label="Supprimer">🗑️</button>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  A.bindTxTable = (root, rows) => {
    root.querySelectorAll("tbody tr").forEach((tr) => {
      const tx = rows.find((r) => r.id === Number(tr.dataset.id));
      A.$("[data-edit]", tr).onclick = () => A.openTransactionForm(tx);
      A.$("[data-del]", tr).onclick = async () => {
        if (await A.confirm(`Supprimer « ${tx.description || "cette opération"} » (${A.money(tx.amount)}) ?`)) {
          await A.api("deleteTransaction", tx.id);
          A.toast("Transaction supprimée");
          A.refresh();
        }
      };
    });
  };
})(window.Astra);
