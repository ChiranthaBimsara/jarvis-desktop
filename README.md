# Jarvis HUD

A futuristic desktop AI assistant inspired by JARVIS and premium Apple-style voice interfaces.

Built with Python and PySide6, this project delivers a sleek sci-fi HUD with a glowing central core, animated listening waveform, startup boot sequence, dark glass styling, and a clean minimal experience.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

This project is a personal desktop assistant prototype built to feel like a premium AI control surface. It combines a cinematic visual shell with assistant-style workflows, voice-driven behavior, and a minimal futuristic dashboard experience.

## Main files

- `jarvis_hud.py` – main desktop HUD interface
- `jarvis_agentic.py` – assistant runtime / agent workflow script
- `jarvis.py` – original clap-based assistant
- `jarvis_pro.py` – voice assistant variant
- `jarvis_max.py` – expanded assistant variant
- `requirements.txt` – base Python dependencies
- `requirements_pro.txt` – assistant / voice dependencies
- `requirements_ui.txt` – UI dependencies for PySide6
- `jarvis_data/` – tasks, memory, approvals, activity data
- `env.example.txt` – sample environment variables
- `start_jarvis_hud.bat` – quick launcher for Windows

## Features

- Command palette (`Ctrl+K`) for task entry, activity search, refresh, voice controls, and clearing the live feed
- System radar with CPU, RAM, download, and upload histories (60 samples, updated every 1.5 seconds)
- Task controls to add, complete, and reopen tasks, persisted in `jarvis_data/tasks.json`
- Searchable activity by text, event type, or status, showing the latest 500 events
- Animated central JARVIS reactor core
- Live waveform listening / responding effect
- Dark futuristic premium HUD styling
- Startup boot animation and status flow
- Real-time clock and system status display
- Weather and activity support
- Minimal but cinematic interface
- Easy to extend for AI agent workflows and automation

## Project structure

```text
jarvis-main/
├── jarvis_hud.py
├── jarvis_agentic.py
├── jarvis.py
├── jarvis_pro.py
├── jarvis_max.py
├── requirements.txt
├── requirements_pro.txt
├── requirements_ui.txt
├── env.example.txt
├── .env
├── jarvis_data/
├── README.md
├── start_jarvis_hud.bat
└── JARVIS_HUD_SETUP.txt
```

## Step-by-step setup

### 1) Open PowerShell in the project folder

```powershell
cd "C:\Python313\jarvis-main\jarvis-main"
```

### 2) Install dependencies

```powershell
python -m pip install -r requirements.txt -r requirements_pro.txt -r requirements_ui.txt
```

### 3) Create the environment file

```powershell
copy .\env.example.txt .\.env
```

Then edit `.env` and add your values:

```env
JARVIS_USER_NAME=Your Name
JARVIS_DEFAULT_CITY=Colombo
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
```

### 4) Verify the UI is installed

```powershell
python -c "import PySide6; print('PySide6 OK')"
```

If that prints `PySide6 OK`, the GUI dependencies are available.

### 5) Run the main Jarvis HUD

```powershell
python .\jarvis_hud.py
```

### 6) Optional: run the assistant logic separately

```powershell
python .\jarvis_agentic.py
```

### 7) Optional: run the original clap-based assistant

```powershell
python .\jarvis.py
```

## Quick start

### Command center

The expanded dashboard also includes:

- **Focus Protocol:** 25-minute focus, 50-minute deep work, and 5-minute break
  presets, with pause, resume, reset, and a completion alert in the live feed.
  Sessions run while the app is open and reset when it restarts.
- **Notes:** a local scratchpad saved to `jarvis_data/scratchpad.txt`. Click
  **SAVE NOTES** to persist changes; closing with unsaved notes prompts you to
  save, discard, or cancel.
- **Device Health:** disk usage, free space, operating system, and host uptime.
- **Quick Launch:** buttons for ChatGPT, GitHub, and YouTube in your default browser.
- **Fullscreen:** press `F11` or click the fullscreen button to toggle.

The HUD now includes system radar on the left and Tasks / Activity tabs on the right.
Press `Ctrl+K` or click **COMMANDS**, type to filter, use the arrow keys to select,
then press Enter. Escape closes the palette. Commands run only when selected.

In **Tasks**, enter a title and press Enter or click **ADD TASK**. Select a task and
click **COMPLETE / REOPEN** to change its status. Changes persist across restarts;
the panel refreshes every two seconds to pick up assistant updates. Invalid task
data is reported rather than overwritten. Activity search is case insensitive,
and malformed event lines are skipped. Telemetry and task controls work without
the voice assistant or API credentials. Network graphs show host traffic in KB/s
and scale independently; their first rate appears after the second sample.

For Linux cloud development without a display:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python jarvis_hud.py
```

Run the command center interaction tests:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest -v test_command_center test_dashboard_tools
```

### Windows launcher

If everything is already installed:

```powershell
cd "C:\Python313\jarvis-main\jarvis-main"
python .\jarvis_hud.py
```

## Important note

The main visual app is `jarvis_hud.py`. If you want the premium desktop Jarvis interface, launch that file. The other scripts are supporting assistant variants and may be used for different behavior or testing.

## Design direction

This project is intentionally designed to feel like:

- a premium AI assistant control panel
- a futuristic sci-fi command center
- a cinematic voice interface instead of a cluttered dashboard

The goal is to keep the experience clean, elegant, and visually impressive while still being usable as a desktop assistant.

## Troubleshooting

### GUI not opening

```powershell
python -c "import PySide6; print('PySide6 OK')"
```

If PySide6 is missing:

```powershell
python -m pip install -r requirements_ui.txt
```

### Audio or microphone not working

- Check Windows microphone settings
- Confirm the default input device is active
- Retry after restarting the app

### Missing modules

```powershell
python -m pip install -r requirements.txt -r requirements_pro.txt -r requirements_ui.txt
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## GitHub project note

This repository is structured as a personal AI assistant / desktop HUD prototype and is ready to be extended with voice interactions, automation, workflows, and more advanced assistant features.
