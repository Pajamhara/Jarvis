// Tableau de bord : diagramme de Sankey Salaire Net → catégories / Épargne
(function (A) {
  A.views.dashboard = {
    async render(root) {
      const month = A.state.month;
      const d = await A.api("sankeyData", month);
      const rate = d.income > 0 ? (d.savings / d.income) * 100 : 0;

      root.innerHTML = `
        <div class="page-head">
          <h1>Tableau de bord</h1>
          <div class="head-actions">${A.monthNavHtml(month)}<button class="btn primary" id="add-tx">＋ Transaction</button></div>
        </div>
        <div class="kpis">
          <div class="kpi income"><div class="label">Salaire Net</div><div class="value">${A.money(d.income)}</div><div class="sub">${d.incomeCount} revenu(s)</div></div>
          <div class="kpi"><div class="label">Dépenses</div><div class="value">${A.money(d.expenses)}</div><div class="sub">${d.income > 0 ? A.pct((d.expenses / d.income) * 100) + " du revenu" : "&nbsp;"}</div></div>
          <div class="kpi savings"><div class="label">Épargne</div><div class="value">${A.money(d.savings)}</div><div class="sub">${d.income > 0 ? "Taux d'épargne : " + A.pct(rate) : "&nbsp;"}</div></div>
        </div>
        <section class="card">
          <div class="card-head"><h2>Flux du mois</h2><span class="muted">Survole un flux pour voir le détail</span></div>
          ${d.deficit > 0 ? `<div class="warn">⚠️ Tes dépenses dépassent tes revenus de ${A.money(d.deficit)} ce mois-ci : aucune épargne n'est affichée.</div>` : ""}
          <div id="sankey"></div>
        </section>`;

      A.bindMonthNav(root);
      A.$("#add-tx", root).onclick = () => A.openTransactionForm();
      draw(A.$("#sankey", root), d);
    },
  };

  function tipCategory(c, d) {
    const share = d.income > 0 ? (c.total / d.income) * 100 : null;
    let h = `<div class="tt-title">${A.esc(c.emoji)} ${A.esc(c.name)}</div>`;
    h += A.ttLine("Total", A.money(c.total));
    if (share !== null) h += A.ttLine("Part du revenu", A.pct(share));
    h += A.ttLine("Part des dépenses", A.pct((c.total / d.expenses) * 100));
    h += A.ttLine("Transactions", c.count);
    if (c.budget) {
      const over = c.total > c.budget;
      h += A.ttLine("Budget mensuel", `${A.money(c.budget)}${over ? " — dépassé de " + A.money(c.total - c.budget) : ""}`, over ? "tt-over" : "");
    }
    if (c.top.length) {
      h += `<div class="tt-sep"></div>`;
      h += c.top.map((t) => A.ttLine(`${A.fmtDate(t.date)} · ${t.description || "Sans description"}`, A.money(t.amount))).join("");
    }
    return h;
  }

  function draw(el, d) {
    el.innerHTML = "";
    if (!d.income && !d.categories.length) {
      el.innerHTML = A.emptyState("Aucune opération ce mois-ci. Ajoute ton salaire et tes dépenses pour générer le diagramme.", "＋ Ajouter une transaction", "empty-add");
      A.$("#empty-add", el).onclick = () => A.openTransactionForm();
      return;
    }

    const accent = A.cssVar("--accent"), success = A.cssVar("--success");
    const cats = d.categories;
    const nodes = [{ name: "Salaire Net", emoji: "💼", kind: "income", order: 0, color: accent }];
    cats.forEach((c, i) => nodes.push({ name: c.name, emoji: c.emoji, kind: "cat", order: i + 1, color: c.color, cat: c }));
    const hasSavings = d.savings > 0;
    if (hasSavings) nodes.push({ name: "Épargne", emoji: "💰", kind: "savings", order: cats.length + 1, color: success });

    const links = cats.map((c, i) => ({ source: 0, target: i + 1, value: c.total, cat: c }));
    if (hasSavings) links.push({ source: 0, target: nodes.length - 1, value: d.savings });
    if (!links.length) {
      el.innerHTML = A.emptyState("Aucune dépense ce mois-ci : tout ton revenu est disponible.");
      return;
    }

    const W = Math.max(520, el.clientWidth);
    const H = Math.max(380, nodes.length * 52);
    const m = { l: 150, r: Math.min(240, W * 0.3), t: 8, b: 8 };
    const graph = d3.sankey()
      .nodeWidth(16).nodePadding(18)
      .nodeSort((a, b) => a.order - b.order)
      .extent([[m.l, m.t], [W - m.r, H - m.b]])({ nodes: nodes.map((n) => ({ ...n })), links: links.map((l) => ({ ...l })) });

    const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("height", H);

    const link = svg.append("g").attr("fill", "none").selectAll("path").data(graph.links).join("path")
      .attr("d", d3.sankeyLinkHorizontal())
      .attr("stroke", (l) => l.target.color)
      .attr("stroke-opacity", 0.38)
      .attr("stroke-width", (l) => Math.max(1.5, l.width));

    const base = () => link.attr("stroke-opacity", 0.38);
    const focus = (fn) => link.attr("stroke-opacity", (l) => (fn(l) ? 0.7 : 0.1));

    link
      .on("mouseenter", (e, l) => {
        focus((x) => x === l);
        const share = d.income > 0 ? (l.value / d.income) * 100 : null;
        const isSav = l.target.kind === "savings";
        let h = `<div class="tt-title">${isSav ? "Épargne" : A.esc(l.target.emoji + " " + l.target.name)}</div>`;
        h += A.ttLine("Montant", A.money(l.value));
        if (share !== null) h += A.ttLine("Part du revenu", A.pct(share));
        A.tooltip.show(h, e);
      })
      .on("mousemove", (e) => A.tooltip.move(e))
      .on("mouseleave", () => { base(); A.tooltip.hide(); });

    const node = svg.append("g").selectAll("g").data(graph.nodes).join("g");
    node.append("rect")
      .attr("x", (n) => n.x0).attr("y", (n) => n.y0)
      .attr("width", (n) => n.x1 - n.x0).attr("height", (n) => Math.max(2, n.y1 - n.y0))
      .attr("rx", 3).attr("fill", (n) => n.color);

    const text = node.append("text")
      .attr("x", (n) => (n.kind === "income" ? n.x0 - 12 : n.x1 + 12))
      .attr("y", (n) => (n.y0 + n.y1) / 2)
      .attr("text-anchor", (n) => (n.kind === "income" ? "end" : "start"));
    text.append("tspan").attr("class", "n-name").attr("dy", "-0.15em").text((n) => `${n.emoji} ${n.name}`);
    text.append("tspan").attr("x", (n) => (n.kind === "income" ? n.x0 - 12 : n.x1 + 12)).attr("dy", "1.35em")
      .text((n) => {
        const v = n.kind === "income" ? d.income : n.value;
        const share = d.income > 0 && n.kind !== "income" ? ` · ${A.pct((n.value / d.income) * 100)}` : "";
        return `${A.money(v)}${share}`;
      });

    node
      .style("cursor", "default")
      .on("mouseenter", (e, n) => {
        focus((l) => l.source === n || l.target === n);
        let h;
        if (n.kind === "cat") h = tipCategory(n.cat, d);
        else if (n.kind === "income") {
          h = `<div class="tt-title">💼 Salaire Net</div>` + A.ttLine("Revenus du mois", A.money(d.income)) +
              A.ttLine("Dépensé", A.money(d.expenses)) + A.ttLine("Épargné", A.money(d.savings));
        } else {
          h = `<div class="tt-title">💰 Épargne</div>` + A.ttLine("Montant", A.money(d.savings)) +
              A.ttLine("Taux d'épargne", A.pct(d.income > 0 ? (d.savings / d.income) * 100 : 0));
        }
        A.tooltip.show(h, e);
      })
      .on("mousemove", (e) => A.tooltip.move(e))
      .on("mouseleave", () => { base(); A.tooltip.hide(); });
  }
})(window.Astra);
