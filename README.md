# 🎙️ Jarvis — assistant vocal personnel pour PC

Un assistant vocal en français inspiré de J.A.R.V.I.S. (Iron Man). Dites **« Hey Jarvis »**, puis demandez :

- « Lance Spotify », « Ouvre le bloc-notes »
- « Ouvre YouTube », « Cherche des recettes de crêpes sur YouTube »
- « Ouvre les paramètres Wi-Fi »
- « Quel temps fera-t-il demain à Paris ? »
- « Mets un minuteur de dix minutes pour les pâtes », « Baisse un peu le son », « Pause »
- « Éteins l'ordinateur » *(demande une confirmation vocale)*
- Et toute question générale : Jarvis répond à voix haute.

## Comment ça marche

```
Micro → Mot d'activation (openWakeWord, local)
      → Enregistrement de la phrase (détection de silence)
      → [Vérification de votre voix — optionnel, Resemblyzer]
      → Voix → texte (faster-whisper, local)
      → Cerveau : Claude + outils (API Anthropic)
      → Actions : applications, web, paramètres, météo, minuteurs…
      → Texte → voix (edge-tts, repli pyttsx3)
```

| Brique | Local / Cloud |
|---|---|
| Mot d'activation, reconnaissance vocale, empreinte vocale | **Local** (rien n'est envoyé hors du PC) |
| Cerveau (compréhension + réponses) | **Cloud** : seul le *texte* de vos demandes est envoyé à l'API Anthropic |
| Voix de Jarvis | **Cloud** avec `edge`, **local** avec `pyttsx3` |
| Météo | API Open-Meteo (gratuite, sans clé) |

Le LLM ne code pas les actions : il *choisit un outil* parmi ceux déclarés dans `jarvis/skills/`, et c'est le code Python qui décide ce qui s'exécute vraiment.

## Installation (Windows)

Prérequis : **Python 3.10 à 3.12**, un micro, et une [clé API Anthropic](https://console.anthropic.com/).

```powershell
git clone https://github.com/<votre-compte>/jarvis.git
cd jarvis
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # puis éditez .env et collez votre clé API
```

### Lancer

```powershell
python main.py --text       # 1) tester le cerveau et les outils, sans micro
python main.py --text --speak   # 2) idem, avec la voix de Jarvis
python main.py              # 3) mode vocal complet : dites « Hey Jarvis »
```

Au premier lancement vocal, les modèles Whisper et openWakeWord sont téléchargés (quelques centaines de Mo).

Autres commandes : `python main.py --list-devices` (choisir son micro), `python main.py -v` (logs détaillés), `python main.py --enroll` (empreinte vocale).

> Dites « **au revoir Jarvis** » (ou « éteins-toi ») pour l'arrêter.

## Configuration

Tout se règle dans [`config.yaml`](config.yaml) :

- **`apps`** : la liste blanche des applications que Jarvis peut lancer. Ajoutez les vôtres (nom → exécutable, chemin ou URI comme `spotify:`).
- **`wake_word`** : seuil de détection. Le modèle `hey_jarvis` est entraîné sur de l'anglais : avec un accent français il fonctionne en général bien, sinon baissez `threshold` (ex. 0.35). Mettez `enabled: false` pour un mode « Entrée pour parler ».
- **`stt.model_size`** : `small` est un bon compromis sur CPU ; `medium`/`large-v3` si vous avez un GPU (`device: cuda`, `compute_type: float16`).
- **`llm.model`** : `claude-haiku-5-5` par défaut (rapide, économique) ; `claude-sonnet-5-5` pour des réponses plus fines.
- **`tts`** : voix (`fr-FR-HenriNeural`, `fr-FR-DeniseNeural`…) ou moteur hors ligne `pyttsx3`.
- **`assistant.user_title`** : comment Jarvis vous appelle (« Monsieur », « Boss »… ou vide).

Après une réponse, vous avez quelques secondes (`follow_up_seconds`) pour enchaîner sans redire « Jarvis ».

## Reconnaissance de *votre* voix (optionnel)

Par défaut, Jarvis comprend *ce que* vous dites mais obéit à tout le monde. Pour qu'il n'obéisse qu'à vous :

```powershell
pip install -r requirements-speaker.txt
pip install resemblyzer --no-deps
python main.py --enroll
```

L'assistant vous fait lire 5 phrases, calcule votre empreinte (`data/voiceprint.npy`), vous fait tester 3 phrases libres et suggère un seuil. Reportez-le dans `config.yaml` et passez `speaker_verification.enabled` à `true`.

Limites à connaître :
- C'est un **filtre de confort, pas une sécurité forte** : un enregistrement de votre voix peut tromper le système.
- La voix est vérifiée sur la **première phrase** de chaque conversation ; les phrases suivantes (fenêtre de suivi) sont considérées comme venant de vous. Les phrases très courtes (« météo ») sont peu fiables : formulez des phrases complètes.
- Resemblyzer est peu maintenu : si l'installation pose problème avec votre version de Python, c'est la brique à remplacer (SpeechBrain ECAPA-TDNN est une alternative).
- L'empreinte est une donnée biométrique : `data/` est dans le `.gitignore`, **ne la publiez jamais**.

## Sécurité

- **Liste blanche** : seules les apps de `config.yaml` peuvent être lancées ; jamais de `shell=True`, jamais de commande générée par le LLM.
- **Confirmation vocale** pour les actions sensibles (extinction, redémarrage), imposée par le code et non par le LLM. L'extinction a un délai de 20 s et reste annulable.
- Seules les URL `http(s)` sont ouvertes.
- La clé API reste dans `.env` (ignoré par git). Ne la commitez jamais.

## Ajouter une compétence

Une compétence = un fichier dans `jarvis/skills/` avec une fonction `register`. Exemple : lire le niveau de batterie.

```python
# jarvis/skills/battery.py
import psutil
from jarvis.brain.tools import Tool

def battery_status() -> str:
    b = psutil.sensors_battery()
    return "Pas de batterie." if b is None else f"{b.percent:.0f} % ({'en charge' if b.power_plugged else 'sur batterie'})"

def register(registry, config):
    registry.register(Tool(
        name="battery_status",
        description="Donne le niveau de batterie du PC.",
        input_schema={"type": "object", "properties": {}},
        func=battery_status,
    ))
```

Puis dans `jarvis/app.py`, importez le module et ajoutez `battery.register(registry, config)` dans `build_registry`. Le LLM saura l'utiliser tout seul grâce à la description.

## Structure

```
jarvis/
├── main.py                 point d'entrée
├── config.yaml             réglages + liste blanche d'apps
├── jarvis/
│   ├── app.py              boucle principale
│   ├── config.py
│   ├── core/               audio, wake_word, stt, tts, speaker_id
│   ├── brain/              llm.py (Claude + tool use), tools.py (registre)
│   └── skills/             apps, web, weather, system, timer
└── tests/                  pytest (sans micro ni réseau)
```

Tests : `pip install -r requirements-dev.txt && pytest`

## Dépannage

| Problème | Piste |
|---|---|
| Jarvis ne réagit pas à « Hey Jarvis » | Baissez `wake_word.threshold`, vérifiez le micro (`--list-devices`, `audio.input_device`) |
| Il se déclenche tout seul | Montez `wake_word.threshold` |
| Il coupe ma phrase ou n'entend pas la fin | Ajustez `silence_duration` et `min_rms` |
| Transcription approximative | Passez à `stt.model_size: medium` |
| Pas de voix / erreur edge-tts | Vérifiez internet, ou `tts.engine: pyttsx3` |
| `ANTHROPIC_API_KEY manquante` | Créez `.env` depuis `.env.example` |

## Pistes d'évolution

Interface animée façon Jarvis (orbe PyQt/Tauri), icône dans la barre système et démarrage automatique, mémoire à long terme, recherche web, agenda/mails, domotique, contrôle d'apps par fenêtre, interruption de Jarvis pendant qu'il parle.

## Licence

MIT — voir [LICENSE](LICENSE).
