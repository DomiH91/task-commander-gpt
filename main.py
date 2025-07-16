from fastapi import FastAPI
from fastapi import Depends
import httpx
from core.config import AppConfig
from services.todoist import get_todoist_service, TodoistService
from routers import tasks

config = AppConfig()
app = FastAPI(title=config.app_title)

# Lifespan: erstelle/zerstöre den AsyncClient
@app.on_event("startup")
async def startup_event():
    app.state.todoist_client = httpx.AsyncClient()

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.todoist_client.aclose()

# Dependency override: übergebe den AsyncClient aus state
@app.on_event("startup")
def override_todoist_dep():
    from services.todoist import get_todoist_service
    app.dependency_overrides[get_todoist_service] = lambda config=config: TodoistService(
        client=app.state.todoist_client, config=config
    )

# --- NEU: Init-Menü mit allen Core-Kommandos ---
@app.get("/init_menu", summary="Returns the main Task Commander menu")
def init_menu():
    return {
        "options": [
            "commander_dashboard",         # Komplett-Dashboard
            "prioritize_tasks",            # Nur Top-N priorisierte Tasks
            "plan_tasks",                  # Tasks ohne Termin für Scheduling
            "review_batch",                # Cleanup-Vorschläge reviewen
            "execute_review_response",     # Review-Batch ausführen
            "focus_session",               # Deep-Work Starter
            "label_recommendations",       # Label-Vorschläge anzeigen
            "accept_label_recommendations",# Labels übernehmen
            "complete_task",               # Task als erledigt markieren
            "add_task",                    # Neue Aufgabe anlegen
            "quick_add",                   # Schnelles Add in Inbox
            "get_projects",                # Projektliste abrufen
            "task_diagnostics"             # Aufgaben-Audit
        ]
    }

# binde alle Task-Endpoints
app.include_router(tasks.router)

@app.get("/", summary="Healthcheck")
def healthcheck():
    return {"status": "alive"}