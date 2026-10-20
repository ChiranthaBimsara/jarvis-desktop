# Jarvis Desktop

A sci-fi desktop command center built with Python and PySide6. Monitor your system, manage tasks, capture ideas, and run focus sessions around an animated JARVIS reactor.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Dashboard features

| Feature | What it does |
| --- | --- |
| Animated HUD | Reactor animation, boot sequence, live clock, and assistant status |
| Command palette | Search actions with `Ctrl+K`, select with arrow keys, and run with Enter |
| System radar | CPU, RAM, download, and upload graphs with 60 samples, refreshed every 1.5 seconds |
| Device health | Disk usage, free space, operating system, architecture, and host uptime |
| Task controls | Add, complete, and reopen tasks with local persistence |
| Activity search | Search the latest 500 event lines by text, type, or status |
| Focus Protocol | 25-minute focus, 50-minute deep work, and 5-minute break presets |
| Scratchpad | Save notes locally, with an unsaved-changes prompt on exit |
| Quick launch | Open ChatGPT, GitHub, and YouTube in your default browser |
| Fullscreen | Toggle with `F11` or the header button |
| Voice controls | Start and stop the optional assistant runtime and view its terminal output |

The dashboard, telemetry, tasks, notes, and focus timer work without API credentials. Voice interaction is a separate optional workflow that needs audio hardware and additional dependencies.

## Get started on Windows

Use Python 3.12 for the development environment tested in this project.

### 1. Get the code

```powershell
git clone https://github.com/ChiranthaBimsara/jarvis-desktop.git
cd jarvis-desktop
```

Already have the repository? Open its folder and run `git pull` to get the latest dashboard.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

The commands below use the virtual environment's Python directly, so PowerShell activation is not required.

### 3. Install and launch the dashboard

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements_ui.txt
.\.venv\Scripts\python.exe jarvis_hud.py
```

This installs everything needed for the visual dashboard. Install the voice dependencies only if you want to start the assistant.

## Try the controls

1. Wait for the boot animation to finish.
2. Press **Ctrl+K** or click **COMMANDS**. Type a command, use **↑ / ↓**, and press **Enter**. Press **Escape** to dismiss the palette.
3. In **Tasks**, enter a title and press **Enter** or click **ADD TASK**. Select a task and click **COMPLETE / REOPEN** to update it.
4. Open **Activity** to search assistant events. An empty list is normal before activity has been recorded.
5. Choose a **Focus Protocol** preset and click **START FOCUS**. Pause, resume, or reset the session whenever needed.
6. Open **Notes**, write something, and click **SAVE NOTES**.
7. Press **F11** for fullscreen. Click a quick-launch button to open its website.

The command palette also exposes notes, focus timer controls, fullscreen, refresh, voice start/stop, and clearing the live feed. Selecting a command runs it; typing alone does not.

### How the dashboard behaves

- Task and activity panels refresh every two seconds. Unreadable task data is reported rather than overwritten; malformed activity lines are skipped.
- Network graphs show host traffic in KB/s and scale independently. The first transfer rate appears after the second sample.
- Focus sessions use elapsed time, support pause/resume, and announce completion in the live feed. Sessions reset when the app restarts.
- Notes save only when you click **SAVE NOTES** or choose **Save** when closing. The exit prompt also lets you discard changes or cancel closing.
- The reactor shows **STANDBY** when the voice assistant is stopped. Starting the HUD alone does not start microphone listening.

## Optional voice assistant

Install the additional dependencies in the same environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements_pro.txt -r requirements_ui.txt
```

If you do not already have a `.env` file, copy the example:

```powershell
Copy-Item env.example.txt .env
```

Edit `.env` locally. Replace the example ElevenLabs key and voice ID if you want ElevenLabs speech, and check the microphone settings, including `JARVIS_INPUT_DEVICE`. Never commit real credentials.

The assistant scripts load `.env`. The HUD itself reads profile settings from its process environment; it does not load `.env` directly. To customize the HUD before launching it in PowerShell:

```powershell
$env:JARVIS_USER_NAME = "Your Name"
$env:JARVIS_DEFAULT_CITY = "Colombo"
.\.venv\Scripts\python.exe jarvis_hud.py
```

Click **START** in the dashboard to launch `jarvis_agentic.py`, or run it separately:

```powershell
.\.venv\Scripts\python.exe jarvis_agentic.py
```

Use **STOP** to terminate the assistant. Closing the HUD also stops the assistant process it launched.

Microphone access, audio playback, service credentials, and some desktop automation depend on your operating system and device. Voice functionality has not been validated in the headless cloud environment. ElevenLabs may require a paid account; the local dashboard does not.

## Linux and headless development

For a desktop Linux session:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements_ui.txt
.venv/bin/python jarvis_hud.py
```

Without a display, Qt can run offscreen for development and testing:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python jarvis_hud.py
```

Offscreen mode does not display an interactive window in your browser. Use a desktop session to interact with the dashboard.

Linux voice workflows also need PortAudio (for example, the `libportaudio2` system package on Debian/Ubuntu), audio devices, and the voice Python dependencies. GUI automation may need a graphical session.

## Tests

Windows:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\.venv\Scripts\python.exe -m unittest -v test_command_center test_dashboard_tools
Remove-Item Env:QT_QPA_PLATFORM
```

Linux/cloud:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest -v test_command_center test_dashboard_tools
```

The 13 tests cover task persistence and error handling, activity filtering, command execution, telemetry calculations, timer behavior, note saving, fullscreen, and exit protection. The dashboard has also passed an offscreen boot and rendering check. These checks do not establish microphone or external voice-service readiness.

## Project files and local data

```text
jarvis-desktop/
├── jarvis_hud.py              # Main desktop application
├── command_center.py         # Palette, telemetry, tasks, and activity widgets
├── dashboard_tools.py        # Focus timer, scratchpad, and device health
├── jarvis_agentic.py          # Optional assistant runtime
├── jarvis_max.py              # Expanded assistant behavior
├── jarvis_pro.py              # Voice assistant support
├── jarvis.py                  # Original clap-based assistant
├── requirements*.txt          # Dashboard and assistant dependencies
├── test_command_center.py
├── test_dashboard_tools.py
├── env.example.txt            # Optional voice configuration template
└── jarvis_data/               # Runtime data; created when needed
```

Tasks are stored in `jarvis_data/tasks.json`, notes in `jarvis_data/scratchpad.txt`, and assistant events in `jarvis_data/activity.jsonl`. The assistant also uses this directory for memory and approvals. Back up data you want to keep. These files can contain personal information; review them before adding any runtime data to Git.

## Troubleshooting

- **Missing PySide6 or psutil:** install `requirements_ui.txt` using the same Python executable you use to launch the app.
- **No visible window:** unset `QT_QPA_PLATFORM` if it is set to `offscreen`, then launch from a desktop session.
- **START exits immediately:** inspect the live feed, install the voice dependencies, and check audio devices and configuration.
- **PortAudio library not found:** install your platform's PortAudio runtime before starting the voice assistant.
- **Notes did not save:** read the status below the save button and check that `jarvis_data` is writable. Failed saves keep your edited text available.
- **Empty activity:** events appear as the assistant records them; the panel does not generate sample activity.

## License

[MIT](LICENSE)
