// Graphiques D3 réutilisables : barres (groupées/empilées), courbe, barres horizontales
(function (A) {
  const M = { t: 14, r: 14, b: 32, l: 62 };

  function frame(el, height) {
    el.innerHTML = "";
    const w = Math.max(320, el.clientWidth || 800);
    const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${w} ${height}`).attr("height", height);
    return { svg, w };
  }

  function drawAxes(svg, { x, y, w, height, labels, xTickEvery = 1 }) {
    const grid = svg.append("g");
    y.ticks(5).forEach((t) => {
      grid.append("line").attr("x1", M.l).attr("x2", w - M.r).attr("y1", y(t)).attr("y2", y(t)).attr("stroke", A.cssVar("--grid"));
      grid.append("text").attr("x", M.l - 8).attr("y", y(t)).attr("dy", "0.32em").attr("text-anchor", "end").text(A.money(t, { compact: true }));
    });
    const xs = svg.append("g");
    labels.forEach((l, i) => {
      if (i % xTickEvery) return;
      xs.append("text").attr("x", x(l) + (x.bandwidth ? x.bandwidth() / 2 : 0)).attr("y", height - 10).attr("text-anchor", "middle").text(l);
    });
  }

  /* Barres verticales. series: [{name,color,values[]}] */
  A.charts.bars = (el, { labels, series, stacked = false, height = 320, tooltip }) => {
    const { svg, w } = frame(el, height);
    const x = d3.scaleBand().domain(labels).range([M.l, w - M.r]).padding(0.28);
    const maxY = stacked
      ? d3.max(labels, (_, i) => d3.sum(series, (s) => s.values[i]))
      : d3.max(series, (s) => d3.max(s.values));
    const y = d3.scaleLinear().domain([0, (maxY || 1) * 1.08]).nice().range([height - M.b, M.t]);
    drawAxes(svg, { x, y, w, height, labels, xTickEvery: Math.ceil(labels.length / Math.max(1, Math.floor(w / 60))) });

    const g = svg.append("g");
    if (stacked) {
      labels.forEach((l, i) => {
        let acc = 0;
        series.forEach((s) => {
          const v = s.values[i];
          if (!v) return;
          g.append("rect").attr("x", x(l)).attr("width", x.bandwidth())
            .attr("y", y(acc + v)).attr("height", Math.max(0, y(acc) - y(acc + v) - 1)).attr("rx", 2).attr("fill", s.color);
          acc += v;
        });
      });
    } else {
      const x1 = d3.scaleBand().domain(series.map((s) => s.name)).range([0, x.bandwidth()]).padding(0.12);
      labels.forEach((l, i) => {
        series.forEach((s) => {
          const v = s.values[i];
          g.append("rect").attr("x", x(l) + x1(s.name)).attr("width", x1.bandwidth())
            .attr("y", y(v)).attr("height", Math.max(0, y(0) - y(v))).attr("rx", 3).attr("fill", s.color);
        });
      });
    }
    overlay(svg, { labels, x, w, height, tooltip, bandwidth: true });
  };

  /* Courbe (avec aire optionnelle). series: [{name,color,values[]}] */
  A.charts.line = (el, { labels, series, height = 320, area = true, tooltip }) => {
    const { svg, w } = frame(el, height);
    const x = d3.scalePoint().domain(labels).range([M.l + 12, w - M.r - 12]);
    const all = series.flatMap((s) => s.values);
    const lo = Math.min(0, d3.min(all) ?? 0), hi = Math.max(0, d3.max(all) ?? 1);
    const y = d3.scaleLinear().domain([lo, hi === lo ? lo + 1 : hi]).nice().range([height - M.b, M.t]);
    drawAxes(svg, { x, y, w, height, labels, xTickEvery: Math.ceil(labels.length / Math.max(1, Math.floor(w / 60))) });
    if (lo < 0) svg.append("line").attr("x1", M.l).attr("x2", w - M.r).attr("y1", y(0)).attr("y2", y(0)).attr("stroke", A.cssVar("--muted")).attr("stroke-opacity", 0.5);

    series.forEach((s, si) => {
      const pts = s.values.map((v, i) => [x(labels[i]), y(v)]);
      if (area && si === 0) {
        svg.append("path").attr("d", d3.area().x((d) => d[0]).y0(y(0)).y1((d) => d[1]).curve(d3.curveMonotoneX)(pts)).attr("fill", s.color).attr("fill-opacity", 0.14);
      }
      svg.append("path").attr("d", d3.line().curve(d3.curveMonotoneX)(pts)).attr("fill", "none").attr("stroke", s.color).attr("stroke-width", 2.4);
      if (labels.length <= 36) pts.forEach((p) => svg.append("circle").attr("cx", p[0]).attr("cy", p[1]).attr("r", 3).attr("fill", s.color));
    });
    overlay(svg, { labels, x, w, height, tooltip, bandwidth: false });
  };

  // Zones invisibles pour l'infobulle par colonne
  function overlay(svg, { labels, x, w, height, tooltip, bandwidth }) {
    if (!tooltip) return;
    const step = labels.length > 1 ? (w - M.l - M.r) / labels.length : w - M.l - M.r;
    const hl = svg.append("rect").attr("y", M.t).attr("height", height - M.t - M.b).attr("fill", A.cssVar("--accent")).attr("opacity", 0).attr("pointer-events", "none");
    labels.forEach((l, i) => {
      const cx = x(l) + (bandwidth ? x.bandwidth() / 2 : 0);
      svg.append("rect").attr("x", cx - step / 2).attr("width", step).attr("y", M.t).attr("height", height - M.t - M.b)
        .attr("fill", "transparent")
        .on("mouseenter", (e) => { hl.attr("x", cx - step / 2).attr("width", step).attr("opacity", 0.07); A.tooltip.show(tooltip(i), e); })
        .on("mousemove", (e) => A.tooltip.move(e))
        .on("mouseleave", () => { hl.attr("opacity", 0); A.tooltip.hide(); });
    });
  }

  /* Barres horizontales HTML. rows: [{label,color,value,tip,mark}] */
  A.charts.hbars = (el, rows) => {
    const max = d3.max(rows, (r) => Math.max(r.value, r.mark || 0)) || 1;
    el.innerHTML = rows
      .map(
        (r, i) => `
      <div class="hbar" data-i="${i}">
        <div>${A.esc(r.label)}</div>
        <div class="track"><div class="fill" style="width:${(r.value / max) * 100}%;background:${A.esc(r.color)}"></div>
          ${r.mark ? `<div class="mark" style="left:${(r.mark / max) * 100}%"></div>` : ""}</div>
        <div class="amount">${A.money(r.value)}</div>
      </div>`
      )
      .join("");
    el.querySelectorAll(".hbar").forEach((row) => {
      const r = rows[Number(row.dataset.i)];
      row.addEventListener("mouseenter", (e) => A.tooltip.show(r.tip, e));
      row.addEventListener("mousemove", (e) => A.tooltip.move(e));
      row.addEventListener("mouseleave", () => A.tooltip.hide());
    });
  };

  A.charts.legend = (items) =>
    `<div class="legend">${items.map((i) => `<span><i style="background:${A.esc(i.color)}"></i>${A.esc(i.name)}</span>`).join("")}</div>`;
})(window.Astra);
