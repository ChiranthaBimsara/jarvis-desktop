#!/usr/bin/env python3
"""
JARVIS PRO - Windows voice assistant
- Double clap wakes Jarvis
- ElevenLabs voice replies (cached)
- Google Speech Recognition via SpeechRecognition package (no PyAudio needed)
- Voice commands for apps, websites, searches, system controls, notes, reminders, calculator, etc.
- Say "Jarvis sleep" to return to clap mode
- Say "Jarvis exit" to quit

Keep your API key in .env:
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...
"""

from __future__ import annotations

import ast
import hashlib
import logging
import math
import operator
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import wave
import webbrowser
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import psutil
except ImportError:
    psutil = None

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SAMPLE_RATE = int(os.getenv("JARVIS_SAMPLE_RATE", "44100"))
CHANNELS = 1
BLOCK_MS = 40

# Clap sensitivity
SPIKE_RATIO = float(os.getenv("JARVIS_SPIKE_RATIO", "7.0"))
COOLDOWN_S = 0.45
MIN_DOUBLE_GAP_S = 0.05
MAX_DOUBLE_GAP_S = 0.40
RETRIGGER_RATIO = 0.55
NOISE_FLOOR_ALPHA = 0.992
MIN_RMS = 0.012
QUIET_GATE_MULT = 2.2

# Voice command recording
COMMAND_MAX_SECONDS = float(os.getenv("JARVIS_COMMAND_MAX_SECONDS", "8"))
COMMAND_SILENCE_SECONDS = float(os.getenv("JARVIS_COMMAND_SILENCE_SECONDS", "1.1"))
COMMAND_MIN_RMS = float(os.getenv("JARVIS_COMMAND_MIN_RMS", "0.008"))
COMMAND_START_TIMEOUT = float(os.getenv("JARVIS_COMMAND_START_TIMEOUT", "7"))

# Behavior
REQUIRE_WAKE_WORD = os.getenv("JARVIS_REQUIRE_WAKE_WORD", "false").lower() == "true"
WAKE_WORDS = ("jarvis", "jervis", "service", "travis")
WELCOME_ON_CLAP = os.getenv("JARVIS_WELCOME_ENABLED", "true").lower() == "true"

SONG_URI = os.getenv(
    "SONG_URI",
    "https://open.spotify.com/track/39shmbIHICJ2Wxnk1fPSdz?si=2900c75c2e2d4b82",
)

JARVIS_WELCOME_PHRASE = os.getenv(
    "JARVIS_WELCOME_PHRASE",
    "Welcome back, sir. All systems are online. How may I assist you?",
)

# TTS
ELEVENLABS_API_KEY = (os.getenv("ELEVENLABS_API_KEY") or "").strip()
ELEVENLABS_VOICE_ID = (os.getenv("ELEVENLABS_VOICE_ID") or "").strip()
ELEVENLABS_MODEL_ID = (os.getenv("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2").strip()
ELEVENLABS_OUTPUT_FORMAT = (os.getenv("ELEVENLABS_OUTPUT_FORMAT") or "pcm_24000").strip()
USE_ELEVENLABS = os.getenv("JARVIS_USE_ELEVENLABS", "true").lower() == "true"

CACHE_DIR = BASE_DIR / ".cache" / "jarvis_tts"
NOTES_DIR = BASE_DIR / "jarvis_notes"
SCREENSHOT_DIR = BASE_DIR / "screenshots"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("jarvis-pro")

# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

def pcm_sample_rate() -> int:
    if ELEVENLABS_OUTPUT_FORMAT.startswith("pcm_"):
        try:
            return int(ELEVENLABS_OUTPUT_FORMAT.split("_", 1)[1])
        except Exception:
            pass
    return 24000


def cache_path_for(text: str) -> Path:
    key = f"{text}|{ELEVENLABS_VOICE_ID}|{ELEVENLABS_MODEL_ID}|{ELEVENLABS_OUTPUT_FORMAT}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:28]
    return CACHE_DIR / f"{digest}.wav"


def play_wav(path: Path) -> bool:
    try:
        with wave.open(str(path), "rb") as wf:
            rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
            channels = wf.getnchannels()
            width = wf.getsampwidth()
        if channels != 1 or width != 2 or not raw:
            return False
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        sd.play(audio, rate)
        sd.wait()
        return True
    except Exception as e:
        log.warning("WAV playback failed: %s", e)
        return False


def save_pcm_wav(path: Path, raw: bytes, rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(raw)


def windows_speak(text: str) -> None:
    safe = text.replace("'", "''")
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.Speak('{safe}')"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except Exception:
        pass


def speak(text: str) -> None:
    text = str(text).strip()
    if not text:
        return

    print(f"JARVIS: {text}")
    log.info("JARVIS: %s", text)

    if USE_ELEVENLABS and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
        cp = cache_path_for(text)
        if cp.exists() and play_wav(cp):
            return
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            chunks = client.text_to_speech.convert(
                voice_id=ELEVENLABS_VOICE_ID,
                text=text,
                model_id=ELEVENLABS_MODEL_ID,
                output_format=ELEVENLABS_OUTPUT_FORMAT,
            )
            raw = b"".join(chunks)
            if raw:
                save_pcm_wav(cp, raw, pcm_sample_rate())
                play_wav(cp)
                return
        except Exception as e:
            log.warning("ElevenLabs failed, using Windows voice: %s", e)

    windows_speak(text)


# ---------------------------------------------------------------------------
# MICROPHONE + SPEECH RECOGNITION
# ---------------------------------------------------------------------------

def input_devices():
    return [
        (i, d)
        for i, d in enumerate(sd.query_devices())
        if d["max_input_channels"] >= 1
    ]


def resolve_input_device() -> int:
    override = (os.getenv("JARVIS_INPUT_DEVICE") or "").strip()
    if override:
        if override.isdigit():
            return int(override)
        for idx, dev in input_devices():
            if override.lower() in dev["name"].lower():
                return idx

    default = sd.default.device[0]
    if default is not None and default >= 0:
        return int(default)

    devices = input_devices()
    if not devices:
        raise RuntimeError("No microphone input device found.")
    return devices[0][0]


def rms(data: np.ndarray) -> float:
    if data.size == 0:
        return 0.0
    x = data.astype(np.float64)
    if x.ndim > 1:
        x = np.mean(x, axis=1)
    return float(np.sqrt(np.mean(x * x)))


def wait_for_double_clap(device: int) -> None:
    blocksize = max(1, int(SAMPLE_RATE * BLOCK_MS / 1000))
    noise_floor = 1e-4
    first_clap = None
    spike_armed = True
    last_double = 0.0

    log.info("Clap mode active. Double clap to wake Jarvis.")

    with sd.InputStream(
        device=device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=blocksize,
    ) as stream:
        while True:
            data, overflow = stream.read(blocksize)
            level = rms(data)

            if level < noise_floor * QUIET_GATE_MULT:
                noise_floor = (
                    NOISE_FLOOR_ALPHA * noise_floor
                    + (1 - NOISE_FLOOR_ALPHA) * level
                )
                noise_floor = max(noise_floor, 1e-7)

            threshold = max(noise_floor * SPIKE_RATIO, MIN_RMS)
            now = time.monotonic()

            if level < threshold * RETRIGGER_RATIO:
                spike_armed = True

            if (
                spike_armed
                and level >= threshold
                and now - last_double >= COOLDOWN_S
            ):
                spike_armed = False
                if first_clap is None:
                    first_clap = now
                else:
                    gap = now - first_clap
                    if gap < MIN_DOUBLE_GAP_S:
                        continue
                    if gap <= MAX_DOUBLE_GAP_S:
                        log.info("Double clap detected (gap %.3fs)", gap)
                        return
                    first_clap = now

            if first_clap is not None and now - first_clap > MAX_DOUBLE_GAP_S:
                first_clap = None


def record_command(device: int) -> np.ndarray | None:
    """Wait for speech, record until silence, return mono float32 audio."""
    block_ms = 50
    blocksize = int(SAMPLE_RATE * block_ms / 1000)
    start_deadline = time.monotonic() + COMMAND_START_TIMEOUT
    chunks = []
    speech_started = False
    silence_time = 0.0
    max_blocks = int(COMMAND_MAX_SECONDS * 1000 / block_ms)

    with sd.InputStream(
        device=device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=blocksize,
    ) as stream:
        for _ in range(max_blocks + int(COMMAND_START_TIMEOUT * 1000 / block_ms)):
            data, _ = stream.read(blocksize)
            level = rms(data)

            if not speech_started:
                if level >= COMMAND_MIN_RMS:
                    speech_started = True
                    chunks.append(data.copy())
                elif time.monotonic() >= start_deadline:
                    return None
                continue

            chunks.append(data.copy())

            if level < COMMAND_MIN_RMS * 0.75:
                silence_time += block_ms / 1000
            else:
                silence_time = 0.0

            if silence_time >= COMMAND_SILENCE_SECONDS:
                break

            if len(chunks) >= max_blocks:
                break

    if not chunks:
        return None
    return np.concatenate(chunks, axis=0).flatten()


def recognize_audio(audio: np.ndarray) -> str:
    if sr is None:
        raise RuntimeError("SpeechRecognition is not installed.")

    pcm16 = np.clip(audio, -1, 1)
    pcm16 = (pcm16 * 32767).astype(np.int16).tobytes()
    audio_data = sr.AudioData(pcm16, SAMPLE_RATE, 2)
    recognizer = sr.Recognizer()

    # Free Google recognizer; internet required.
    try:
        text = recognizer.recognize_google(audio_data, language=os.getenv("JARVIS_LANGUAGE", "en-US"))
        return text.strip()
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        log.warning("Speech recognition network error: %s", e)
        return ""


def listen_command(device: int) -> str:
    print("\nListening for command...")
    audio = record_command(device)
    if audio is None:
        return ""
    text = recognize_audio(audio)
    if text:
        print(f"YOU: {text}")
        log.info("YOU: %s", text)
    return text


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def open_url(url: str) -> None:
    webbrowser.open(url)


def google_search(query: str) -> None:
    open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(query))


def youtube_search(query: str) -> None:
    open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query))


def maps_search(query: str) -> None:
    open_url("https://www.google.com/maps/search/" + urllib.parse.quote_plus(query))


def launch(command, shell=False) -> bool:
    try:
        subprocess.Popen(
            command,
            shell=shell,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        log.warning("Launch failed: %s", e)
        return False


def open_cursor() -> bool:
    candidates = [
        Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "cursor" / "Cursor.exe",
        Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Cursor" / "Cursor.exe",
        Path(os.getenv("PROGRAMFILES", "")) / "Cursor" / "Cursor.exe",
    ]
    for p in candidates:
        if p.is_file():
            return launch([str(p)])
    exe = shutil.which("cursor")
    if exe:
        return launch([exe])
    return False


SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "email": "https://mail.google.com",
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "claude": "https://claude.ai/new",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "whatsapp": "https://web.whatsapp.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "github": "https://github.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "calendar": "https://calendar.google.com",
    "spotify": "https://open.spotify.com",
    "binance": "https://www.binance.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
}

WINDOWS_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "file explorer": ["explorer.exe"],
    "explorer": ["explorer.exe"],
    "settings": ["cmd", "/c", "start", "ms-settings:"],
    "task manager": ["taskmgr.exe"],
    "command prompt": ["cmd.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "control panel": ["control.exe"],
}

FOLDERS = {
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "pictures": Path.home() / "Pictures",
    "videos": Path.home() / "Videos",
    "music": Path.home() / "Music",
}

# ---------------------------------------------------------------------------
# SAFE CALCULATOR
# ---------------------------------------------------------------------------

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_calculate(expr: str):
    expr = (
        expr.lower()
        .replace("plus", "+")
        .replace("minus", "-")
        .replace("times", "*")
        .replace("multiplied by", "*")
        .replace("divided by", "/")
    )
    tree = ast.parse(expr, mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left = ev(node.left)
            right = ev(node.right)
            # avoid absurd exponent calculations
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent too large")
            return _BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](ev(node.operand))
        raise ValueError("Unsupported calculation")

    return ev(tree)


# ---------------------------------------------------------------------------
# REMINDERS + NOTES
# ---------------------------------------------------------------------------

def reminder_worker(seconds: int, message: str) -> None:
    time.sleep(max(0, seconds))
    speak(f"Sir, reminder. {message}")


def parse_reminder(text: str):
    m = re.search(
        r"remind me in\s+(\d+)\s*(second|seconds|minute|minutes|hour|hours)\s+(?:to\s+)?(.+)",
        text,
        re.I,
    )
    if not m:
        return None
    amount = int(m.group(1))
    unit = m.group(2).lower()
    message = m.group(3).strip()
    multiplier = 1 if "second" in unit else 60 if "minute" in unit else 3600
    return amount * multiplier, message


def save_note(text: str) -> Path:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"note_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# COMMAND ENGINE
# ---------------------------------------------------------------------------

HELP_TEXT = """
Main commands:
  open YouTube / Google / Gmail / ChatGPT / Claude / Facebook / Instagram
  open Google Drive / Calendar / WhatsApp / GitHub / Spotify / Binance
  open Notepad / Calculator / Paint / Explorer / Settings / Task Manager
  open Cursor
  open Downloads / Documents / Desktop / Pictures / Videos / Music

Search:
  search Google for ...
  Google ...
  search YouTube for ...
  YouTube ...
  search maps for ...
  find ... on Google

Computer:
  volume up / volume down / mute
  play pause / next track / previous track
  take screenshot
  type ...
  copy ...
  read clipboard
  lock computer
  shutdown computer / restart computer   (asks for confirmation)

Work:
  take a note ...
  remind me in 10 minutes to ...
  what time is it
  what date is it
  battery status
  calculate 25 * 14

Assistant:
  what can you do
  Jarvis sleep   -> return to clap mode
  Jarvis exit    -> close Jarvis
"""


class JarvisState:
    pending_dangerous_action: str | None = None
    pending_until: float = 0.0


STATE = JarvisState()


def strip_wake_word(text: str) -> tuple[str, bool]:
    t = text.strip().lower()
    heard = False
    for word in WAKE_WORDS:
        if t.startswith(word + " "):
            t = t[len(word):].strip(" ,")
            heard = True
            break
        if t == word:
            t = ""
            heard = True
            break
    return t, heard


def confirm_dangerous(action: str) -> None:
    STATE.pending_dangerous_action = action
    STATE.pending_until = time.monotonic() + 12
    speak(f"Please confirm. Say confirm {action}.")


def perform_dangerous(action: str) -> None:
    if action == "shutdown":
        subprocess.Popen(["shutdown", "/s", "/t", "0"])
    elif action == "restart":
        subprocess.Popen(["shutdown", "/r", "/t", "0"])


def handle_command(raw: str) -> str:
    """Returns: continue | sleep | exit"""
    if not raw:
        return "continue"

    text, had_wake = strip_wake_word(raw)

    if REQUIRE_WAKE_WORD and not had_wake:
        return "continue"

    text = text.strip().lower()
    if not text and had_wake:
        speak("Yes, sir?")
        return "continue"

    # confirmation gate
    if STATE.pending_dangerous_action:
        if time.monotonic() > STATE.pending_until:
            STATE.pending_dangerous_action = None
        elif text in (
            f"confirm {STATE.pending_dangerous_action}",
            "confirm",
            "yes confirm",
        ):
            action = STATE.pending_dangerous_action
            STATE.pending_dangerous_action = None
            speak(f"Confirmed. {action.capitalize()} now.")
            perform_dangerous(action)
            return "exit"
        elif text in ("cancel", "cancel that", "no"):
            STATE.pending_dangerous_action = None
            speak("Cancelled.")
            return "continue"

    # assistant mode
    if text in ("sleep", "go to sleep", "stand by", "standby", "stop listening"):
        speak("Standing by, sir.")
        return "sleep"

    if text in ("exit", "quit", "goodbye", "shut down jarvis", "close jarvis"):
        speak("Shutting down Jarvis. Goodbye, sir.")
        return "exit"

    if text in ("help", "commands", "what can you do", "show commands"):
        print(HELP_TEXT)
        speak("I displayed the command list on screen, sir.")
        return "continue"

    # time/date/status
    if "what time" in text or text == "time":
        speak(datetime.now().strftime("It is %I:%M %p, sir."))
        return "continue"

    if "what date" in text or "what day" in text or text == "date":
        speak(datetime.now().strftime("Today is %A, %B %d, %Y."))
        return "continue"

    if "battery" in text:
        if psutil:
            b = psutil.sensors_battery()
            if b:
                status = "charging" if b.power_plugged else "not charging"
                speak(f"Battery is at {round(b.percent)} percent and {status}.")
            else:
                speak("I could not read the battery status.")
        else:
            speak("Install psutil to read battery status.")
        return "continue"

    # calculator
    m = re.match(r"(?:calculate|compute|what is)\s+(.+)", text)
    if m:
        expr = m.group(1).strip().rstrip("?")
        try:
            result = safe_calculate(expr)
            speak(f"The answer is {result}.")
        except Exception:
            speak("I could not calculate that expression.")
        return "continue"

    # reminders
    reminder = parse_reminder(text)
    if reminder:
        seconds, msg = reminder
        threading.Thread(target=reminder_worker, args=(seconds, msg), daemon=True).start()
        speak(f"Reminder set for {msg}.")
        return "continue"

    # notes
    for prefix in ("take a note ", "take note ", "note this ", "remember this "):
        if text.startswith(prefix):
            note = raw[raw.lower().find(prefix) + len(prefix):].strip()
            path = save_note(note)
            speak("Note saved, sir.")
            log.info("Saved note: %s", path)
            return "continue"

    # web searches
    patterns = [
        (r"(?:search google for|google search|google)\s+(.+)", google_search, "Searching Google."),
        (r"(?:search youtube for|youtube search|youtube)\s+(.+)", youtube_search, "Searching YouTube."),
        (r"(?:search maps for|maps|find on maps)\s+(.+)", maps_search, "Opening Maps."),
        (r"find\s+(.+)\s+on google", google_search, "Searching Google."),
    ]
    for pattern, fn, reply in patterns:
        m = re.fullmatch(pattern, text)
        if m:
            speak(reply)
            fn(m.group(1))
            return "continue"

    # open website
    if text.startswith("open "):
        target = text[5:].strip()

        if target in SITES:
            speak(f"Opening {target}.")
            open_url(SITES[target])
            return "continue"

        if target in WINDOWS_APPS:
            ok = launch(WINDOWS_APPS[target])
            speak(f"Opening {target}." if ok else f"I could not open {target}.")
            return "continue"

        if target == "cursor":
            if open_cursor():
                speak("Opening Cursor.")
            else:
                speak("I could not find Cursor on this computer.")
            return "continue"

        if target in ("visual studio code", "vs code", "vscode"):
            exe = shutil.which("code")
            if exe:
                launch([exe])
                speak("Opening Visual Studio Code.")
            else:
                speak("Visual Studio Code command was not found.")
            return "continue"

        if target in FOLDERS:
            p = FOLDERS[target]
            if p.exists():
                os.startfile(str(p))
                speak(f"Opening {target}.")
            else:
                speak(f"I could not find the {target} folder.")
            return "continue"

        # unknown open command -> Google
        speak(f"I don't have a direct shortcut for {target}. Searching for it.")
        google_search(target)
        return "continue"

    # media + volume controls
    if pyautogui:
        if text in ("volume up", "increase volume", "turn volume up"):
            pyautogui.press("volumeup", presses=3)
            return "continue"
        if text in ("volume down", "decrease volume", "turn volume down"):
            pyautogui.press("volumedown", presses=3)
            return "continue"
        if text in ("mute", "mute volume", "unmute"):
            pyautogui.press("volumemute")
            return "continue"
        if text in ("play", "pause", "play pause", "play music", "pause music"):
            pyautogui.press("playpause")
            return "continue"
        if text in ("next", "next track", "next song"):
            pyautogui.press("nexttrack")
            return "continue"
        if text in ("previous", "previous track", "previous song"):
            pyautogui.press("prevtrack")
            return "continue"

        if text in ("take screenshot", "screenshot", "capture screen"):
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            path = SCREENSHOT_DIR / f"screenshot_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
            pyautogui.screenshot(str(path))
            speak("Screenshot saved.")
            log.info("Screenshot: %s", path)
            return "continue"

        if text.startswith("type "):
            content = raw[raw.lower().find("type ") + 5:]
            pyautogui.write(content, interval=0.02)
            return "continue"

    # clipboard
    if text.startswith("copy "):
        content = raw[raw.lower().find("copy ") + 5:]
        if pyperclip:
            pyperclip.copy(content)
            speak("Copied to clipboard.")
        else:
            speak("Install pyperclip for clipboard commands.")
        return "continue"

    if text in ("read clipboard", "what is in clipboard", "clipboard"):
        if pyperclip:
            value = pyperclip.paste()
            speak(value[:500] if value else "The clipboard is empty.")
        else:
            speak("Install pyperclip for clipboard commands.")
        return "continue"

    # Windows lock / power
    if text in ("lock computer", "lock pc", "lock screen"):
        speak("Locking the computer.")
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "continue"

    if text in ("shutdown computer", "shutdown pc", "turn off computer"):
        confirm_dangerous("shutdown")
        return "continue"

    if text in ("restart computer", "restart pc", "reboot computer"):
        confirm_dangerous("restart")
        return "continue"

    # generic navigation / convenience
    if text in ("open startup", "start work", "work mode"):
        speak("Starting work mode.")
        open_url("https://mail.google.com")
        open_url("https://calendar.google.com")
        open_url("https://chatgpt.com")
        return "continue"

    # fallback
    speak(f"I don't have a direct command for {raw}. I'll search Google.")
    google_search(raw)
    return "continue"


# ---------------------------------------------------------------------------
# STARTUP ACTIONS
# ---------------------------------------------------------------------------

def startup_actions() -> None:
    # Open song only if configured
    if SONG_URI.strip():
        try:
            os.startfile(SONG_URI)
        except Exception:
            webbrowser.open(SONG_URI)

    # Useful startup pages (can disable via .env)
    if os.getenv("JARVIS_OPEN_CLAUDE_ON_CLAP", "true").lower() == "true":
        open_url(os.getenv("CLAUDE_CODE_URL", "https://claude.ai/new"))

    if os.getenv("JARVIS_OPEN_BINANCE_ON_CLAP", "false").lower() == "true":
        open_url(os.getenv("BINANCE_BTC_URL", "https://www.binance.com/en/trade/BTC_USDT"))

    if os.getenv("JARVIS_OPEN_CURSOR_ON_CLAP", "false").lower() == "true":
        open_cursor()

    if WELCOME_ON_CLAP:
        time.sleep(0.8)
        speak(JARVIS_WELCOME_PHRASE)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def voice_session(device: int) -> str:
    speak("Voice command mode activated.")
    print(HELP_TEXT)

    while True:
        try:
            text = listen_command(device)
        except Exception as e:
            log.error("Listening failed: %s", e)
            speak("I had a microphone problem.")
            return "sleep"

        if not text:
            continue

        result = handle_command(text)
        if result == "sleep":
            return "sleep"
        if result == "exit":
            return "exit"


def main() -> int:
    if sr is None:
        print("Missing package: SpeechRecognition")
        print('Run: python -m pip install "SpeechRecognition>=3.10"')
        return 1

    device = resolve_input_device()
    dev = sd.query_devices(device)
    log.info("Using microphone [%d]: %s", device, dev["name"])

    speak("Jarvis is online.")

    while True:
        try:
            wait_for_double_clap(device)
            startup_actions()
            result = voice_session(device)
            if result == "exit":
                return 0
        except KeyboardInterrupt:
            print()
            log.info("Jarvis stopped.")
            return 0
        except sd.PortAudioError as e:
            log.error("Audio error: %s", e)
            return 1
        except Exception as e:
            log.exception("Unexpected error: %s", e)
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
