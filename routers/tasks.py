# routers/tasks.py

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from core.config import AppConfig

# ── Konfiguration ────────────────────────────────────────────────────────────

config = AppConfig()
BASE_URL = config.todoist_api_url
HEADERS = {
    "Authorization": f"Bearer {config.todoist_token}",
    "Content-Type": "application/json"
}
TIMEOUT = config.todoist_timeout
MY_USER_ID = "53165679"  # ← Deine echte ID aus /me

router = APIRouter()

# ── Initialization Menu ────────────────────────────────────────────────────────

@router.get("/init_menu")
def init_menu():
    return {
        "options": [
            "top3_focus",
            "full_overview",
            "complete_task",
            "add_task",
            "plan_tasks",
            "prioritize_tasks",
            "commander_dashboard"
        ]
    }

# ── Models ────────────────────────────────────────────────────────────────────
class CompleteTaskInput(BaseModel):
    task_id: str
    comment: str = ""

class AddTaskInput(BaseModel):
    content: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    due_string: Optional[str] = None
    duration_minutes: Optional[int] = None

class QuickAddInput(BaseModel):
    content: str

class UpdateTaskInput(BaseModel):
    task_id: str
    content: Optional[str] = None
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    due_string: Optional[str] = None
    priority: Optional[int] = None
    duration: Optional[int] = None
    labels: Optional[List[str]] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/get_tasks")
def get_tasks(limit: int = 50, offset: int = 0):
    resp = requests.get(
        f"{BASE_URL}/tasks?limit={limit}&offset={offset}",
        headers=HEADERS,
        timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Aufgaben")
    return resp.json()


@router.post("/complete_task")
def complete_task(data: CompleteTaskInput):
    resp = requests.post(
        f"{BASE_URL}/tasks/{data.task_id}/close",
        headers=HEADERS,
        timeout=TIMEOUT
    )
    if resp.status_code != 204:
        raise HTTPException(status_code=500, detail="Fehler beim Abschließen der Aufgabe")
    return {"status": "completed", "task_id": data.task_id}


@router.post("/add_task")
def add_task(data: AddTaskInput):
    project_id = data.project_id

    if not project_id and data.project_name:
        pr = requests.get(
            f"{BASE_URL}/projects",
            headers=HEADERS,
            timeout=TIMEOUT
        )
        if pr.status_code != 200:
            raise HTTPException(status_code=500, detail="Fehler beim Laden der Projekte")
        match = next((p for p in pr.json() if p["name"].lower() == data.project_name.lower()), None)
        if not match:
            raise HTTPException(status_code=400, detail=f"Projekt '{data.project_name}' nicht gefunden")
        project_id = match["id"]

    payload = {
        "content": data.content,
        "project_id": project_id,
        "due_string": data.due_string
    }

    resp = requests.post(
        f"{BASE_URL}/tasks",
        headers=HEADERS,
        json=payload,
        timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Anlegen der Aufgabe")
    return resp.json()


@router.post("/quick_add")
def quick_add(data: QuickAddInput):
    pr = requests.get(
        f"{BASE_URL}/projects",
        headers=HEADERS,
        timeout=TIMEOUT
    )
    if pr.status_code != 200:
        raise HTTPException(status_code=500, detail="Projekte konnten nicht geladen werden")

    inbox = next((p for p in pr.json() if p["name"].lower() == "inbox"), None)
    if not inbox:
        raise HTTPException(status_code=500, detail="Inbox-Projekt nicht gefunden")

    resp = requests.post(
        f"{BASE_URL}/tasks",
        headers=HEADERS,
        json={"content": data.content, "project_id": inbox["id"]},
        timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Quick Add")
    return resp.json()


@router.get("/plan_tasks")
def get_tasks_needing_schedule():
    resp = requests.get(
        f"{BASE_URL}/tasks",
        headers=HEADERS,
        timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Aufgaben")

    tasks = resp.json()
    unplanned = [
        {
            "id": t["id"],
            "content": t["content"],
            "project_id": t.get("project_id"),
            "priority": t.get("priority"),
            "created_at": t.get("created_at"),
            "needs_scheduling": True
        }
        for t in tasks if not t.get("due")
    ]
    return {"tasks": unplanned, "total": len(unplanned)}


@router.patch("/update_task")
def update_task(data: UpdateTaskInput):
    payload: dict = {}
    if data.content is not None:
        payload["content"] = data.content
    if data.project_id:
        payload["project_id"] = data.project_id
    elif data.project_name:
        pr = requests.get(
            f"{BASE_URL}/projects",
            headers=HEADERS,
            timeout=TIMEOUT
        )
        if pr.status_code != 200:
            raise HTTPException(status_code=500, detail="Fehler beim Laden der Projekte")
        match = next((p for p in pr.json() if p["name"].lower() == data.project_name.lower()), None)
        if not match:
            raise HTTPException(status_code=400, detail=f"Projekt '{data.project_name}' nicht gefunden")
        payload["project_id"] = match["id"]
    if data.due_string is not None:
        payload["due_string"] = data.due_string
    if data.priority is not None:
        if data.priority not in (1, 2, 3, 4):
            raise HTTPException(status_code=400, detail="Priority muss zwischen 1 und 4 liegen")
        payload["priority"] = data.priority
    if data.labels is not None:
        payload["labels"] = data.labels
    if data.duration is not None:
        payload["duration"] = {"amount": data.duration, "unit": "minute"}

    if not payload:
        raise HTTPException(status_code=400, detail="Keine Felder zum Aktualisieren angegeben")

    resp = requests.patch(
        f"{BASE_URL}/tasks/{data.task_id}",
        headers=HEADERS,
        json=payload,
        timeout=TIMEOUT
    )
    if resp.status_code not in (200, 204):
        raise HTTPException(status_code=500, detail=f"Update fehlgeschlagen ({resp.status_code})")
    return {"status": "updated", "task_id": data.task_id, "changes": payload}

@router.get("/get_projects")
def get_projects():
    resp = requests.get(f"{BASE_URL}/projects", headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return {"projects": resp.json()}


@router.get("/task_diagnostics")
def task_diagnostics():
    resp = requests.get(
        f"{BASE_URL}/tasks",
        headers=HEADERS,
        timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Aufgaben")

    tasks = resp.json()
    issues = []
    for t in tasks:
        if t.get("creator_id") != MY_USER_ID:
            continue
        raw_content = t.get("content", "")
        content = raw_content.lower() if isinstance(raw_content, str) else ""
        prio = t.get("priority", 1)
        due = t.get("due")
        labels = t.get("labels", [])
        task_issues = []
        suggested_label = None

        if not due:
            task_issues.append("missing_due")
        if prio == 1:
            task_issues.append("low_or_missing_priority")
        if not t.get("project_id"):
            task_issues.append("missing_project")
        if not labels:
            task_issues.append("missing_label")
            if any(w in content for w in ["review", "bericht", "analyse", "reflexion", "tracker", "d&o"]):
                suggested_label = "plan"
            elif any(w in content for w in ["abschicken", "abgeben", "fertigstellen", "abschluss", "submit"]):
                suggested_label = "deliver"
            elif prio >= 3 and due:
                suggested_label = "do"
            elif any(w in content for w in ["call", "meeting", "besprechung", "termin", "abstimmung"]):
                suggested_label = "social"
            elif any(w in content for w in ["überweisen", "zahlung", "rechnung", "kosten", "versicherung", "miete"]):
                suggested_label = "admin"
            elif len(content.split()) <= 3:
                suggested_label = "quick"
            else:
                suggested_label = "admin"

        if task_issues:
            issues.append({
                "id": t["id"],
                "content": raw_content,
                "issues": task_issues,
                "suggested_label": suggested_label
            })

    return {
        "diagnostics": issues,
        "summary": {"total_checked": len(tasks), "with_issues": len(issues)},
        "action_tips": [
            "Setze due_string für planungsrelevante Aufgaben.",
            "Heb die Priorität für wichtige Aufgaben auf 3 oder 4 an.",
            "Ordne Aufgaben einem Projekt zu.",
            "Kennzeichne Aufgaben mit sinnvollem Label (z. B. do, plan, admin)"
        ]
    }

# oben im File dürfen SERVICE_URL bzw. BASE_URL weiter existieren, wir brauchen sie hier nicht mehr

@router.get("/cleanup_recommendations")
def cleanup_recommendations():
    # direkt task_diagnostics() aufrufen, statt HTTP-Request
    diag = task_diagnostics()
    diagnostics = diag["diagnostics"]
    recommendations = []

    for d in diagnostics:
        missing = []
        suggested_update = {}
        if "missing_due" in d["issues"]:
            suggested_update["due_string"] = "tomorrow"; missing.append("due")
        if "low_or_missing_priority" in d["issues"]:
            suggested_update["priority"] = 3; missing.append("priority")
        if "missing_label" in d["issues"] and d.get("suggested_label"):
            suggested_update["labels"] = [d["suggested_label"]]; missing.append("label")
        if suggested_update:
            recommendations.append({
                "task_id": d["id"],
                "content": d["content"],
                "missing": missing,
                "suggested_update": suggested_update
            })

    return {
        "suggested_updates": recommendations,
        "summary": {
            "total_analyzed": len(diagnostics),
            "recommendations": len(recommendations)
        },
        "next_action": "Bestätige über /review_batch oder sende direkt an /update_task"
    }


@router.get("/review_batch")
def review_batch(size: int = 5):
    # direkt cleanup_recommendations() aufrufen
    batch = cleanup_recommendations()["suggested_updates"]
    return {
        "review_batch": batch[:size],
        "instruction": (
            "Antwortformat Beispiel:\n"
            "1 akzeptieren\n"
            "2: due 2025-08-04\n"
            "3 skip\n"
            "4: prio 4, labels ['do']\n"
            "5 akzeptieren"
        )
    }

import re

# Stelle sicher, dass UpdateTaskInput oben importiert ist:
# from routers.tasks import UpdateTaskInput, update_task

@router.post("/execute_review_response")
def execute_review_response(data: dict):
    batch = data.get("review_batch", [])
    raw_response = data.get("response", "")
    if not batch or not raw_response:
        raise HTTPException(status_code=400, detail="review_batch und response sind erforderlich")

    executed, skipped, errors = [], [], {}

    for line in raw_response.strip().split("\n"):
        m = re.match(r"^(\d+)(:| )\s*(.*)$", line.strip())
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if not (0 <= idx < len(batch)):
            errors[str(idx+1)] = "Index außerhalb des review_batch"
            continue

        entry       = batch[idx]
        task_id     = entry["task_id"]
        suggestion  = entry["suggested_update"]
        user_input  = m.group(3).strip().lower()

        if user_input.startswith("skip"):
            skipped.append(str(idx+1))
            continue

        # Baue das Payload für update_task
        payload = {"task_id": task_id}
        if user_input.startswith("akzeptieren"):
            payload.update(suggestion)
        else:
            for f in re.split(r",\s*", user_input):
                if f.startswith("prio"):
                    payload["priority"] = int(re.findall(r"\d+", f)[0])
                elif f.startswith("due"):
                    ds = re.findall(r"\d{4}-\d{2}-\d{2}", f)
                    payload["due_string"] = ds[0] if ds else f.replace("due","").strip()
                elif f.startswith("project"):
                    payload["project_name"] = f.split(" ",1)[1].strip()

        # Rufe direkt das interne update_task auf
        try:
            # wandelt payload in das Pydantic‑Model um
            inp = UpdateTaskInput(**payload)
            update_task(inp)
            executed.append({"task_id": task_id, "applied": payload})
        except HTTPException as he:
            errors[str(idx+1)] = f"Update fehlgeschlagen: {he.detail}"
        except Exception as e:
            errors[str(idx+1)] = f"Fehler: {e}"

    return {"executed": executed, "skipped": skipped, "errors": errors}

@router.get("/focus_session")
def focus_session(limit: int = 3):
    try:
        resp = requests.get(f"{BASE_URL}/tasks", headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        tasks = resp.json()

        filtered = []
        for t in tasks:
            # nur offene Tasks mit Fälligkeitsdatum und hoher Priorität
            if t.get("is_completed") or not t.get("due") or t.get("priority", 1) < 3:
                continue

            dur_obj = t.get("duration") or {}
            duration = dur_obj.get("amount", 0)

            # Dauer ≤ 60 Minuten
            if duration > 60:
                continue

            labels = [l.lower() for l in t.get("labels", [])]
            filtered.append({
                "id": t["id"],
                "content": t["content"],
                "due": t["due"],
                "priority": t.get("priority", 1),
                "duration": duration,
                "labels": labels,
                "focus": any(x in labels for x in ["do", "deliver", "deep"])
            })

        # Sortierung: höhere Priorität zuerst, dann Fälligkeitsdatum
        filtered.sort(key=lambda x: (-x["priority"], x["due"]["date"]))

        return {
            "focus_tasks": filtered[:limit],
            "total_found": len(filtered),
            "logic": "Priorität ≥ 3, due vorhanden, Dauer ≤ 60 Min, Fokus-Labels optional"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"focus_session-Fehler: {e}")

@router.get("/label_recommendations")
def label_recommendations():
    resp = requests.get(f"{BASE_URL}/tasks", headers=HEADERS, timeout=TIMEOUT)
    if resp.status_code != 200:
        raise HTTPException(500, "Fehler beim Laden der Aufgaben von Todoist")

    suggestions = []
    for t in resp.json():
        if t.get("labels"):
            continue

        content = t.get("content", "").lower()
        prio    = t.get("priority", 1)
        due     = t.get("due")

        if any(w in content for w in ["review", "plan", "entwurf", "konzept", "strategie"]):
            lbl = "plan"
        elif any(w in content for w in ["abschicken", "finalisieren", "abgeben", "fertigstellen"]):
            lbl = "deliver"
        elif prio >= 3 and due:
            lbl = "do"
        elif any(w in content for w in ["call", "meeting", "besprechen", "termin"]):
            lbl = "social"
        elif len(content.split()) <= 3:
            lbl = "quick"
        else:
            lbl = "admin"

        suggestions.append({
            "task_id": t["id"],
            "content": t["content"],
            "suggested_label": lbl
        })

    return {
        "recommendations": suggestions,
        "total_suggested": len(suggestions),
        "info": "Nur Tasks ohne Label werden berücksichtigt"
    }


# —————————————————————————————————————————————
# 2) Accept Label Recommendations
# —————————————————————————————————————————————

class AcceptLabelsInput(BaseModel):
    accept: List[str]  # Liste von task_id

@router.post("/accept_label_recommendations")
def accept_label_recommendations(data: AcceptLabelsInput):
    # 1) Hole die Vorschläge direkt aus der Funktion
    rec = label_recommendations()
    suggestions = rec["recommendations"]

    # 2) Lade alle Label-IDs von Todoist
    label_resp = requests.get(f"{BASE_URL}/labels", headers=HEADERS, timeout=TIMEOUT)
    if label_resp.status_code != 200:
        raise HTTPException(500, "Labels konnten nicht geladen werden")
    label_map = {l["name"].strip().lower(): l["id"] for l in label_resp.json()}

    # 3) Bestimme, welche IDs akzeptiert wurden
    accepted_ids = set(data.accept)

    executed, skipped, errors = [], [], {}

    # 4) Für jede Empfehlung
    for s in suggestions:
        tid = s["task_id"]
        if tid not in accepted_ids:
            skipped.append(tid)
            continue

        lbl = s["suggested_label"].strip().lower()
        lid = label_map.get(lbl)
        if not lid:
            errors[tid] = f"Label '{lbl}' nicht gefunden"
            continue

        payload = {"task_id": tid, "labels": [lid]}

        # 5) Update entweder lokal oder direkt gegen Todoist
        try:
            # Variante A: lokale Funktion (wenn Du update_task importiert hast)
            # update_task(UpdateTaskInput(task_id=tid, labels=[lid]))
            #
            # Variante B: direkte API
            r = requests.post(
                f"{BASE_URL}/tasks/{tid}",
                headers=HEADERS,
                json=payload,
                timeout=TIMEOUT
            )
            if r.status_code not in (200, 204):
                errors[tid] = f"Todoist-Update fehlgeschlagen ({r.status_code})"
            else:
                executed.append({"task_id": tid, "label": lbl})
        except Exception as e:
            errors[tid] = str(e)

    return {
        "executed": executed,
        "skipped": skipped,
        "errors": errors,
        "summary": {
            "total_accepted": len(executed),
            "total_skipped": len(skipped),
            "total_failed": len(errors)
        }
    }

@router.get("/me")
def get_me():
    return {"user_id": MY_USER_ID}


@router.get("/prioritized_tasks")
def prioritized_tasks(limit: int = 5):
    resp = requests.get(
        f"{BASE_URL}/tasks",
        headers=HEADERS,
        timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Aufgaben")

    now = datetime.utcnow()
    today = now.date()
    tasks = resp.json()
    scored = []
    for t in tasks:
        if t.get("is_completed") or t.get("creator_id") != MY_USER_ID:
            continue
        content = t.get("content", "").lower()
        labels = [l.lower() for l in t.get("labels", [])]
        prio = t.get("priority", 1)
        due = t.get("due")
        wc = len(content.split())
        score = 0
        reason = []
        is_today = False

        if any(l in labels for l in ["do", "deliver"]):
            score += 3; reason.append("impact")
        if due and "date" in due:
            try:
                dd = datetime.fromisoformat(due["date"]).date()
                if dd == today:
                    score += 3; reason.append("due today"); is_today = True
                elif dd <= today + timedelta(days=3):
                    score += 2; reason.append("due < 3d")
            except:
                reason.append("due parse error")
        else:
            reason.append("no due")
        if not is_today and any(x in content for x in ["staubsaugen","fenster","pool","kinder","privat","putzen"]):
            score -= 2; reason.append("private")
        if prio == 4:
            score += 2; reason.append("prio 4")
        if wc <= 3:
            score += 1; reason.append("quick")

        scored.append({
            "id": t["id"],
            "content": t.get("content"),
            "score": score,
            "priority": prio,
            "due": due,
            "labels": labels,
            "reason": reason
        })

    scored.sort(key=lambda x: -x["score"])
    return {
        "prioritized": scored[:limit],
        "total_eligible": len(scored),
        "scoring_logic": "impact +3, due today +3, due<3d +2, prio 4 +2, quick +1, private -2 (wenn nicht today)"
    }

from fastapi import HTTPException
from datetime import datetime

@router.get("/commander_dashboard")
def commander_dashboard(limit: int = 5):
    try:
        # direkt auf unsere internen Funktionen zugreifen
        top_tasks    = prioritized_tasks(limit)["prioritized"]
        review_needs = review_batch(limit)["review_batch"]
        unplanned    = get_tasks_needing_schedule()["tasks"]

        return {
            "date": datetime.utcnow().date().isoformat(),
            "top_tasks": top_tasks,
            "review_needs": review_needs,
            "unplanned_tasks": unplanned,
            "slot_suggestions": {
                "deep_work":   [t["content"] for t in top_tasks if "plan" in t.get("labels", []) or t["score"] >= 6],
                "quick_wins":  [t["content"] for t in top_tasks if "quick" in t.get("reason", []) or t["score"] <= 4],
                "today_focus": [t["content"] for t in top_tasks if "due today" in t.get("reason", [])]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Commander-Dashboard Fehler: {e}")