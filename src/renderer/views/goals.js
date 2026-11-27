// Objectifs d'achat financés par l'épargne
(function (A) {
  A.views.goals = {
    async render(root) {
      const o = await A.api("goalsOverview");
      const allocated = o.goals.reduce((s, g) => s + g.saved_amount, 0);
      const free = o.totalSavings - allocated;

      root.innerHTML = `
        <div class="page-head"><h1>Objectifs d'épargne</h1>
          <div class="head-actions"><button class="btn primary" id="add-goal">＋ Objectif</button></div></div>
        <div class="kpis">
          <div class="kpi savings"><div class="label">Épargne cumulée</div><div class="value">${A.money(o.totalSavings)}</div><div class="sub">Revenus − dépenses, depuis le début</div></div>
          <div class="kpi"><div class="label">Déjà affectée aux objectifs</div><div class="value">${A.money(allocated)}</div></div>
          <div class="kpi"><div class="label">Épargne mensuelle moyenne</div><div class="value">${A.money(o.avgMonthlySavings)}</div><div class="sub">Sur les 3 derniers mois</div></div>
        </div>
        ${free < 0 ? `<div class="warn">Tu as affecté ${A.money(-free)} de plus que ton épargne cumulée.</div>` : ""}
        <div id="goal-list">${o.goals.length ? "" : `<section class="card">${A.emptyState("Aucun objectif pour l'instant. Ajoute un achat à financer : un PC, un voyage, un permis…", "＋ Créer un objectif", "empty-add")}</section>`}</div>`;

      A.$("#add-goal", root).onclick = () => goalForm();
      const empty = A.$("#empty-add", root);
      if (empty) empty.onclick = () => goalForm();

      const list = A.$("#goal-list", root);
      o.goals.forEach((g) => {
        const pct = Math.min(100, (g.saved_amount / g.target_amount) * 100);
        const done = g.saved_amount >= g.target_amount;
        const remaining = Math.max(0, g.target_amount - g.saved_amount);
        const sec = document.createElement("section");
        sec.className = "card goal";
        sec.innerHTML = `
          <div class="goal-top"><h3>${done ? "✅" : "🎯"} ${A.esc(g.name)}</h3>
            <span><b>${A.money(g.saved_amount)}</b> <span class="muted">/ ${A.money(g.target_amount)}</span></span></div>
          <div class="progress ${done ? "done" : ""}"><i style="width:${pct}%"></i></div>
          <div class="goal-meta">${A.pct(pct)} · ${done ? "Objectif atteint" : "Reste " + A.money(remaining)}${g.deadline ? " · échéance " + A.fmtDate(g.deadline) : ""}</div>
          <div class="goal-meta">${done ? "" : estimate(g, remaining, o.avgMonthlySavings)}</div>
          <div class="goal-actions">
            <button class="btn small primary" data-add>＋ Verser</button>
            <button class="btn small" data-withdraw>− Retirer</button>
            <button class="btn small" data-edit>Modifier</button>
            <button class="btn small danger" data-del>Supprimer</button>
          </div>`;
        A.$("[data-add]", sec).onclick = () => amountForm(g, 1);
        A.$("[data-withdraw]", sec).onclick = () => amountForm(g, -1);
        A.$("[data-edit]", sec).onclick = () => goalForm(g);
        A.$("[data-del]", sec).onclick = async () => {
          if (await A.confirm(`Supprimer l'objectif « ${g.name} » ?`)) { await A.api("deleteGoal", g.id); A.refresh(); }
        };
        list.appendChild(sec);
      });
    },
  };

  function estimate(g, remaining, avg) {
    const parts = [];
    if (avg > 0) {
      const n = Math.ceil(remaining / avg);
      const d = new Date(); d.setMonth(d.getMonth() + n);
      parts.push(`À ton rythme d'épargne actuel : ${n} mois (${A.monthLabel(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`)})`);
    } else parts.push("Ton épargne mensuelle actuelle ne permet pas d'estimer une date");
    if (g.deadline) {
      const now = new Date(), end = new Date(g.deadline + "T00:00:00");
      const months = (end.getFullYear() - now.getFullYear()) * 12 + end.getMonth() - now.getMonth();
      if (months > 0) parts.push(`Pour tenir l'échéance : ${A.money(remaining / months)} / mois`);
      else parts.push("Échéance dépassée");
    }
    return parts.join(" · ");
  }

  function goalForm(g = null) {
    A.openModal({
      title: g ? "Modifier l'objectif" : "Nouvel objectif",
      html: `<form id="goal-form" novalidate>
        <label class="field"><span>Nom</span><input type="text" name="name" maxlength="80" placeholder="Ex. : Nouveau PC" value="${A.esc(g ? g.name : "")}" /></label>
        <div class="row">
          <label class="field"><span>Montant cible</span><input type="number" name="target" min="1" step="0.01" value="${g ? g.target_amount : ""}" /></label>
          ${g ? "" : `<label class="field"><span>Déjà épargné</span><input type="number" name="saved" min="0" step="0.01" value="0" /></label>`}
        </div>
        <label class="field"><span>Échéance (facultatif)</span><input type="date" name="deadline" value="${g && g.deadline ? g.deadline : ""}" /></label>
        <div class="form-error" id="goal-error"></div>
        <div class="modal-foot"><button type="button" class="btn" data-c>Annuler</button><button class="btn primary">${g ? "Enregistrer" : "Créer"}</button></div>
      </form>`,
      onMount(m, close) {
        A.$("[data-c]", m).onclick = close;
        A.$("#goal-form", m).onsubmit = async (e) => {
          e.preventDefault();
          const f = e.target;
          const num = (v) => parseFloat(String(v).replace(",", "."));
          try {
            if (g) await A.api("updateGoal", g.id, { name: f.name.value, target_amount: num(f.target.value), deadline: f.deadline.value || null });
            else await A.api("addGoal", { name: f.name.value, target_amount: num(f.target.value), saved_amount: num(f.saved.value) || 0, deadline: f.deadline.value || null });
            close(); A.toast(g ? "Objectif modifié" : "Objectif créé"); A.refresh();
          } catch (err) { A.$("#goal-error", m).textContent = A.errMsg(err); }
        };
      },
    });
  }

  function amountForm(g, sign) {
    A.openModal({
      title: `${sign > 0 ? "Verser vers" : "Retirer de"} « ${g.name} »`,
      html: `<form id="amt-form" novalidate>
        <label class="field"><span>Montant</span><input type="number" name="amount" min="0.01" step="0.01" placeholder="0,00" /></label>
        <div class="form-error" id="amt-error"></div>
        <div class="modal-foot"><button type="button" class="btn" data-c>Annuler</button><button class="btn primary">${sign > 0 ? "Verser" : "Retirer"}</button></div>
      </form>`,
      onMount(m, close) {
        A.$("[data-c]", m).onclick = close;
        A.$("#amt-form", m).onsubmit = async (e) => {
          e.preventDefault();
          const v = parseFloat(String(e.target.amount.value).replace(",", "."));
          if (!(v > 0)) return (A.$("#amt-error", m).textContent = "Saisis un montant supérieur à 0.");
          await A.api("contributeToGoal", g.id, sign * v);
          close(); A.toast(sign > 0 ? "Versement ajouté" : "Retrait effectué"); A.refresh();
        };
      },
    });
  }
})(window.Astra);
