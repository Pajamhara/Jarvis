// Base SQLite : transactions, catégories, budgets, objectifs
const Database = require("better-sqlite3");

let db = null;

const DEFAULT_CATEGORIES = [
  ["Logement", "🏠", "#6fa8dc"],
  ["Transport", "🚗", "#8b78d0"],
  ["Loisirs", "🎮", "#e0894f"],
  ["Restaurants", "🍔", "#e5736b"],
  ["Courses", "🛒", "#4fb3c9"],
  ["Informatique", "💻", "#c27bc4"],
];

function init(file) {
  db = new Database(file);
  db.pragma("foreign_keys = ON");
  migrate();
  return db;
}

function close() {
  if (db) db.close();
  db = null;
}

function migrate() {
  const version = db.pragma("user_version", { simple: true });
  if (version < 1) {
    db.exec(`
      CREATE TABLE categories (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT NOT NULL UNIQUE,
        emoji TEXT NOT NULL DEFAULT '📦',
        color TEXT NOT NULL DEFAULT '#6fa8dc'
      );
      CREATE TABLE transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT NOT NULL,                       -- YYYY-MM-DD
        amount      REAL NOT NULL CHECK (amount > 0),
        type        TEXT NOT NULL CHECK (type IN ('income','expense')),
        category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
        description TEXT NOT NULL DEFAULT ''
      );
      CREATE INDEX idx_tx_date ON transactions(date);
      CREATE TABLE budgets (
        category_id  INTEGER PRIMARY KEY REFERENCES categories(id) ON DELETE CASCADE,
        limit_amount REAL NOT NULL CHECK (limit_amount > 0)   -- plafond mensuel
      );
      CREATE TABLE goals (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        target_amount REAL NOT NULL CHECK (target_amount > 0),
        saved_amount  REAL NOT NULL DEFAULT 0,
        deadline      TEXT,                                    -- YYYY-MM-DD ou NULL
        created_at    TEXT NOT NULL DEFAULT (date('now'))
      );
    `);
    const ins = db.prepare("INSERT INTO categories (name, emoji, color) VALUES (?, ?, ?)");
    for (const c of DEFAULT_CATEGORIES) ins.run(...c);
    db.pragma("user_version = 1");
  }
  if (version < 2) {
    // Nouvelle palette Émeraude : met à jour les couleurs des catégories par défaut
    // (uniquement si l'utilisateur ne les a pas déjà personnalisées)
    const upd = db.prepare("UPDATE categories SET color = ? WHERE name = ? AND color = ?");
    const OLD = { Logement: "#7fb2e5", Loisirs: "#d9a441", Courses: "#4fb98a", Informatique: "#4f8fd6" };
    for (const [name, , color] of DEFAULT_CATEGORIES) if (OLD[name]) upd.run(color, name, OLD[name]);
    db.pragma("user_version = 2");
  }
}

/* ---------- Validation ---------- */

const isDate = (s) => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s);
const isMonth = (s) => typeof s === "string" && /^\d{4}-\d{2}$/.test(s);

function cleanTx(tx) {
  const amount = Math.round(Number(tx.amount) * 100) / 100;
  if (!isDate(tx.date)) throw new Error("Date invalide.");
  if (!(amount > 0)) throw new Error("Le montant doit être supérieur à 0.");
  const type = tx.type === "income" ? "income" : "expense";
  const category_id = type === "expense" && tx.category_id ? Number(tx.category_id) : null;
  return { date: tx.date, amount, type, category_id, description: String(tx.description || "").trim().slice(0, 200) };
}

/* ---------- API ---------- */

const TX_SELECT = `
  SELECT t.id, t.date, t.amount, t.type, t.category_id, t.description,
         c.name AS category_name, c.emoji AS category_emoji, c.color AS category_color
  FROM transactions t LEFT JOIN categories c ON c.id = t.category_id`;

const api = {
  /* Catégories */
  listCategories: () =>
    db
      .prepare(
        `SELECT c.*, b.limit_amount AS budget FROM categories c
         LEFT JOIN budgets b ON b.category_id = c.id ORDER BY c.id`
      )
      .all(),

  addCategory: ({ name, emoji, color, budget }) => {
    name = String(name || "").trim();
    if (!name) throw new Error("Le nom est obligatoire.");
    const r = db
      .prepare("INSERT INTO categories (name, emoji, color) VALUES (?, ?, ?)")
      .run(name.slice(0, 40), (emoji || "📦").slice(0, 8), /^#[0-9a-fA-F]{6}$/.test(color) ? color : "#6fa8dc");
    if (budget > 0) api.setBudget(r.lastInsertRowid, budget);
    return r.lastInsertRowid;
  },

  deleteCategory: (id) => db.prepare("DELETE FROM categories WHERE id = ?").run(id).changes,

  setBudget: (categoryId, limit) => {
    if (!(Number(limit) > 0)) return db.prepare("DELETE FROM budgets WHERE category_id = ?").run(categoryId).changes;
    return db
      .prepare(
        `INSERT INTO budgets (category_id, limit_amount) VALUES (?, ?)
         ON CONFLICT(category_id) DO UPDATE SET limit_amount = excluded.limit_amount`
      )
      .run(categoryId, Number(limit)).changes;
  },

  /* Transactions */
  addTransaction: (tx) => {
    const t = cleanTx(tx);
    return db
      .prepare(
        `INSERT INTO transactions (date, amount, type, category_id, description)
         VALUES (@date, @amount, @type, @category_id, @description)`
      )
      .run(t).lastInsertRowid;
  },

  updateTransaction: (id, tx) => {
    const t = cleanTx(tx);
    return db
      .prepare(
        `UPDATE transactions SET date=@date, amount=@amount, type=@type,
         category_id=@category_id, description=@description WHERE id=@id`
      )
      .run({ ...t, id }).changes;
  },

  deleteTransaction: (id) => db.prepare("DELETE FROM transactions WHERE id = ?").run(id).changes,

  listTransactions: ({ month } = {}) => {
    if (!isMonth(month)) throw new Error("Mois invalide.");
    return db
      .prepare(`${TX_SELECT} WHERE substr(t.date,1,7) = ? ORDER BY t.date DESC, t.id DESC`)
      .all(month);
  },

  searchTransactions: ({ q, type } = {}) => {
    const text = String(q || "").trim().replace(/,/g, ".");
    if (!text) return [];
    const like = `%${text.replace(/[%_]/g, "")}%`;
    const typeSql = type === "income" || type === "expense" ? "AND t.type = @type" : "";
    return db
      .prepare(
        `${TX_SELECT}
         WHERE (t.description LIKE @like OR c.name LIKE @like OR t.date LIKE @like
                OR CAST(t.amount AS TEXT) LIKE @like) ${typeSql}
         ORDER BY t.date DESC, t.id DESC LIMIT 200`
      )
      .all(type === "income" || type === "expense" ? { like, type } : { like });
  },

  /* Données du Sankey pour un mois */
  sankeyData: (month) => {
    if (!isMonth(month)) throw new Error("Mois invalide.");
    const inc = db
      .prepare(
        `SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS n
         FROM transactions WHERE type='income' AND substr(date,1,7)=?`
      )
      .get(month);
    const cats = db
      .prepare(
        `SELECT t.category_id AS id,
                COALESCE(c.name,'Sans catégorie') AS name,
                COALESCE(c.emoji,'📦') AS emoji,
                COALESCE(c.color,'#8895a5') AS color,
                SUM(t.amount) AS total, COUNT(*) AS count, b.limit_amount AS budget
         FROM transactions t
         LEFT JOIN categories c ON c.id = t.category_id
         LEFT JOIN budgets b ON b.category_id = t.category_id
         WHERE t.type='expense' AND substr(t.date,1,7)=?
         GROUP BY t.category_id ORDER BY total DESC`
      )
      .all(month);
    const topStmt = db.prepare(
      `SELECT date, description, amount FROM transactions
       WHERE type='expense' AND substr(date,1,7)=? AND category_id IS ?
       ORDER BY amount DESC LIMIT 3`
    );
    let expenses = 0;
    for (const c of cats) {
      c.top = topStmt.all(month, c.id);
      expenses += c.total;
    }
    return {
      month,
      income: inc.total,
      incomeCount: inc.n,
      expenses,
      savings: Math.max(0, inc.total - expenses),
      deficit: Math.max(0, expenses - inc.total),
      categories: cats,
    };
  },

  /* Séries pour les statistiques */
  monthlySeries: () =>
    db
      .prepare(
        `SELECT substr(date,1,7) AS month,
                SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS income,
                SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
         FROM transactions GROUP BY month ORDER BY month`
      )
      .all(),

  monthlyByCategory: (year) =>
    db
      .prepare(
        `SELECT substr(t.date,1,7) AS month, t.category_id AS id,
                COALESCE(c.name,'Sans catégorie') AS name,
                COALESCE(c.emoji,'📦') AS emoji,
                COALESCE(c.color,'#8895a5') AS color,
                SUM(t.amount) AS total
         FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
         WHERE t.type='expense' AND substr(t.date,1,4)=?
         GROUP BY month, t.category_id ORDER BY month`
      )
      .all(String(year)),

  yearlySeries: () =>
    db
      .prepare(
        `SELECT substr(date,1,4) AS year,
                SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS income,
                SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS expense
         FROM transactions GROUP BY year ORDER BY year`
      )
      .all(),

  topCategories: (from, to) => {
    if (!isDate(from) || !isDate(to)) throw new Error("Période invalide.");
    return db
      .prepare(
        `SELECT t.category_id AS id,
                COALESCE(c.name,'Sans catégorie') AS name,
                COALESCE(c.emoji,'📦') AS emoji,
                COALESCE(c.color,'#8895a5') AS color,
                SUM(t.amount) AS total, COUNT(*) AS count, MAX(t.amount) AS biggest
         FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
         WHERE t.type='expense' AND t.date BETWEEN ? AND ?
         GROUP BY t.category_id ORDER BY total DESC`
      )
      .all(from, to);
  },

  /* Objectifs */
  goalsOverview: () => {
    const goals = db.prepare("SELECT * FROM goals ORDER BY (saved_amount >= target_amount), COALESCE(deadline,'9999'), id").all();
    const net = db
      .prepare(
        `SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0) AS total
         FROM transactions`
      )
      .get().total;
    // Épargne mensuelle moyenne sur les 3 derniers mois contenant des opérations
    const recent = db
      .prepare(
        `SELECT substr(date,1,7) AS m,
                SUM(CASE WHEN type='income' THEN amount ELSE -amount END) AS net
         FROM transactions GROUP BY m ORDER BY m DESC LIMIT 3`
      )
      .all();
    const avg = recent.length ? recent.reduce((s, r) => s + r.net, 0) / recent.length : 0;
    return { goals, totalSavings: net, avgMonthlySavings: avg };
  },

  addGoal: ({ name, target_amount, saved_amount, deadline }) => {
    name = String(name || "").trim();
    if (!name) throw new Error("Le nom est obligatoire.");
    if (!(Number(target_amount) > 0)) throw new Error("Le montant cible doit être supérieur à 0.");
    return db
      .prepare("INSERT INTO goals (name, target_amount, saved_amount, deadline) VALUES (?, ?, ?, ?)")
      .run(name.slice(0, 80), Number(target_amount), Math.max(0, Number(saved_amount) || 0), isDate(deadline) ? deadline : null)
      .lastInsertRowid;
  },

  updateGoal: (id, { name, target_amount, deadline }) => {
    name = String(name || "").trim();
    if (!name) throw new Error("Le nom est obligatoire.");
    if (!(Number(target_amount) > 0)) throw new Error("Le montant cible doit être supérieur à 0.");
    return db
      .prepare("UPDATE goals SET name=?, target_amount=?, deadline=? WHERE id=?")
      .run(name.slice(0, 80), Number(target_amount), isDate(deadline) ? deadline : null, id).changes;
  },

  contributeToGoal: (id, delta) =>
    db
      .prepare("UPDATE goals SET saved_amount = MAX(0, saved_amount + ?) WHERE id = ?")
      .run(Number(delta) || 0, id).changes,

  deleteGoal: (id) => db.prepare("DELETE FROM goals WHERE id = ?").run(id).changes,
};

function backupTo(file) {
  return db.backup(file);
}

module.exports = { init, close, backupTo, api, DEFAULT_CATEGORIES };
