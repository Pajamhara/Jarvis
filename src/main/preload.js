const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("astra", {
  // Appelle une fonction de l'API déclarée dans main.js (liste blanche côté main)
  call: (name, ...args) => ipcRenderer.invoke("api", name, ...args),
  onUpdateStatus: (cb) => ipcRenderer.on("updater:status", (_e, s) => cb(s)),
});
