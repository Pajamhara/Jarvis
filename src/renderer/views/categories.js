// Gestion des catégories et des budgets mensuels
(function (A) {
  A.views.categories = {
    async render(root) {
      await A.loadCategories();
      const cats = A.state.categories;
      root.innerHTML = `
        <div class="page-head"><h1>Catégories & budgets</h1></div>
        <section class="card">
          <div class="card-head"><h2>Tes catégories</h2><span class="muted">Le budget est un plafond mensuel (facultatif)</span></div>
          <table>
            <thead><tr><th>Catégorie</th><th class="num" style="width:200px">Budget mensuel</th><th></th></tr></thead>
            <tbody>${cats.map((c) => `
              <tr data-id="${c.id}">
                <td>${A.catChip(c.name, c.emoji, c.color)}</td>
                <td class="num"><input type="number" min="0" step="1" value="${c.budget || ""}" placeholder="Aucun" data-budget style="width:140px;text-align:right" /></td>
                <td class="actions"><button class="icon-btn danger" data-del aria-label="Supprimer">🗑️</button></td>
              </tr>`).join("")}</tbody>
          </table>
        </section>
        <section class="card">
          <div class="card-head"><h2>Ajouter une catégorie</h2></div>
          <form id="cat-form" novalidate>
            <div class="row" style="align-items:end">
              <label class="field" style="max-width:90px"><span>Emoji</span><input type="text" name="emoji" maxlength="4" value="📦" /></label>
              <label class="field" style="flex:3"><span>Nom</span><input type="text" name="name" maxlength="40" placeholder="Ex. : Santé" /></label>
              <label class="field" style="flex:none"><span>Couleur</span><input type="color" name="color" value="#6fa8dc" /></label>
              <label class="field"><span>Budget mensuel</span><input type="number" name="budget" min="0" step="1" placeholder="Facultatif" /></label>
              <label class="field" style="flex:none"><span>&nbsp;</span><button class="btn primary">Ajouter</button></label>
            </div>
            <div class="form-error" id="cat-error"></div>
          </form>
        </section>`;

      root.querySelectorAll("tbody tr").forEach((tr) => {
        const id = Number(tr.dataset.id);
        const c = cats.find((x) => x.id === id);
        A.$("[data-budget]", tr).onchange = async (e) => {
          const v = parseFloat(String(e.target.value).replace(",", "."));
          await A.api("setBudget", id, v > 0 ? v : 0);
          A.toast("Budget enregistré");
          await A.loadCategories();
        };
        A.$("[data-del]", tr).onclick = async () => {
          if (await A.confirm(`Supprimer « ${c.name} » ? Ses transactions passeront en « Sans catégorie ».`)) {
            await A.api("deleteCategory", id);
            A.refresh();
          }
        };
      });

      A.$("#cat-form", root).onsubmit = async (e) => {
        e.preventDefault();
        const f = e.target;
        try {
          await A.api("addCategory", { name: f.name.value, emoji: f.emoji.value, color: f.color.value, budget: parseFloat(f.budget.value) || 0 });
          A.toast("Catégorie ajoutée");
          A.refresh();
        } catch (err) {
          A.$("#cat-error", root).textContent = /UNIQUE/.test(String(err.message)) ? "Une catégorie porte déjà ce nom." : A.errMsg(err);
        }
      };
    },
  };
})(window.Astra);
