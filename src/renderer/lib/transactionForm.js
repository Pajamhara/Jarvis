// Formulaire d'ajout / modification d'une transaction
(function (A) {
  A.openTransactionForm = (tx = null) => {
    const editing = !!tx;
    let type = tx ? tx.type : "expense";
    const month = A.state.month || A.currentMonth();
    const defaultDate = tx ? tx.date : month === A.currentMonth() ? A.today() : `${month}-01`;

    const catOptions = A.state.categories
      .map((c) => `<option value="${c.id}" ${tx && tx.category_id === c.id ? "selected" : ""}>${A.esc(c.emoji)} ${A.esc(c.name)}</option>`)
      .join("");

    A.openModal({
      title: editing ? "Modifier la transaction" : "Ajouter une transaction",
      html: `
        <form id="tx-form" novalidate>
          <div class="segmented" role="group" aria-label="Type">
            <button type="button" data-type="expense">Dépense</button>
            <button type="button" data-type="income">Revenu</button>
          </div>
          <div class="row">
            <label class="field"><span>Date</span><input type="date" name="date" value="${defaultDate}" required /></label>
            <label class="field"><span>Montant</span><input type="number" name="amount" min="0.01" step="0.01" inputmode="decimal" placeholder="0,00" value="${tx ? tx.amount : ""}" required /></label>
          </div>
          <label class="field" id="cat-field"><span>Catégorie</span>
            <select name="category_id"><option value="">Sans catégorie</option>${catOptions}</select></label>
          <label class="field"><span>Description</span>
            <input type="text" name="description" maxlength="200" placeholder="Ex. : Loyer, Salaire de novembre…" value="${A.esc(tx ? tx.description : "")}" /></label>
          <div class="form-error" id="tx-error"></div>
          <div class="modal-foot">
            <button type="button" class="btn" data-close2>Annuler</button>
            <button type="submit" class="btn primary">${editing ? "Enregistrer" : "Ajouter"}</button>
          </div>
        </form>`,
      onMount(modal, close) {
        const form = A.$("#tx-form", modal);
        const setType = (t) => {
          type = t;
          modal.querySelectorAll("[data-type]").forEach((b) => {
            b.classList.toggle("on", b.dataset.type === t);
            b.classList.toggle("exp", b.dataset.type === "expense");
          });
          A.$("#cat-field", modal).hidden = t === "income";
          if (t === "income" && !form.description.value) form.description.placeholder = "Salaire Net";
        };
        setType(type);
        modal.querySelectorAll("[data-type]").forEach((b) => (b.onclick = () => setType(b.dataset.type)));
        A.$("[data-close2]", modal).onclick = close;

        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const amount = parseFloat(String(form.amount.value).replace(",", "."));
          const payload = {
            date: form.date.value,
            amount,
            type,
            category_id: type === "expense" && form.category_id.value ? Number(form.category_id.value) : null,
            description: form.description.value || (type === "income" ? "Salaire Net" : ""),
          };
          if (!payload.date) return (A.$("#tx-error", modal).textContent = "Choisis une date.");
          if (!(amount > 0)) return (A.$("#tx-error", modal).textContent = "Saisis un montant supérieur à 0.");
          try {
            if (editing) await A.api("updateTransaction", tx.id, payload);
            else await A.api("addTransaction", payload);
            close();
            A.toast(editing ? "Transaction modifiée" : "Transaction ajoutée");
            // Se place sur le mois de la transaction pour qu'elle soit visible
            A.state.month = payload.date.slice(0, 7);
            A.refresh();
          } catch (err) {
            A.$("#tx-error", modal).textContent = A.errMsg(err);
          }
        });
      },
    });
  };
})(window.Astra);
