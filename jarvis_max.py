#!/usr/bin/env python3
"""
JARVIS MAX - personal desktop assistant for Chirantha Bimsara

Requires:
    jarvis_pro.py in the same folder.

Adds:
- Personal profile: Chirantha Bimsara, age 24
- Facebook / Meta / Messenger / Instagram shortcuts
- Facebook notifications page
- Optional Gmail-based social notification monitoring
- Weather by city using wttr.in
- ChatGPT / Claude / Gemini shortcuts
- Gmail / Calendar / Google Drive / YouTube / GitHub / LinkedIn
- Creator Mode / Work Mode / Study Mode / Social Media Mode
- Internet search shortcuts
- PC/system status
- IP address
- Open common Windows apps
- Website launcher
- Timers
- More natural voice phrases
- Safer shutdown/restart confirmations inherited from jarvis_pro.py

IMPORTANT:
This does NOT scrape Facebook or bypass login/security.
Automatic Facebook/Instagram alerts work by checking notification emails in Gmail,
if you enable Facebook/Instagram email notifications and configure a Gmail App Password.
"""

from __future__ import annotations

import email
import imaplib
import json
import os
import platform
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from email.header import decode_header
from pathlib import Path

from dotenv import load_dotenv

import jarvis_pro as jp

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# PERSONAL PROFILE
# ---------------------------------------------------------------------------

USER_NAME = os.getenv("JARVIS_USER_NAME", "Chirantha Bimsara").strip()
USER_FIRST_NAME = USER_NAME.split()[0] if USER_NAME else "Sir"
USER_AGE = int(os.getenv("JARVIS_USER_AGE", "24"))

# ---------------------------------------------------------------------------
# SOCIAL / NOTIFICATIONS
# ---------------------------------------------------------------------------

NOTIFICATION_CHECK_ENABLED = (
    os.getenv("JARVIS_NOTIFICATION_CHECK_ENABLED", "false").lower() == "true"
)
NOTIFICATION_CHECK_MINUTES = max(
    1, int(os.getenv("JARVIS_NOTIFICATION_CHECK_MINUTES", "5"))
)

GMAIL_ADDRESS = (os.getenv("JARVIS_GMAIL_ADDRESS") or "").strip()
GMAIL_APP_PASSWORD = (os.getenv("JARVIS_GMAIL_APP_PASSWORD") or "").replace(" ", "").strip()

SPEAK_SOCIAL_NOTIFICATIONS = (
    os.getenv("JARVIS_SPEAK_SOCIAL_NOTIFICATIONS", "true").lower() == "true"
)

SOCIAL_KEYWORDS = ("facebook", "meta", "instagram", "messenger")
_seen_message_ids: set[str] = set()
_notification_muted = False
_monitor_started = False
_lock = threading.Lock()

URLS = {
    # AI
    "chatgpt": "https://chatgpt.com",
    "chat gpt": "https://chatgpt.com",
    "claude": "https://claude.ai/new",
    "gemini": "https://gemini.google.com",

    # Meta / social
    "facebook": "https://www.facebook.com",
    "facebook notifications": "https://www.facebook.com/notifications",
    "facebook pages": "https://www.facebook.com/pages/?category=your_pages",
    "messenger": "https://www.messenger.com",
    "meta business suite": "https://business.facebook.com/latest/home",
    "business suite": "https://business.facebook.com/latest/home",
    "facebook insights": "https://business.facebook.com/latest/insights",
    "page insights": "https://business.facebook.com/latest/insights",
    "facebook content": "https://business.facebook.com/latest/content",
    "instagram": "https://www.instagram.com",

    # Google/productivity
    "gmail": "https://mail.google.com",
    "google mail": "https://mail.google.com",
    "calendar": "https://calendar.google.com",
    "google calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "google docs": "https://docs.google.com",
    "sheets": "https://sheets.google.com",
    "google sheets": "https://sheets.google.com",

    # Media/dev/work
    "youtube": "https://www.youtube.com",
    "spotify": "https://open.spotify.com",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "netflix": "https://www.netflix.com",
    "binance": "https://www.binance.com",
    "google news": "https://news.google.com",
    "news": "https://news.google.com",
}

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def open_url(url: str) -> None:
    webbrowser.open(url)


def say_personal_greeting() -> None:
    hour = datetime.now().hour
    if hour < 12:
        period = "Good morning"
    elif hour < 18:
        period = "Good afternoon"
    else:
        period = "Good evening"

    jp.speak(
        f"{period}, {USER_FIRST_NAME}. Jarvis Max is online. "
        "Your systems are ready."
    )


def _decode(value: str | None) -> str:
    if not value:
        return ""
    parts = []
    for chunk, enc in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts).strip()


# ---------------------------------------------------------------------------
# WEATHER
# ---------------------------------------------------------------------------

def get_weather(city: str) -> dict | None:
    """
    Uses wttr.in JSON endpoint. No API key required.
    """
    city = city.strip()
    if not city:
        return None

    url = (
        "https://wttr.in/"
        + urllib.parse.quote(city)
        + "?format=j1"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Jarvis-Max/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        current = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]

        area_name = (
            area.get("areaName", [{}])[0].get("value")
            if area.get("areaName")
            else city
        )

        country = (
            area.get("country", [{}])[0].get("value")
            if area.get("country")
            else ""
        )

        description = current.get("weatherDesc", [{}])[0].get("value", "")
        temp_c = current.get("temp_C", "?")
        feels_c = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")
        wind_kph = current.get("windspeedKmph", "?")

        return {
            "location": f"{area_name}, {country}".strip(", "),
            "description": description,
            "temp_c": temp_c,
            "feels_c": feels_c,
            "humidity": humidity,
            "wind_kph": wind_kph,
        }
    except Exception as e:
        jp.log.warning("Weather request failed: %s", e)
        return None


def speak_weather(city: str) -> None:
    jp.speak(f"Checking the weather in {city}.")
    weather = get_weather(city)

    if not weather:
        jp.speak(
            "I could not get the weather right now. "
            "I will open a weather search instead."
        )
        jp.google_search(f"weather {city}")
        return

    jp.speak(
        f"In {weather['location']}, it is {weather['temp_c']} degrees Celsius "
        f"with {weather['description']}. "
        f"It feels like {weather['feels_c']} degrees. "
        f"Humidity is {weather['humidity']} percent."
    )


# ---------------------------------------------------------------------------
# IP / SYSTEM STATUS
# ---------------------------------------------------------------------------

def local_ip() -> str:
    try:
        host = socket.gethostname()
        return socket.gethostbyname(host)
    except Exception:
        return "unknown"


def system_summary() -> str:
    cpu = platform.processor() or "your processor"
    system = platform.system()
    release = platform.release()

    if jp.psutil:
        mem = jp.psutil.virtual_memory()
        memory = round(mem.percent)
        b = jp.psutil.sensors_battery()
        if b:
            battery = f" Battery is {round(b.percent)} percent."
        else:
            battery = ""
        return (
            f"You are running {system} {release}. "
            f"Memory usage is {memory} percent.{battery}"
        )

    return f"You are running {system} {release} on {cpu}."


# ---------------------------------------------------------------------------
# TIMERS
# ---------------------------------------------------------------------------

def timer_worker(seconds: int, label: str) -> None:
    time.sleep(max(0, seconds))
    jp.speak(f"{USER_FIRST_NAME}, your timer is finished. {label}".strip())


def parse_timer(text: str):
    m = re.search(
        r"(?:set )?(?:a )?timer(?: for)?\s+(\d+)\s*"
        r"(second|seconds|minute|minutes|hour|hours)"
        r"(?:\s+(?:for|called|named)\s+(.+))?",
        text,
        re.I,
    )
    if not m:
        return None

    amount = int(m.group(1))
    unit = m.group(2).lower()
    label = (m.group(3) or "").strip()

    multiplier = 1 if "second" in unit else 60 if "minute" in unit else 3600
    return amount * multiplier, label


# ---------------------------------------------------------------------------
# GMAIL-BASED SOCIAL NOTIFICATION MONITOR
# ---------------------------------------------------------------------------

def gmail_configured() -> bool:
    return bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD)


def fetch_social_notification_emails(limit: int = 15) -> list[dict]:
    if not gmail_configured():
        return []

    mail = None
    found = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data:
            return []

        ids = data[0].split()[-limit:][::-1]

        for msg_id_bytes in ids:
            status, msg_data = mail.fetch(
                msg_id_bytes,
                "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
            )
            if status != "OK":
                continue

            raw = b""
            for item in msg_data:
                if isinstance(item, tuple) and isinstance(item[1], bytes):
                    raw += item[1]

            if not raw:
                continue

            msg = email.message_from_bytes(raw)
            subject = _decode(msg.get("Subject"))
            sender = _decode(msg.get("From"))
            message_id = _decode(msg.get("Message-ID")) or msg_id_bytes.decode()

            combined = f"{sender} {subject}".lower()
            if any(word in combined for word in SOCIAL_KEYWORDS):
                found.append(
                    {
                        "id": message_id,
                        "subject": subject or "Social notification",
                        "sender": sender,
                    }
                )

        return found

    except Exception as e:
        jp.log.warning("Social notification check failed: %s", e)
        return []
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass


def check_social_notifications(announce_empty: bool = True) -> int:
    global _seen_message_ids

    if not gmail_configured():
        if announce_empty:
            jp.speak(
                "Gmail notification monitoring is not configured yet. "
                "I can still open your Facebook notification page."
            )
        return 0

    items = fetch_social_notification_emails()
    new_items = []

    with _lock:
        for item in items:
            if item["id"] not in _seen_message_ids:
                _seen_message_ids.add(item["id"])
                new_items.append(item)

    if not new_items:
        if announce_empty:
            jp.speak("No new social notification emails, sir.")
        return 0

    count = len(new_items)
    latest = new_items[0]["subject"]

    if not _notification_muted and SPEAK_SOCIAL_NOTIFICATIONS:
        jp.speak(
            f"{USER_FIRST_NAME}, you have {count} new social notification"
            f"{'s' if count != 1 else ''}. Latest: {latest}"
        )

    return count


def notification_loop() -> None:
    # Seed existing unread notifications so they do not all speak at startup.
    for item in fetch_social_notification_emails():
        _seen_message_ids.add(item["id"])

    while True:
        time.sleep(NOTIFICATION_CHECK_MINUTES * 60)
        check_social_notifications(announce_empty=False)


def start_notification_monitor() -> None:
    global _monitor_started
    if _monitor_started or not NOTIFICATION_CHECK_ENABLED:
        return

    _monitor_started = True
    threading.Thread(
        target=notification_loop,
        daemon=True,
        name="JarvisSocialMonitor",
    ).start()


# ---------------------------------------------------------------------------
# MODES
# ---------------------------------------------------------------------------

def creator_mode() -> None:
    jp.speak("Starting creator mode.")
    for url in (
        URLS["meta business suite"],
        URLS["facebook notifications"],
        URLS["youtube"],
        URLS["chatgpt"],
    ):
        open_url(url)


def work_mode() -> None:
    jp.speak("Starting work mode.")
    for url in (
        URLS["gmail"],
        URLS["calendar"],
        URLS["drive"],
        URLS["chatgpt"],
    ):
        open_url(url)


def study_mode() -> None:
    jp.speak("Starting study mode.")
    for url in (
        URLS["chatgpt"],
        URLS["drive"],
        URLS["youtube"],
    ):
        open_url(url)


def ai_mode() -> None:
    jp.speak("Opening your AI workspace.")
    for url in (
        URLS["chatgpt"],
        URLS["claude"],
        URLS["gemini"],
    ):
        open_url(url)


# ---------------------------------------------------------------------------
# COMMAND ENGINE EXTENSION
# ---------------------------------------------------------------------------

_original_handle = jp.handle_command


def normalized(raw: str) -> str:
    text, _ = jp.strip_wake_word(raw)
    return text.lower().strip()


def max_handle_command(raw: str) -> str:
    global _notification_muted

    text = normalized(raw)

    # Personal
    if text in (
        "who am i",
        "what is my name",
        "tell me my name",
    ):
        jp.speak(f"You are {USER_NAME}, sir.")
        return "continue"

    if text in (
        "how old am i",
        "what is my age",
        "tell me my age",
    ):
        jp.speak(f"You are {USER_AGE} years old, {USER_FIRST_NAME}.")
        return "continue"

    if text in ("introduce me", "who is chirantha"):
        jp.speak(
            f"You are {USER_NAME}, age {USER_AGE}. "
            "I am your personal Jarvis assistant."
        )
        return "continue"

    # Weather
    m = re.match(
        r"(?:what(?:'s| is) the weather(?: like)? in|weather in|check weather in)\s+(.+)",
        text,
    )
    if m:
        speak_weather(m.group(1).strip())
        return "continue"

    if text in ("weather", "check weather", "weather today"):
        city = (os.getenv("JARVIS_DEFAULT_CITY") or "Colombo").strip()
        speak_weather(city)
        return "continue"

    # Timers
    timer = parse_timer(text)
    if timer:
        seconds, label = timer
        threading.Thread(
            target=timer_worker,
            args=(seconds, label),
            daemon=True,
        ).start()
        mins = round(seconds / 60, 1)
        jp.speak(
            f"Timer set for {mins} minutes."
            if seconds >= 60
            else f"Timer set for {seconds} seconds."
        )
        return "continue"

    # System
    if text in (
        "system status",
        "computer status",
        "pc status",
        "how is my computer",
    ):
        jp.speak(system_summary())
        return "continue"

    if text in ("my ip", "local ip", "ip address", "what is my ip"):
        jp.speak(f"Your local IP address is {local_ip()}.")
        return "continue"

    # AI websites
    if text in (
        "open chatgpt",
        "open chat gpt",
        "chatgpt",
        "chat gpt",
    ):
        jp.speak("Opening ChatGPT.")
        open_url(URLS["chatgpt"])
        return "continue"

    if text in ("open claude", "claude"):
        jp.speak("Opening Claude.")
        open_url(URLS["claude"])
        return "continue"

    if text in ("open gemini", "gemini"):
        jp.speak("Opening Gemini.")
        open_url(URLS["gemini"])
        return "continue"

    if text in ("ai mode", "open ai workspace", "start ai mode"):
        ai_mode()
        return "continue"

    # Social
    if text in (
        "open facebook notifications",
        "facebook notifications",
        "show facebook notifications",
        "open notifications",
    ):
        jp.speak("Opening Facebook notifications.")
        open_url(URLS["facebook notifications"])
        return "continue"

    if text in (
        "check facebook notifications",
        "check social notifications",
        "check notifications",
        "any notifications",
    ):
        check_social_notifications(True)
        return "continue"

    if text in ("open messenger", "messenger"):
        jp.speak("Opening Messenger.")
        open_url(URLS["messenger"])
        return "continue"

    if text in (
        "open meta business suite",
        "open business suite",
        "business suite",
    ):
        jp.speak("Opening Meta Business Suite.")
        open_url(URLS["meta business suite"])
        return "continue"

    if text in (
        "open facebook insights",
        "facebook insights",
        "open page insights",
        "page insights",
    ):
        jp.speak("Opening Facebook insights.")
        open_url(URLS["facebook insights"])
        return "continue"

    if text in (
        "open facebook content",
        "facebook content",
        "open meta content",
    ):
        jp.speak("Opening your Meta content dashboard.")
        open_url(URLS["facebook content"])
        return "continue"

    if text in ("open facebook pages", "my facebook pages"):
        jp.speak("Opening your Facebook pages.")
        open_url(URLS["facebook pages"])
        return "continue"

    if text in ("mute notifications", "mute social notifications"):
        _notification_muted = True
        jp.speak("Social voice notifications muted.")
        return "continue"

    if text in ("unmute notifications", "unmute social notifications"):
        _notification_muted = False
        jp.speak("Social voice notifications enabled.")
        return "continue"

    # Productivity modes
    if text in (
        "creator mode",
        "start creator mode",
        "social media mode",
        "facebook work mode",
    ):
        creator_mode()
        return "continue"

    if text in ("work mode", "start work mode"):
        work_mode()
        return "continue"

    if text in ("study mode", "start study mode"):
        study_mode()
        return "continue"

    # Quick website aliases
    if text.startswith("open "):
        target = text[5:].strip()
        if target in URLS:
            jp.speak(f"Opening {target}.")
            open_url(URLS[target])
            return "continue"

    # Search ChatGPT / YouTube / Google
    m = re.match(r"(?:ask chatgpt|search chatgpt for)\s+(.+)", text)
    if m:
        query = m.group(1)
        jp.speak("Opening ChatGPT for that.")
        open_url("https://chatgpt.com/?q=" + urllib.parse.quote_plus(query))
        return "continue"

    m = re.match(r"(?:search facebook for|facebook search)\s+(.+)", text)
    if m:
        query = m.group(1)
        jp.speak("Searching Facebook.")
        open_url(
            "https://www.facebook.com/search/top?q="
            + urllib.parse.quote_plus(query)
        )
        return "continue"

    m = re.match(r"(?:search instagram for|instagram search)\s+(.+)", text)
    if m:
        query = m.group(1)
        jp.speak("Searching Instagram.")
        jp.google_search(f"site:instagram.com {query}")
        return "continue"

    # More useful web tools
    if text in ("open news", "news", "latest news"):
        jp.speak("Opening Google News.")
        open_url(URLS["google news"])
        return "continue"

    if text in ("open linkedin", "linkedin"):
        jp.speak("Opening LinkedIn.")
        open_url(URLS["linkedin"])
        return "continue"

    if text in ("open github", "github"):
        jp.speak("Opening GitHub.")
        open_url(URLS["github"])
        return "continue"

    # Fallback to original Jarvis Pro engine
    return _original_handle(raw)


jp.handle_command = max_handle_command

# Extend visible help
jp.HELP_TEXT += f"""

JARVIS MAX - extra commands for {USER_NAME}

Personal:
  who am I
  what is my name
  how old am I
  introduce me

Weather:
  weather
  weather today
  weather in Colombo
  weather in London
  check weather in Kandy

AI:
  open ChatGPT
  open Claude
  open Gemini
  AI mode
  ask ChatGPT <question>

Facebook / Social:
  open Facebook
  open Facebook notifications
  check Facebook notifications
  open Messenger
  open Meta Business Suite
  open Facebook insights
  open Facebook content
  open Facebook pages
  search Facebook for <topic>
  mute notifications
  unmute notifications
  creator mode

Work / Productivity:
  work mode
  study mode
  open Gmail
  open Calendar
  open Google Drive
  open Docs
  open Sheets
  open LinkedIn
  open GitHub
  open news

Computer:
  system status
  local IP
  set timer for 10 minutes
  set timer for 30 seconds
"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> int:
    start_notification_monitor()

    # Replace the generic startup line in jarvis_pro with a personalized one
    original_speak = jp.speak

    # We cannot suppress all inherited startup speech cleanly without rewriting
    # jarvis_pro, so greet once before entering its normal loop.
    say_personal_greeting()

    return jp.main()


if __name__ == "__main__":
    raise SystemExit(main())
