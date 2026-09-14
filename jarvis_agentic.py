#!/usr/bin/env python3
"""JARVIS AGENTIC - manager + memory + tasks + approvals + workflows.
Requires jarvis_pro.py and jarvis_max.py in the same folder.
"""
from __future__ import annotations
import json, os, re, threading, time, urllib.parse, urllib.request, webbrowser
from datetime import datetime, timedelta
from pathlib import Path
import jarvis_max as jm
import jarvis_pro as jp

BASE = Path(__file__).resolve().parent
DATA = BASE / "jarvis_data"
DATA.mkdir(exist_ok=True)
MEMORY = DATA / "memory.json"
TASKS = DATA / "tasks.json"
APPROVALS = DATA / "approvals.json"
ACTIVITY = DATA / "activity.jsonl"
USER = os.getenv("JARVIS_USER_NAME", "Chirantha Bimsara")
AGE = int(os.getenv("JARVIS_USER_AGE", "24"))


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def log(kind, detail, status="ok"):
    row = {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind, "detail": detail, "status": status}
    with ACTIVITY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def remember(text):
    items = load(MEMORY, [])
    items.append({"id": int(time.time()*1000), "created": datetime.now().isoformat(timespec="seconds"), "text": text})
    save(MEMORY, items); log("memory", f"remembered: {text}")


def forget(term):
    items = load(MEMORY, []); before = len(items)
    items = [x for x in items if term.lower() not in x.get("text", "").lower()]
    save(MEMORY, items); return before-len(items)


def add_task(title, due=None, category="general"):
    items = load(TASKS, [])
    items.append({"id": int(time.time()*1000), "title": title, "created": datetime.now().isoformat(timespec="seconds"), "due": due, "category": category, "status": "open", "notified": False})
    save(TASKS, items); log("task", f"added: {title}")


def open_tasks():
    return [x for x in load(TASKS, []) if x.get("status") == "open"]


def complete_task(term):
    items = load(TASKS, [])
    for x in items:
        if x.get("status") == "open" and term.lower() in x.get("title", "").lower():
            x["status"] = "done"; x["completed"] = datetime.now().isoformat(timespec="seconds")
            save(TASKS, items); log("task", f"completed: {x['title']}"); return True
    return False


def parse_due(text):
    m = re.search(r"in\s+(\d+)\s+(minute|minutes|hour|hours|day|days)", text)
    if not m: return None
    n = int(m.group(1)); unit = m.group(2)
    delta = timedelta(minutes=n) if "minute" in unit else timedelta(hours=n) if "hour" in unit else timedelta(days=n)
    return (datetime.now()+delta).isoformat(timespec="minutes")


def queue_approval(kind, description, payload=None):
    items = load(APPROVALS, [])
    items.append({"id": int(time.time()*1000), "type": kind, "description": description, "payload": payload or {}, "status": "pending", "created": datetime.now().isoformat(timespec="seconds")})
    save(APPROVALS, items); log("approval", description, "pending")


def pending():
    return [x for x in load(APPROVALS, []) if x.get("status") == "pending"]


def resolve(approve=True):
    items = load(APPROVALS, [])
    for x in items:
        if x.get("status") == "pending":
            x["status"] = "approved" if approve else "rejected"; x["resolved"] = datetime.now().isoformat(timespec="seconds")
            save(APPROVALS, items); log("approval", x["description"], x["status"]); return x
    return None


def morning_brief():
    tasks = open_tasks(); approvals = pending()
    msg = f"Good morning, {USER}. You have {len(tasks)} open tasks and {len(approvals)} pending approvals."
    if tasks: msg += " Top priorities: " + "; ".join(x["title"] for x in tasks[:3]) + "."
    jp.speak(msg)
    for url in ("https://mail.google.com", "https://calendar.google.com", "https://business.facebook.com/latest/home", "https://chatgpt.com"):
        webbrowser.open(url)
    log("brief", "morning brief")


def creator_workflow(topic):
    topic = topic.strip() or "today's content"
    for title in (
        f"Research content idea: {topic}",
        f"Draft hook and caption: {topic}",
        f"Prepare or edit media: {topic}",
        f"Review analytics after posting: {topic}",
    ):
        add_task(title, category="creator")
    queue_approval("social_publish", f"Publish approved content about: {topic}", {"topic": topic})
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(topic + " trends"))
    webbrowser.open("https://business.facebook.com/latest/content")
    webbrowser.open("https://chatgpt.com")
    jp.speak(f"Creator workflow prepared for {topic}. Publishing is waiting for your approval.")


def research_workflow(topic):
    add_task(f"Research: {topic}", category="research")
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(topic))
    webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(topic))
    webbrowser.open("https://chatgpt.com")
    jp.speak(f"Research workspace opened for {topic}.")


def social_dashboard():
    for url in ("https://www.facebook.com/notifications", "https://www.messenger.com", "https://business.facebook.com/latest/home", "https://business.facebook.com/latest/insights"):
        webbrowser.open(url)
    jp.speak("Your social dashboard is open.")


def ask_ollama(prompt):
    if os.getenv("JARVIS_USE_OLLAMA", "false").lower() != "true": return None
    model = os.getenv("JARVIS_OLLAMA_MODEL", "llama3.2:3b")
    try:
        body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body, headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read().decode()).get("response", "").strip()
    except Exception as e:
        jp.log.warning("Ollama unavailable: %s", e); return None


def task_watcher():
    while True:
        try:
            items = load(TASKS, []); changed = False; now = datetime.now()
            for x in items:
                if x.get("status") != "open" or x.get("notified") or not x.get("due"): continue
                try: due = datetime.fromisoformat(x["due"])
                except Exception: continue
                if due <= now:
                    x["notified"] = True; changed = True; jp.speak(f"{USER}, task due: {x['title']}")
            if changed: save(TASKS, items)
        except Exception as e: jp.log.warning("Task watcher error: %s", e)
        time.sleep(20)

threading.Thread(target=task_watcher, daemon=True).start()
_original = jm.max_handle_command


def handle(raw):
    text = jm.normalized(raw)
    if text in ("status", "agent status", "jarvis status", "manager status", "system status"):
        jp.speak(f"Agent system online. {len(open_tasks())} open tasks, {len(pending())} pending approvals, and {len(load(MEMORY, []))} stored memories."); return "continue"
    m = re.match(r"(?:remember that|remember)\s+(.+)", text)
    if m: remember(m.group(1)); jp.speak("I stored that in persistent memory."); return "continue"
    m = re.match(r"(?:forget|forget about)\s+(.+)", text)
    if m: jp.speak(f"I removed {forget(m.group(1))} matching memories."); return "continue"
    if text in ("what do you remember", "show memory", "recent memories"):
        items = load(MEMORY, [])[-5:]; jp.speak("Recent memory: " + "; ".join(x["text"] for x in items) if items else "I do not have saved memory yet."); return "continue"
    m = re.match(r"(?:add task|create task|task)\s+(.+)", text)
    if m: body=m.group(1); add_task(body, parse_due(body)); jp.speak("Task added."); return "continue"
    if text in ("list tasks", "show tasks", "what are my tasks"):
        items=open_tasks(); jp.speak("Your tasks are: " + "; ".join(x["title"] for x in items[:8]) if items else "You have no open tasks."); return "continue"
    m = re.match(r"(?:complete task|finish task|mark task complete)\s+(.+)", text)
    if m: jp.speak("Task completed." if complete_task(m.group(1)) else "I could not find that task."); return "continue"
    if text in ("pending approvals", "show approvals", "what needs approval"):
        items=pending(); jp.speak(f"You have {len(items)} pending approvals. Next: {items[0]['description']}" if items else "There are no pending approvals."); return "continue"
    if text in ("approve", "approve action", "approve next"):
        x=resolve(True); jp.speak(f"Approved: {x['description']}. Cleared for the future publishing connector." if x else "There is nothing waiting for approval."); return "continue"
    if text in ("reject", "reject action", "reject next"):
        x=resolve(False); jp.speak(f"Rejected: {x['description']}." if x else "There is nothing waiting for approval."); return "continue"
    if text in ("morning brief", "daily brief", "brief me", "start my day"): morning_brief(); return "continue"
    m = re.match(r"(?:creator workflow|create content workflow|content workflow)(?: for)?\s*(.*)", text)
    if m: creator_workflow(m.group(1)); return "continue"
    m = re.match(r"(?:research workflow|research mode)(?: for)?\s+(.+)", text)
    if m: research_workflow(m.group(1)); return "continue"
    if text in ("social dashboard", "open social dashboard"): social_dashboard(); return "continue"
    m = re.match(r"(?:queue post|prepare post|social post)\s+(.+)", raw, re.I)
    if m: queue_approval("social_publish", f"Publish social post: {m.group(1)[:100]}", {"text":m.group(1)}); jp.speak("The post is prepared and waiting for your approval."); return "continue"
    if text in ("recent activity", "activity log", "what did you do"):
        if not ACTIVITY.exists(): jp.speak("No activity has been logged yet."); return "continue"
        events=[]
        for line in ACTIVITY.read_text(encoding="utf-8").splitlines()[-5:]:
            try: events.append(json.loads(line).get("detail","activity"))
            except Exception: pass
        jp.speak("Recent activity: " + "; ".join(events)); return "continue"
    m = re.match(r"(?:think about|analyze|brainstorm)\s+(.+)", raw, re.I)
    if m:
        answer=ask_ollama(f"You are Jarvis for {USER}, age {AGE}. Request: {m.group(1)}")
        if answer: jp.speak(answer[:900])
        else: jp.speak("Local AI is not enabled. Opening ChatGPT."); webbrowser.open("https://chatgpt.com/?q="+urllib.parse.quote_plus(m.group(1)))
        return "continue"
    return _original(raw)

jm.max_handle_command = handle
jp.handle_command = handle
jp.HELP_TEXT += """

AGENTIC COMMANDS
  agent status
  remember that <fact>
  what do you remember
  forget <topic>
  add task <task>
  add task <task> in 30 minutes
  list tasks
  complete task <name>
  morning brief
  creator workflow for <topic>
  research workflow for <topic>
  social dashboard
  queue post <caption/text>
  pending approvals
  approve next
  reject next
  recent activity
  think about <question>
  analyze <topic>
  brainstorm <topic>
"""


def main():
    jp.log.info("JARVIS AGENTIC layer loaded")
    jp.speak(f"Agentic systems online for {USER}. Manager, memory, tasks, approvals, and workflows are ready.")
    return jm.main()

if __name__ == "__main__":
    raise SystemExit(main())
