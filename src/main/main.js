const { app, BrowserWindow, ipcMain, dialog, Menu, nativeTheme } = require("electron");
const path = require("path");
const fs = require("fs");

const config = require("./config");
const db = require("./db");
const updater = require("./updater");

let win = null;

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
}

/* ---------- API exposée au renderer ---------- */

const api = {
  ...db.api,

  version: () => app.getVersion(),
  getConfig: () => config.get(),
  setConfig: (patch) => {
    const c = config.save(patch || {});
    if (patch && patch.theme) nativeTheme.themeSource = c.theme;
    return c;
  },

  checkUpdates: () => updater.check({ isManual: true }),

  backup: async () => {
    const stamp = new Date().toISOString().slice(0, 10);
    const { canceled, filePath } = await dialog.showSaveDialog(win, {
      title: "Sauvegarder les données Astra",
      defaultPath: `astra-sauvegarde-${stamp}.db`,
      filters: [{ name: "Base Astra", extensions: ["db"] }],
    });
    if (canceled || !filePath) return false;
    await db.backupTo(filePath);
    return true;
  },

  restore: async () => {
    const { canceled, filePaths } = await dialog.showOpenDialog(win, {
      title: "Restaurer une sauvegarde Astra",
      filters: [{ name: "Base Astra", extensions: ["db"] }],
      properties: ["openFile"],
    });
    if (canceled || !filePaths[0]) return false;

    // Vérifie que le fichier ressemble bien à une base Astra
    const Database = require("better-sqlite3");
    try {
      const probe = new Database(filePaths[0], { readonly: true, fileMustExist: true });
      probe.prepare("SELECT 1 FROM transactions LIMIT 1").get();
      probe.prepare("SELECT 1 FROM categories LIMIT 1").get();
      probe.close();
    } catch {
      dialog.showErrorBox("Fichier invalide", "Ce fichier n'est pas une sauvegarde Astra valide.");
      return false;
    }

    const { response } = await dialog.showMessageBox(win, {
      type: "warning",
      title: "Restaurer la sauvegarde",
      message: "Les données actuelles seront remplacées.",
      detail: "Astra va redémarrer après la restauration.",
      buttons: ["Restaurer", "Annuler"],
      defaultId: 1,
      cancelId: 1,
    });
    if (response !== 0) return false;

    const target = dbFile();
    db.close();
    fs.copyFileSync(filePaths[0], target);
    app.relaunch();
    app.exit(0);
    return true;
  },
};

ipcMain.handle("api", (_event, name, ...args) => {
  if (!Object.prototype.hasOwnProperty.call(api, name)) throw new Error(`API inconnue : ${name}`);
  return api[name](...args);
});

const dbFile = () => path.join(app.getPath("userData"), "astra.db");

/* ---------- Fenêtre ---------- */

function createWindow() {
  const cfg = config.get();
  nativeTheme.themeSource = cfg.theme;

  const iconPath = path.join(__dirname, "../../build/icon.png");
  win = new BrowserWindow({
    width: cfg.windowWidth,
    height: cfg.windowHeight,
    minWidth: 980,
    minHeight: 640,
    backgroundColor: cfg.theme === "dark" ? "#0e1512" : "#f1f6f4",
    title: `Astra v${app.getVersion()}`,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.loadFile(path.join(__dirname, "../renderer/index.html"));
  win.once("ready-to-show", () => win.show());

  // Garde la version dans le titre de la fenêtre
  win.on("page-title-updated", (e) => e.preventDefault());

  // Mémorise la taille de la fenêtre
  let timer = null;
  win.on("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      if (!win || win.isDestroyed() || win.isMaximized() || win.isMinimized()) return;
      const [w, h] = win.getSize();
      config.save({ windowWidth: w, windowHeight: h });
    }, 400);
  });

  // Les liens externes s'ouvrent dans le navigateur
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https:\/\//.test(url)) require("electron").shell.openExternal(url);
    return { action: "deny" };
  });

  // Vérifie les mises à jour au démarrage
  updater.init(win);
  win.webContents.once("did-finish-load", () => setTimeout(() => updater.check(), 2500));
}

app.whenReady().then(() => {
  config.init(app.getPath("userData"));
  db.init(dbFile());
  Menu.setApplicationMenu(null);
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  db.close();
  if (process.platform !== "darwin") app.quit();
});
