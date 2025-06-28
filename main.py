# Force redeploy marker
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pydantic.functional_validators import model_validator
import requests

app = FastAPI()

TODOIST_TOKEN = os.getenv("TODOIST_TOKEN", "…fallback token…")

@app.get("/")
def root():
    return {"status": "alive"}

class CompleteTaskInput(BaseModel):
    task_id: str
    comment: str = ""

class AddTaskInput(BaseModel):
    content: str
    due_string: str
    project_id: str | None = None
    project_name: str | None = None
    duration_minutes: int | None = None

    @model_validator(mode="after")
    def check_project_identifier(cls, model):
        if not (model.project_id or model.project_name):
            raise ValueError("Either project_id or project_name must be provided")
        return model

@app.get("/init_menu")
def init_menu():
    return {"options": ["top3_focus", "full_overview", "complete_task", "add_task", "get_projects"]}

@app.get("/get_tasks")
def get_tasks():
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = requests.get("https://api.todoist.com/rest/v2/tasks", headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")
    tasks = resp.json()
    enriched = []
    for t in tasks:
        tags = []
        if t.get("due"):
            tags.append("has_due")
        if "review" in t["content"].lower():
            tags.append("DeepWork")
        due_info = t.get("due") or {}
        enriched.append({
            "id": t["id"],
            "content": t["content"],
            "due": due_info.get("date"),
            "duration_minutes": None,
            "tags": tags
        })
    return {"tasks": enriched}

@app.get("/get_projects")
def get_projects():
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch projects")
    projs = resp.json()
    return {"projects": [{"id": p["id"], "name": p["name"]} for p in projs]}

@app.post("/complete_task")
def complete_task(data: CompleteTaskInput):
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}"}
    resp = requests.post(
        f"https://api.todoist.com/rest/v2/tasks/{data.task_id}/close",
        headers=headers
    )
    if resp.status_code != 204:
        raise HTTPException(status_code=500, detail="Failed to close task")
    return {"status": "completed", "task_id": data.task_id}

@app.post("/add_task")
def add_task(data: AddTaskInput):
    headers = {"Authorization": f"Bearer {TODOIST_TOKEN}", "Content-Type": "application/json"}

    # resolve project_id by name
    if not data.project_id and data.project_name:
        proj_resp = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers)
        proj_resp.raise_for_status()
        match = next((p for p in proj_resp.json() if p["name"].lower() == data.project_name.lower()), None)
        if not match:
            raise HTTPException(status_code=400, detail=f"Project '{data.project_name}' not found")
        project_id = match["id"]
    else:
        project_id = data.project_id

    payload = {
        "content": data.content,
        "due_string": data.due_string,
        "project_id": project_id,
        "duration_minutes": data.duration_minutes
    }
    resp = requests.post("https://api.todoist.com/rest/v2/tasks", json=payload, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to create task")
    return resp.json()