# 🎙️ Jarvis (version locale et gratuite)

Assistant vocal en français inspiré de J.A.R.V.I.S. (Iron Man). Dites **« Hey Jarvis »**, puis demandez :

- « Lance Spotify », « Ouvre YouTube », « Ouvre les paramètres Wi-Fi »
- « Quel temps fera-t-il demain à Paris ? »
- « Mets un minuteur de dix minutes », « Monte le son », « Chanson suivante »
- « Éteins l'ordinateur » *(confirmation vocale demandée)*
- « Prends en note que j'ai rendez-vous jeudi », « Lis mes notes », « Retiens que mon chat s'appelle Mochi »
- « Rappelle-moi à 18h30 d'appeler maman », « Rappelle-moi dans 20 minutes de sortir le gratin »
- « Qui a gagné le match hier ? » : le modèle cherche sur internet et résume
- Et n'importe quelle question : le modèle local répond à voix haute.

**Aucune clé API, aucun abonnement.** Le cerveau est un modèle qui tourne sur votre carte graphique via [Ollama](https://ollama.com).

## Comment ça marche

```
Micro → Mot d'activation (openWakeWord)
      → Enregistrement (détection de silence)
      → [Vérification de votre voix — optionnel]
      → Voix → texte (faster-whisper, GPU)
      → Chemin rapide par règles ──► actions (apps, web, météo, volume, minuteur…)
            │ (non reconnu)
            └► Modèle local Ollama + outils ──► actions
      → Texte → voix (Piper local, repli edge-tts puis pyttsx3), 1re phrase lue dès qu'elle est prête
```

Le **chemin rapide** traite instantanément (et sans erreur possible du modèle) les commandes courantes. Seul le reste passe par le modèle, plus lent et moins fiable qu'un grand modèle en ligne.

| Brique | Où ça tourne |
|---|---|
| Mot d'activation, reconnaissance vocale, modèle, empreinte vocale | **Votre PC** |
| Voix de Jarvis (`piper`) | **Votre PC** (la voix est téléchargée une fois dans `data/voices`). Repli automatique sur `edge` (en ligne) puis `pyttsx3` |
| Météo, recherche internet | API Open-Meteo ; DuckDuckGo (via `ddgs`) : seules les requêtes de recherche sortent du PC |

## Installation (Windows)

Prérequis : **Python 3.10 à 3.12**, un micro, une carte NVIDIA à jour (pilote récent).

**1. Ollama et le modèle**
```powershell
winget install Ollama.Ollama        # ou téléchargez-le sur https://ollama.com/download
ollama pull qwen3.5:9b              # ~6,6 Go
```
Ollama se lance en tâche de fond. Si `qwen3.5:9b` n'est pas reconnu par votre version, mettez Ollama à jour ou prenez `qwen3:8b` (changez `llm.model` dans `config.yaml`).

**2. Jarvis**
```powershell
git clone https://github.com/<votre-compte>/jarvis-local.git
cd jarvis-local
python -m venv .venv
.venv\Scripts\activate              # Git Bash : source .venv/Scripts/activate
pip install -r requirements.txt
pip install -r requirements-extra.txt   # voix locale Piper + recherche internet (optionnel)
```

**3. Lancer**
```powershell
python main.py --text           # test sans micro (cerveau + outils)
python main.py --text --speak   # avec la voix
python main.py                  # mode vocal : dites « Hey Jarvis »
```
Au premier lancement vocal, les modèles Whisper et openWakeWord se téléchargent. Dites « **au revoir Jarvis** » pour l'arrêter.

Autres options : `--list-devices` (choisir son micro), `-v` (logs détaillés), `--enroll` (empreinte vocale).

## L'orbe

Une petite orbe animée s'affiche en bas à droite de l'écran : **bleue** = en veille, **cyan** = écoute, **orange** = réfléchit, **verte** = parle, **rouge** = erreur.
Clic = **couper la parole** de Jarvis · glisser = déplacer · clic droit = menu (Quitter). Désactivable avec `ui.orb: false`.

## Mesurer la vitesse

Après chaque phrase, la console affiche par exemple :
`⏱ 1.4 s entre la fin de votre phrase et la voix (transcription 0.4 s · cerveau 0.8 s · synthèse 0.2 s)`.
Cela montre quelle étape ralentit. Tout est aussi enregistré dans `data/jarvis.log` (à joindre en cas de problème).

## Notes, mémoire, rappels

- **Notes** : « prends en note… » ajoute une ligne horodatée dans `data/notes.txt` ; « lis mes notes » relit les dernières.
- **Mémoire** : « retiens que… » range un fait dans `data/memory.json` ; Jarvis s'en sert dans ses réponses, même après un redémarrage. « Oublie tout ce que tu sais » l'efface (avec confirmation).
- **Rappels** : programmés en mémoire vive, donc **perdus si Jarvis redémarre**.
- Ces fichiers sont personnels : le dossier `data/` n'est jamais publié sur GitHub (`.gitignore`).

## Recherche sur internet

Pour une question d'actualité ou de fait récent, le modèle appelle l'outil `lookup_online` (DuckDuckGo) puis résume les extraits. C'est le seul cas où le contenu de votre question quitte le PC. Les extraits sont traités comme des données, jamais comme des ordres. La recherche peut échouer ponctuellement (limitation de débit) : Jarvis le dit.

## Votre RTX 5070

- Whisper (`medium`, `float16`) occupe environ 1,5 Go de VRAM et `qwen3.5:9b` environ 6,6 Go : l'ensemble tient dans les 12 Go.
- Les RTX 50xx (Blackwell) exigent les bibliothèques **CUDA 12.8 minimum** ; `requirements.txt` installe les bonnes (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`). Évitez les modes `int8` sur ces cartes.
- Au démarrage, Jarvis teste vraiment le GPU. En cas d'échec il **retombe tout seul sur le processeur** et l'indique dans les logs (« GPU indisponible… »), plus lent mais fonctionnel.
- Pour vérifier que le modèle est bien sur le GPU : `ollama ps` (colonne PROCESSOR : « 100% GPU »).

## Configuration (`config.yaml`)

- **`apps`** : liste blanche des applications lançables. **`sites`** : sites que « ouvre <nom> » ouvre directement.
- **`llm.model`** : `qwen3.5:9b` (défaut), `qwen3:14b` (plus malin mais très juste en VRAM, donc plus lent si le modèle déborde), `llama3.1:8b`.
- **`llm.think: false`** : désactive le mode « réflexion » du modèle, trop lent pour la voix.
- **`stt.model_size`** : `medium` par défaut ; `small` si vous voulez libérer de la VRAM.
- **`wake_word.threshold`** : le modèle `hey_jarvis` est entraîné sur de l'anglais ; avec un accent français, baissez le seuil (ex. 0.35) s'il réagit mal.
- **`tts`** : voix `fr-FR-HenriNeural`, `fr-FR-DeniseNeural`… ou `pyttsx3` hors ligne.

## Ce qu'on perd face à une IA en ligne

Un modèle de 9 milliards de paramètres comprend moins bien les demandes floues ou enchaînées, se trompe parfois d'outil, a moins de culture générale et ne connaît pas l'actualité. C'est pour cela que les commandes courantes passent par règles. Si une phrase n'est pas comprise, reformulez plus simplement (« ouvre Spotify » plutôt qu'une phrase longue).

## Télécharger un `.exe`

Un workflow GitHub construit `Jarvis.exe` sur un serveur Windows : onglet **Actions > Build Windows exe > Run workflow**, ou créez une **Release** avec un tag `v0.1.0`. Dézippez et double-cliquez.

Attention : **Ollama reste à installer à part** (le modèle n'est pas dans l'exe), et l'exe est très volumineux (plusieurs Go avec les bibliothèques GPU). Le GPU dans l'exe est la partie la plus fragile : en cas de problème, Whisper bascule sur le processeur ; lancer depuis Python (`python main.py`) reste l'option la plus fiable.

## Reconnaissance de *votre* voix (optionnel)

```powershell
pip install torch librosa scipy webrtcvad-wheels
pip install resemblyzer --no-deps
python main.py --enroll
```
Puis reportez le seuil suggéré dans `config.yaml` et passez `speaker_verification.enabled` à `true`. C'est un filtre de confort, pas une sécurité forte ; l'empreinte (`data/`) est une donnée biométrique : ne la publiez jamais.

## Sécurité

Liste blanche d'applications, jamais de `shell=True`, jamais de commande générée par le modèle ; extinction/redémarrage avec **confirmation vocale imposée par le code** (même via le chemin rapide) et délai de 20 s annulable ; seules les URL `http(s)` sont ouvertes.

## Ajouter une commande

1. **Un outil** (utilisable par le modèle) : un fichier dans `jarvis/skills/` avec une fonction `register(registry, config)` (voir `skills/web.py`), puis son ajout dans `build_registry` (`jarvis/app.py`).
2. **Une règle rapide** (instantanée) : une méthode dans `jarvis/brain/router.py`, ajoutée à `self.rules`.

## Structure

```
jarvis-local/
├── main.py, config.yaml
├── jarvis/
│   ├── app.py          boucle principale
│   ├── core/           audio, wake_word, stt (GPU), cuda_setup, tts (Piper), speaker_id
│   ├── ui/             orb.py (orbe animée)
│   ├── brain/          llm.py (Ollama), router.py (chemin rapide), tools.py
│   └── skills/         apps, web, websearch, weather, system, timer, memory
└── tests/              pytest (sans micro, sans réseau, sans Ollama)
```

Tests : `pip install -r requirements-dev.txt && pytest`

## Dépannage

| Problème | Piste |
|---|---|
| « Ollama ne répond pas » | Lancez Ollama (icône dans la barre des tâches) ou `ollama serve` |
| « Le modèle n'est pas installé » | `ollama pull qwen3.5:9b` |
| Premier ordre très lent | Normal : le modèle se charge en VRAM, ensuite il y reste 30 min |
| Réponses lentes (> 10 s) | `ollama ps` : si pas « 100% GPU », prenez un modèle plus petit ou fermez les applications qui occupent la VRAM |
| Log « GPU indisponible pour Whisper » | Mettez à jour le pilote NVIDIA, vérifiez l'installation de `nvidia-cublas-cu12`, ou gardez le repli processeur |
| Jarvis ne réagit pas à « Hey Jarvis » | Baissez `wake_word.threshold`, vérifiez le micro (`--list-devices`) |

## Licence

MIT — voir [LICENSE](LICENSE).
