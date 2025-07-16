# utils/project_utils.py

def resolve_project_id_by_name(client, base_url: str, headers: dict, name: str) -> str:
    """
    Holt die Projektliste und gibt die ID zurück, die dem gegebenen Namen entspricht.
    Wirft ValueError, wenn nicht gefunden.
    """
    resp = client.get(f"{base_url}/projects", headers=headers)
    resp.raise_for_status()
    projects = resp.json()
    match = next((p for p in projects if p["name"].lower() == name.lower()), None)
    if not match:
        raise ValueError(f"Projekt '{name}' nicht gefunden")
    return match["id"]