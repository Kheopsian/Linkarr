# backend/main.py
import os
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from scanner import analyze_hardlinks, analyze_hardlinks_by_folder, count_files
from config_manager import load_config, save_config

# Constante pour la base de navigation (pour la sécurité)
# Dans Docker, ce sera le point de montage de vos données, ex: /data
BROWSE_BASE_PATH = os.path.abspath(os.getenv("BROWSE_BASE_PATH", "."))

app = FastAPI()

# --- AJOUTS POUR CORS ---
origins = [
    "http://localhost:5173", # L'adresse de notre frontend de dev
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dictionnaire pour garder en mémoire l'état des scans
scan_tasks = {}

# --- Modèles Pydantic pour la validation ---
class TabConfig(BaseModel):
    id: str
    name: str
    scan_mode: str = "file"  # "file" ou "folder"
    check_column: str = "a"  # "a", "b" ou "both" (utilisé seulement si scan_mode = "folder")
    paths_a: List[str]
    paths_b: List[str]
    name_a: str = "Downloads"
    name_b: str = "Media"

class AppConfig(BaseModel):
    tabs: List[TabConfig]

# --- Endpoints pour la Configuration ---

@app.get("/api/config", response_model=AppConfig)
def get_config():
    """Récupère la configuration actuelle."""
    return load_config()

@app.post("/api/config")
def update_config(config: AppConfig):
    """Met à jour et sauvegarde la configuration."""
    save_config(config.dict())
    return {"message": "Configuration sauvegardée avec succès."}

# --- Endpoint pour l'Explorateur de fichiers ---

@app.get("/api/browse")
def browse_path(path: str = '/'):
    """
    Liste le contenu d'un répertoire.
    Pour la sécurité, ne permet de naviguer que dans BROWSE_BASE_PATH.
    """
    if path == '/':
        # Si le chemin est la racine, on le redirige vers notre base
        target_path = BROWSE_BASE_PATH
    else:
        target_path = os.path.abspath(os.path.join(BROWSE_BASE_PATH, path))

    # !! SÉCURITÉ !! : Vérifie que le chemin demandé est bien un sous-dossier de notre base
    if not target_path.startswith(BROWSE_BASE_PATH):
        raise HTTPException(status_code=403, detail="Accès non autorisé.")

    try:
        if not os.path.isdir(target_path):
            raise HTTPException(status_code=400, detail="Le chemin n'est pas un répertoire.")

        content = os.listdir(target_path)
        results = []
        for item in content:
            item_path = os.path.join(target_path, item)
            # On retourne un chemin relatif à la base pour le frontend
            relative_item_path = os.path.relpath(item_path, BROWSE_BASE_PATH)
            if relative_item_path == '.':
                relative_item_path = '/'

            results.append({
                "name": item,
                "path": relative_item_path,
                "is_dir": os.path.isdir(item_path)
            })
        return sorted(results, key=lambda x: (not x['is_dir'], x['name'].lower()))

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Chemin non trouvé.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Endpoint pour le Scan (mis à jour) ---

def perform_scan_task(task_id: str, paths_a: list, paths_b: list):
    """Effectue le scan de fichiers et met à jour l'état de la tâche."""
    results, errors = analyze_hardlinks(paths_a, paths_b, task_id, scan_tasks)
    scan_tasks[task_id]["status"] = "completed"
    scan_tasks[task_id]["results"] = results
    scan_tasks[task_id]["errors"] = errors

@app.post("/api/scan/{tab_id}")
def run_scan(tab_id: str, background_tasks: BackgroundTasks):
    """
    Lance une analyse sur un onglet en arrière-plan.
    """
    config = load_config()
    tab = next((t for t in config.get("tabs", []) if t.get("id") == tab_id), None)

    if not tab:
        raise HTTPException(status_code=404, detail=f"L'onglet '{tab_id}' n'existe pas.")
    
    paths_a = tab.get("paths_a", [])
    paths_b = tab.get("paths_b", [])
    
    if not paths_a or not paths_b:
        raise HTTPException(status_code=400, detail=f"Aucun chemin configuré pour l'onglet '{tab_id}'.")

    task_id = str(uuid.uuid4())
    total_files = count_files(paths_a) + count_files(paths_b)
    
    scan_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": total_files,
        "current_file": "",
        "results": None,
        "errors": None
    }

    background_tasks.add_task(perform_scan_task, task_id, paths_a, paths_b)
    
    return {"task_id": task_id}


# --- Endpoint pour le Scan par dossier (nouveau) ---

def perform_scan_folder_task(task_id: str, paths_a: list, paths_b: list, check_column: str):
    """Effectue le scan de dossiers et met à jour l'état de la tâche."""
    results, errors = analyze_hardlinks_by_folder(paths_a, paths_b, check_column, task_id, scan_tasks)
    scan_tasks[task_id]["status"] = "completed"
    scan_tasks[task_id]["results"] = results
    scan_tasks[task_id]["errors"] = errors

@app.post("/api/scan-folder/{tab_id}")
def run_scan_folder(tab_id: str, background_tasks: BackgroundTasks):
    config = load_config()
    tab = next((t for t in config.get("tabs", []) if t.get("id") == tab_id), None)
    
    if not tab:
        raise HTTPException(status_code=404, detail=f"L'onglet '{tab_id}' n'existe pas.")

    paths_a = tab.get("paths_a", [])
    paths_b = tab.get("paths_b", [])
    check_column = tab.get("check_column", "a")

    if not paths_a or not paths_b:
        raise HTTPException(status_code=400, detail=f"Aucun chemin configuré pour l'onglet '{tab_id}'.")

    if check_column not in ["a", "b", "both"]:
        raise HTTPException(status_code=400, detail="Le paramètre check_column doit être 'a', 'b' ou 'both'.")

    task_id = str(uuid.uuid4())
    total_files = count_files(paths_a) + count_files(paths_b)
    
    scan_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": total_files,
        "current_file": "",
        "results": None,
        "errors": None
    }

    background_tasks.add_task(perform_scan_folder_task, task_id, paths_a, paths_b, check_column)
    
    return {"task_id": task_id}

@app.get("/api/scan/status/{task_id}")
def get_scan_status(task_id: str):
    """Récupère l'état d'une tâche de scan."""
    task = scan_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche de scan non trouvée.")
    return task