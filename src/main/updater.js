// Mise à jour automatique via GitHub Releases (electron-updater)
const { app, dialog } = require("electron");
const { autoUpdater } = require("electron-updater");

let win = null;
let manual = false;

function send(state) {
  if (win && !win.isDestroyed()) win.webContents.send("updater:status", state);
}

function init(browserWindow) {
  win = browserWindow;
  autoUpdater.autoDownload = false; // on demande d'abord à l'utilisateur
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("update-available", async (info) => {
    manual = false;
    if (!win.isVisible()) win.show(); // l'appli peut tourner en arrière-plan
    const { response } = await dialog.showMessageBox(win, {
      type: "info",
      title: "Mise à jour disponible",
      message: `Astra ${info.version} est disponible`,
      detail: `Vous utilisez la version ${app.getVersion()}.\nVoulez-vous la télécharger maintenant ?`,
      buttons: ["Télécharger", "Plus tard"],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 0) {
      send({ state: "downloading", percent: 0 });
      autoUpdater.downloadUpdate().catch((e) => {
        send({ state: "idle" });
        dialog.showErrorBox("Téléchargement impossible", String(e.message || e));
      });
    }
  });

  autoUpdater.on("update-not-available", () => {
    if (manual) {
      dialog.showMessageBox(win, {
        type: "info",
        title: "Astra est à jour",
        message: `Vous utilisez la dernière version (${app.getVersion()}).`,
      });
    }
    manual = false;
  });

  autoUpdater.on("download-progress", (p) => {
    win.setProgressBar(p.percent / 100);
    send({ state: "downloading", percent: Math.round(p.percent) });
  });

  autoUpdater.on("update-downloaded", async (info) => {
    win.setProgressBar(-1);
    send({ state: "idle" });
    const { response } = await dialog.showMessageBox(win, {
      type: "info",
      title: "Mise à jour prête",
      message: `Astra ${info.version} est prête à être installée`,
      detail: "L'application va redémarrer pour terminer l'installation.",
      buttons: ["Redémarrer maintenant", "Plus tard"],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 0) autoUpdater.quitAndInstall();
  });

  autoUpdater.on("error", (err) => {
    // Hors ligne ou GitHub injoignable : silencieux au démarrage
    console.error("[updater]", err && err.message);
    win.setProgressBar(-1);
    send({ state: "idle" });
    if (manual) {
      dialog.showErrorBox("Recherche de mise à jour impossible", "Vérifiez votre connexion Internet puis réessayez.");
    }
    manual = false;
  });
}

function check({ isManual = false } = {}) {
  manual = isManual;
  if (!app.isPackaged) {
    if (isManual) {
      dialog.showMessageBox(win, {
        type: "info",
        title: "Mode développement",
        message: "La recherche de mise à jour n'est active que dans la version installée (.exe).",
      });
    }
    return;
  }
  autoUpdater.checkForUpdates().catch(() => {});
}

module.exports = { init, check };
