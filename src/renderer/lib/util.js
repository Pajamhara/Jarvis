// Utilitaires partagés (espace de noms global : window.Astra)
window.Astra = {
  state: { config: { theme: "dark", currency: "EUR" }, categories: [], month: null, view: "dashboard", statsTab: "monthly" },
  views: {},
  charts: {},
};

(function (A) {
  const $ = (sel, root = document) => root.querySelector(sel);
  A.$ = $;

  A.api = (name, ...args) => window.astra.call(name, ...args);

  A.esc = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ----- Formats ----- */
  A.money = (n, { compact = false } = {}) =>
    new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: A.state.config.currency || "EUR",
      maximumFractionDigits: compact ? 0 : 2,
    }).format(n || 0);

  A.pct = (n) => `${(n || 0).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;

  A.fmtDate = (iso) =>
    new Date(iso + "T00:00:00").toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });

  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  A.monthLabel = (ym) => {
    const [y, m] = ym.split("-").map(Number);
    return cap(new Date(y, m - 1, 1).toLocaleDateString("fr-FR", { month: "long", year: "numeric" }));
  };
  A.monthShort = (ym) => {
    const [y, m] = ym.split("-").map(Number);
    return new Date(y, m - 1, 1).toLocaleDateString("fr-FR", { month: "short" }).replace(".", "");
  };

  const pad = (n) => String(n).padStart(2, "0");
  A.today = () => {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  };
  A.currentMonth = () => A.today().slice(0, 7);
  A.shiftMonth = (ym, delta) => {
    const [y, m] = ym.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}`;
  };
  A.monthRange = (from, to) => {
    const out = [];
    for (let m = from; m <= to; m = A.shiftMonth(m, 1)) out.push(m);
    return out;
  };
  A.lastDayOf = (ym) => {
    const [y, m] = ym.split("-").map(Number);
    return `${ym}-${pad(new Date(y, m, 0).getDate())}`;
  };

  A.cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* ----- Sélecteur de mois ----- */
  A.monthNavHtml = (month) => `
    <div class="month-nav" data-month-nav>
      <button data-shift="-1" aria-label="Mois précédent">‹</button>
      <span class="label">${A.esc(A.monthLabel(month))}</span>
      <button data-shift="1" aria-label="Mois suivant">›</button>
    </div>`;
  A.bindMonthNav = (root) => {
    const nav = $("[data-month-nav]", root);
    if (!nav) return;
    nav.addEventListener("click", (e) => {
      const b = e.target.closest("[data-shift]");
      if (!b) return;
      A.state.month = A.shiftMonth(A.state.month, Number(b.dataset.shift));
      A.refresh();
    });
  };

  /* ----- Infobulle ----- */
  const tip = () => $("#tooltip");
  A.tooltip = {
    show(html, evt) {
      const t = tip();
      t.innerHTML = html;
      t.classList.add("on");
      A.tooltip.move(evt);
    },
    move(evt) {
      const t = tip();
      const pad = 14;
      const w = t.offsetWidth, h = t.offsetHeight;
      let x = evt.clientX + pad, y = evt.clientY + pad;
      if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
      if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
      t.style.left = `${Math.max(8, x)}px`;
      t.style.top = `${Math.max(8, y)}px`;
    },
    hide() {
      tip().classList.remove("on");
    },
  };
  A.ttLine = (label, value, cls = "") =>
    `<div class="tt-line ${cls}"><span>${A.esc(label)}</span><span>${value}</span></div>`;

  /* ----- Toast ----- */
  let toastTimer;
  A.toast = (msg) => {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove("on"), 2400);
  };

  /* ----- Fenêtres modales ----- */
  A.openModal = ({ title, html, onMount }) => {
    const root = $("#modal-root");
    root.innerHTML = `
      <div class="overlay">
        <div class="modal card" role="dialog" aria-modal="true" aria-label="${A.esc(title)}">
          <div class="modal-head"><h2>${A.esc(title)}</h2>
            <button class="icon-btn" data-close aria-label="Fermer">✕</button></div>
          ${html}
        </div>
      </div>`;
    const overlay = $(".overlay", root);
    const close = () => {
      root.innerHTML = "";
      document.removeEventListener("keydown", onKey);
    };
    const onKey = (e) => e.key === "Escape" && close();
    document.addEventListener("keydown", onKey);
    overlay.addEventListener("mousedown", (e) => e.target === overlay && close());
    $("[data-close]", root).addEventListener("click", close);
    const first = root.querySelector("input, select");
    if (first) first.focus();
    if (onMount) onMount($(".modal", root), close);
    return close;
  };

  A.confirm = (message, okLabel = "Supprimer") =>
    new Promise((resolve) => {
      A.openModal({
        title: "Confirmation",
        html: `<p>${A.esc(message)}</p>
          <div class="modal-foot">
            <button class="btn" data-no>Annuler</button>
            <button class="btn primary" data-yes>${A.esc(okLabel)}</button>
          </div>`,
        onMount(m, close) {
          $("[data-no]", m).onclick = () => { close(); resolve(false); };
          $("[data-yes]", m).onclick = () => { close(); resolve(true); };
        },
      });
    });

  A.catChip = (name, emoji, color) =>
    `<span class="chip"><i style="background:${A.esc(color || "#8895a5")}"></i>${A.esc(emoji || "")} ${A.esc(name || "Sans catégorie")}</span>`;

  A.emptyState = (text, btnLabel, btnId) =>
    `<div class="empty"><div>${A.esc(text)}</div>${btnLabel ? `<button class="btn primary" id="${btnId}">${A.esc(btnLabel)}</button>` : ""}</div>`;
})(window.Astra);

// Message d'erreur lisible (retire le préfixe ajouté par Electron IPC)
window.Astra.errMsg = (err) =>
  String((err && err.message) || err || "Une erreur est survenue.").replace(/^Error invoking remote method 'api': (Error: )?/, "");
