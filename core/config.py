# core/config.py

from pydantic_settings import BaseSettings
from pydantic import Field

class AppConfig(BaseSettings):
    # Todoist API
    todoist_token: str = Field(..., env="TODOIST_TOKEN")
    todoist_api_url: str = Field(
        "https://api.todoist.com/rest/v2", env="TODOIST_API_URL"
    )
    todoist_timeout: int = Field(5, env="TODOIST_TIMEOUT_SEC")

    # Eigene App
    app_title: str = Field("Task Commander GPT", env="APP_TITLE")

    # Basis‑URL für interne Aufrufe (lokal oder deployed)
    service_base_url: str = Field(
        "http://127.0.0.1:8000", env="SERVICE_BASE_URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"