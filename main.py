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
    from fastapi import Depends
    from services.todoist import get_todoist_service
    app.dependency_overrides[get_todoist_service] = lambda config=config: TodoistService(
        client=app.state.todoist_client, config=config
    )

app.include_router(tasks.router)

@app.get("/")
def healthcheck():
    return {"status": "alive"}