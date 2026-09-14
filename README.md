# Jarvis HUD

A futuristic desktop AI assistant inspired by the cinematic feel of JARVIS and the calm premium motion of modern Apple-like voice interfaces. Built with Python and PySide6, this project focuses on a sleek sci-fi HUD with a glowing central core, animated listening waveform, dark glass aesthetic, and a clean minimal experience.

## ✨ Features

- Animated central JARVIS reactor core
- Live waveform listening and responding effect
- Premium dark futuristic HUD styling
- Startup boot sequence and cinematic UI transitions
- Real-time system status and clock display
- Weather and project activity-related UI support
- Minimal interface focused on the main assistant experience
- Easy to extend for AI workflows and future smart assistant features

## 🧩 Project files

- `jarvis_hud.py` – main cinematic desktop GUI
- `jarvis_agentic.py` – agent-style workflow runtime
- `jarvis.py` – clap-based personal assistant script
- `jarvis_pro.py` – voice-driven assistant version
- `jarvis_max.py` – expanded assistant variant
- `requirements.txt` – base project requirements
- `requirements_pro.txt` – assistant / voice-related dependencies
- `requirements_ui.txt` – PySide6 and UI dependencies
- `jarvis_data/` – data files for memory, tasks, and activity
- `env.example.txt` – example environment configuration

## 🚀 Setup

Use Python 3.10+ and install the dependencies:

```powershell
cd "C:\Python313\jarvis-main\jarvis-main"
python -m pip install -r requirements.txt -r requirements_pro.txt -r requirements_ui.txt
```

## ⚙️ Environment

Create a `.env` file in the project folder using the sample values from `env.example.txt`.

Example:

```env
JARVIS_USER_NAME=Your Name
JARVIS_DEFAULT_CITY=Colombo
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
```

## ▶️ Run

Launch the main HUD:

```powershell
cd "C:\Python313\jarvis-main\jarvis-main"
python .\jarvis_hud.py
```

Run the assistant logic:

```powershell
cd "C:\Python313\jarvis-main\jarvis-main"
python .\jarvis_agentic.py
```

Run the original clap-based version:

```powershell
cd "C:\Python313\jarvis-main\jarvis-main"
python .\jarvis.py
```

## 🎯 Design direction

This project is intentionally designed around a luxury sci-fi aesthetic:

- premium dark UI palette
- minimal but polished layout
- animated central core as the visual focal point
- cinematic startup and listening behavior
- less dashboard clutter, more assistant presence

## 🛠️ Troubleshooting

If the GUI does not launch:

```powershell
python -c "import PySide6; print('PySide6 OK')"
```

If PySide6 is missing, install the UI dependencies again:

```powershell
python -m pip install -r requirements_ui.txt
```

If the assistant is not detecting audio properly, confirm your Windows microphone settings and ensure the correct input device is selected.

## 📜 License

This project is intended for personal and experimental use. If you plan to distribute or publish it, add a license file that matches your preferred usage terms.

## 🧠 GitHub note

This repository is structured as a personal AI assistant / desktop HUD prototype and is ready to be extended with more voice interaction, workflow automation, and advanced smart assistant features.
