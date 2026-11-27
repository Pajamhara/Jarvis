# ✦ Astra

Tracker de finances personnelles : saisis tes revenus et tes dépenses, Astra génère un **diagramme de Sankey** de ton mois (`Salaire Net` → catégories de dépenses → `Épargne`). Tout reste **en local** sur ton PC.

Même identité visuelle que Constellation (bleu nuit, bleu clair unique).

## Fonctionnalités

- **Tableau de bord** : Sankey du mois avec infobulles (total, part du revenu, nombre de transactions, top 3 des dépenses, budget dépassé).
- **Transactions** : date, montant, catégorie, description — ajout, modification, suppression.
- **Catégories & budgets** : 🏠 Logement, 🚗 Transport, 🎮 Loisirs, 🍔 Restaurants, 🛒 Courses, 💻 Informatique, plus les tiennes. Plafond mensuel facultatif par catégorie.
- **Statistiques** : dépenses par mois, par année, catégories les plus coûteuses, évolution du patrimoine, revenus.
- **Objectifs d'épargne** : suivi des achats à financer, estimation de la date d'atteinte selon ton rythme d'épargne.
- **Recherche** d'une opération (description, catégorie, date, montant).
- **Sauvegarder / Restaurer** la base en un clic.
- **Mises à jour automatiques** via GitHub Releases.

## Installation (développement)

Prérequis : [Node.js 20+](https://nodejs.org).

```bash
git clone https://github.com/TON_PSEUDO/astra.git
cd astra
npm install
npm start
```

## Données

Stockées dans `%APPDATA%/Astra/` :

| Fichier | Contenu |
|---|---|
| `astra.db` (SQLite) | transactions, catégories, budgets, objectifs |
| `config.json` | `theme`, `currency`, `windowWidth`, `windowHeight`, `initialBalance` |

Exemple de `config.json` :

```json
{ "theme": "dark", "currency": "EUR", "windowWidth": 1280, "windowHeight": 800, "initialBalance": 0 }
```

## Construire l'installeur `.exe`

```bash
npm run dist     # génère dist/Astra Setup x.y.z.exe
```

## Publier une version (et activer les mises à jour)

1. Remplace `TON_PSEUDO` dans `package.json` (`author` et `build.publish.owner`) et dans `LICENSE`.
2. Change la `version` dans `package.json` (c'est la source de vérité, affichée en bas de la barre latérale).
3. Commit, puis pousse un tag identique :

   ```bash
   git tag v1.0.1
   git push origin main --tags
   ```

4. Le workflow `.github/workflows/release.yml` construit l'installeur et publie la Release (avec `latest.yml`, indispensable aux mises à jour).

Au démarrage, Astra interroge GitHub et compare sa version à la dernière publiée. Si une version plus récente existe, elle propose de la télécharger (barre de progression), puis de redémarrer pour l'installer. Hors ligne, l'échec est silencieux. Un clic sur la version en bas à gauche lance une vérification manuelle.

> La recherche de mise à jour n'est active que dans l'application installée, pas avec `npm start`.
> L'exécutable n'est pas signé : Windows SmartScreen peut afficher un avertissement à la première installation.
> Le dépôt doit être **public** pour que les mises à jour fonctionnent sans jeton.

## Personnaliser les couleurs

Toute la palette est dans `src/renderer/styles/theme.css` (variables CSS, thèmes sombre et clair). Les couleurs des catégories par défaut sont dans `src/main/db.js`.

## Structure

```
src/
├── main/
│   ├── main.js        # fenêtre, API IPC, sauvegarde/restauration
│   ├── db.js          # SQLite + migrations + requêtes
│   ├── config.js      # config.json
│   ├── updater.js     # mises à jour GitHub
│   └── preload.js     # pont sécurisé vers le renderer
└── renderer/
    ├── index.html, app.js
    ├── styles/        # theme.css (palette), app.css
    ├── lib/           # util.js, charts.js, transactionForm.js
    └── views/         # sankey, transactions, monthly, yearly, topCategories,
                       # netWorth, income, stats, goals, search, categories
```

## Licence

MIT
