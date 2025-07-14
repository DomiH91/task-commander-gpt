# Force redeploy marker
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic.functional_validators import model_validator
from dotenv import load_dotenv
import requests

# env laden
load_dotenv()

app = FastAPI()

TODOIST_TOKEN = os.getenv("TODOIST_TOKEN")
if not TODOIST_TOKEN:
    raise RuntimeError("Missing TODOIST_TOKEN in environment")

HEADERS = {"Authorization": f"Bearer {TODOIST_TOKEN}", "Content-Type": "application/json"}

# Schemas
class CompleteTaskInput(BaseModel):
    task_id: str
    comment: str = ""

class AddTaskInput(BaseModel):
    content: str
    project_id: str | None = None
    project_name: str | None = None
    due_string: str | None = None
    duration_minutes: int | None = None

    @model_validator(mode="after")
    def validate_input(cls, model):
        if not (model.project_id or model.project_name):
            raise ValueError("Either project_id or project_name must be provided")
        if not model.due_string and model.duration_minutes is None:
            raise ValueError("If no due date, duration_minutes must be provided")
        return model

class QuickAddInput(BaseModel):
    content: str

class UpdateTaskInput(BaseModel):
    task_id: str
    content: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    due_string: str | None = None
    duration_minutes: int | None = None

# Endpoints
@app.get("/")
def root():
    return {"status": "alive"}

@app.get("/init_menu")
def init_menu():
    return {
        "options": [
            "top3_focus",
            "full_overview",
            "complete_task",
            "add_task",
            "quick_add",
            "plan_task",
            "update_task",
            "get_projects"
        ]
    }

@app.get("/get_tasks")
def get_tasks(limit: int = 50, offset: int = 0):
    resp = requests.get(
        f"https://api.todoist.com/rest/v2/tasks?limit={limit}&offset={offset}",
        headers={"Authorization": f"Bearer {TODOIST_TOKEN}"},
        timeout=5
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Aufgaben")
    tasks = resp.json()
    enriched = []
    for t in tasks:
        tags = []
        if t.get("due"):
            tags.append("has_due")
        if "review" in t["content"].lower():
            tags.append("DeepWork")
        enriched.append({
            "id": t["id"],
            "content": t["content"],
            "due": t["due"]["date"] if t.get("due") else None,
            "duration_minutes": None,
            "tags": tags,
            "needs_scheduling": not t.get("due")  
        })
    return {"tasks": enriched, "limit": limit, "offset": offset}

@app.post("/complete_task")
def complete_task(data: CompleteTaskInput):
    resp = requests.post(
        f"https://api.todoist.com/rest/v2/tasks/{data.task_id}/close",
        headers={"Authorization": f"Bearer {TODOIST_TOKEN}"},
        timeout=5
    )
    if resp.status_code != 204:
        raise HTTPException(status_code=500, detail="Fehler beim Abschließen")
    return {"status": "completed", "task_id": data.task_id}

@app.post("/add_task")
def add_task(data: AddTaskInput):
    headers = HEADERS.copy()
    project_id = data.project_id
    if not project_id and data.project_name:
        pr = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers, timeout=5)
        pr.raise_for_status()
        match = next((p for p in pr.json() if p["name"].lower() == data.project_name.lower()), None)
        if not match:
            raise HTTPException(status_code=400, detail=f"Projekt '{data.project_name}' nicht gefunden")
        project_id = match["id"]
    payload = {
        "content": data.content,
        "project_id": project_id,
        "due_string": data.due_string,
        "duration_minutes": data.duration_minutes,
    }
    resp = requests.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers, timeout=5)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Anlegen")
    return resp.json()

@app.post("/quick_add")
def quick_add(data: QuickAddInput):
    headers = HEADERS.copy()
    # Inbox project ID holen
    pr = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers, timeout=5)
    pr.raise_for_status()
    inbox = next((p for p in pr.json() if p["name"].lower() == "inbox"), None)
    project_id = inbox["id"] if inbox else None
    payload = {"content": data.content, "project_id": project_id}
    resp = requests.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers, timeout=5)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Quick Add")
    return resp.json()

@app.patch("/update_task")
def update_task(data: UpdateTaskInput):
    headers = HEADERS.copy()
    payload = {}
    for field in ("content", "project_id", "due_string", "duration_minutes"):
        val = getattr(data, field)
        if val is not None:
            if field == "project_id" and not val and data.project_name:
                pr = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers, timeout=5)
                pr.raise_for_status()
                m = next((p for p in pr.json() if p["name"].lower() == data.project_name.lower()), None)
                if not m:
                    raise HTTPException(status_code=400, detail=f"Projekt '{data.project_name}' nicht gefunden")
                payload["project_id"] = m["id"]
            else:
                payload[field] = val
    resp = requests.post(f"https://api.todoist.com/rest/v2/tasks/{data.task_id}", json=payload, headers=headers, timeout=5)
    if resp.status_code not in (200,204):
        raise HTTPException(status_code=500, detail="Fehler beim Aktualisieren")
    return {"status": "updated", **payload}

@app.get("/plan_task")
def get_tasks_needing_schedule():
    resp = requests.get(
        "https://api.todoist.com/rest/v2/tasks",
        headers=HEADERS,
        timeout=5
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Fehler beim Laden der Aufgaben")

    tasks = resp.json()
    filtered = []
    for t in tasks:
        if not t.get("due"):
            filtered.append({
                "id": t["id"],
                "content": t["content"],
                "due": None,
                "duration_minutes": None,
                "tags": [],
                "needs_scheduling": True
            })
    return {"tasks": filtered}