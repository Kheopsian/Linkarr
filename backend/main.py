# backend/main.py
import os
import uuid
import logging
import sys
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List
from fastapi.middleware.cors import CORSMiddleware
from scanner import analyze_hardlinks, analyze_hardlinks_by_folder, count_files
from config_manager import load_config, save_config

# Configuration du logging pour Docker
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log du démarrage de l'application
logger.info("🚀 Démarrage de l'application Linkarr Backend")

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

# Configuration des timeouts
TASK_TIMEOUT_SECONDS = 3600  # 1 heure maximum par scan
TASK_CLEANUP_INTERVAL = 300   # Nettoyage toutes les 5 minutes

import time
from datetime import datetime, timedelta

def cleanup_old_tasks():
    """Nettoie les tâches anciennes ou expirées."""
    current_time = time.time()
    tasks_to_remove = []
    
    for task_id, task_data in scan_tasks.items():
        # Vérifier si la tâche a un timestamp de création
        if 'created_at' not in task_data:
            task_data['created_at'] = current_time
            continue
            
        # Supprimer les tâches qui sont terminées depuis plus de 30 minutes
        if task_data.get('status') in ['completed', 'error']:
            if current_time - task_data.get('completed_at', task_data['created_at']) > 1800:  # 30 minutes
                tasks_to_remove.append(task_id)
                
        # Supprimer les tâches qui tournent depuis plus de TASK_TIMEOUT_SECONDS
        elif task_data.get('status') == 'running':
            if current_time - task_data['created_at'] > TASK_TIMEOUT_SECONDS:
                task_data['status'] = 'timeout'
                task_data['error'] = 'Timeout: Le scan a dépassé la limite de temps autorisée'
                task_data['completed_at'] = current_time
                logger.warning(f"⏰ Timeout de la tâche {task_id} après {TASK_TIMEOUT_SECONDS} secondes")
    
    for task_id in tasks_to_remove:
        logger.info(f"🗑️ Suppression de la tâche expirée: {task_id}")
        del scan_tasks[task_id]
    
    if tasks_to_remove:
        logger.info(f"🧹 Nettoyage terminé: {len(tasks_to_remove)} tâche(s) supprimée(s)")

import threading
import atexit

# Démarrer le nettoyage automatique des tâches
def start_cleanup_timer():
    cleanup_old_tasks()
    timer = threading.Timer(TASK_CLEANUP_INTERVAL, start_cleanup_timer)
    timer.daemon = True
    timer.start()
    return timer

cleanup_timer = start_cleanup_timer()
atexit.register(cleanup_timer.cancel)

logger.info(f"🧹 Système de nettoyage automatique des tâches démarré (intervalle: {TASK_CLEANUP_INTERVAL}s)")

# --- Modèles Pydantic pour la validation ---
class TabConfig(BaseModel):
    id: str
    name: str
    scan_mode: str = "file"  # "file" ou "folder"
    check_column: str = "a"  # "a", "b" ou "both" (utilisé seulement si scan_mode = "folder")
    max_depth: int = -1  # Profondeur maximale de scan (-1 = illimitée)
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

def perform_scan_task(task_id: str, paths_a: list, paths_b: list, max_depth: int = -1):
    """Effectue le scan de fichiers et met à jour l'état de la tâche."""
    logger.info(f"🔍 Début du scan pour la tâche {task_id}")
    logger.info(f"📁 Chemins A: {paths_a}")
    logger.info(f"📁 Chemins B: {paths_b}")
    logger.info(f"🔢 Profondeur maximale: {max_depth if max_depth >= 0 else 'illimitée'}")
    
    try:
        results, errors = analyze_hardlinks(paths_a, paths_b, task_id, scan_tasks, max_depth)
        scan_tasks[task_id]["status"] = "completed"
        scan_tasks[task_id]["results"] = results
        scan_tasks[task_id]["errors"] = errors
        scan_tasks[task_id]["completed_at"] = time.time()
        
        logger.info(f"✅ Scan terminé pour la tâche {task_id}")
        logger.info(f"📊 Résultats: {len(results.get('synced', []))} synchronisés, {len(results.get('orphans_a', []))} orphelins A, {len(results.get('orphans_b', []))} orphelins B")
        if errors:
            logger.warning(f"⚠️ {len(errors)} erreurs rencontrées pendant le scan")
    except Exception as e:
        logger.error(f"❌ Erreur lors du scan de la tâche {task_id}: {str(e)}")
        scan_tasks[task_id]["status"] = "error"
        scan_tasks[task_id]["error"] = str(e)
        scan_tasks[task_id]["completed_at"] = time.time()

@app.post("/api/scan/{tab_id}")
def run_scan(tab_id: str, background_tasks: BackgroundTasks):
    """
    Lance une analyse sur un onglet en arrière-plan.
    """
    logger.info(f"🚀 Demande de scan pour l'onglet: {tab_id}")
    
    config = load_config()
    tab = next((t for t in config.get("tabs", []) if t.get("id") == tab_id), None)

    if not tab:
        logger.error(f"❌ Onglet non trouvé: {tab_id}")
        raise HTTPException(status_code=404, detail=f"L'onglet '{tab_id}' n'existe pas.")
    
    paths_a = tab.get("paths_a", [])
    paths_b = tab.get("paths_b", [])
    max_depth = tab.get("max_depth", -1)
    
    if not paths_a or not paths_b:
        logger.error(f"❌ Aucun chemin configuré pour l'onglet {tab_id}")
        raise HTTPException(status_code=400, detail=f"Aucun chemin configuré pour l'onglet '{tab_id}'.")

    task_id = str(uuid.uuid4())
    logger.info(f"📝 Comptage des fichiers pour la tâche {task_id}...")
    total_files = count_files(paths_a, max_depth) + count_files(paths_b, max_depth)
    logger.info(f"📊 Total de fichiers à scanner: {total_files}")
    
    current_time = time.time()
    scan_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": total_files,
        "current_file": "",
        "results": None,
        "errors": None,
        "created_at": current_time,
        "tab_id": tab_id
    }
    
    logger.info(f"✨ Tâche {task_id} créée et ajoutée à scan_tasks")
    logger.debug(f"🔍 Tâches actives: {list(scan_tasks.keys())}")

    background_tasks.add_task(perform_scan_task, task_id, paths_a, paths_b, max_depth)
    
    return {"task_id": task_id}


# --- Endpoint pour le Scan par dossier (nouveau) ---

def perform_scan_folder_task(task_id: str, paths_a: list, paths_b: list, check_column: str, max_depth: int = -1):
    """Effectue le scan de dossiers et met à jour l'état de la tâche."""
    logger.info(f"🔍 Début du scan par dossier pour la tâche {task_id} (colonne: {check_column})")
    logger.info(f"📁 Chemins A: {paths_a}")
    logger.info(f"📁 Chemins B: {paths_b}")
    logger.info(f"🔢 Profondeur maximale: {max_depth if max_depth >= 0 else 'illimitée'}")
    
    try:
        results, errors = analyze_hardlinks_by_folder(paths_a, paths_b, check_column, task_id, scan_tasks, max_depth)
        scan_tasks[task_id]["status"] = "completed"
        scan_tasks[task_id]["results"] = results
        scan_tasks[task_id]["errors"] = errors
        scan_tasks[task_id]["completed_at"] = time.time()
        
        logger.info(f"✅ Scan par dossier terminé pour la tâche {task_id}")
        logger.info(f"📊 Résultats: {len(results.get('synced', []))} synchronisés, {len(results.get('orphans_a', []))} orphelins A, {len(results.get('orphans_b', []))} orphelins B")
        if errors:
            logger.warning(f"⚠️ {len(errors)} erreurs rencontrées pendant le scan")
    except Exception as e:
        logger.error(f"❌ Erreur lors du scan par dossier de la tâche {task_id}: {str(e)}")
        scan_tasks[task_id]["status"] = "error"
        scan_tasks[task_id]["error"] = str(e)
        scan_tasks[task_id]["completed_at"] = time.time()

@app.post("/api/scan-folder/{tab_id}")
def run_scan_folder(tab_id: str, background_tasks: BackgroundTasks):
    config = load_config()
    tab = next((t for t in config.get("tabs", []) if t.get("id") == tab_id), None)
    
    if not tab:
        raise HTTPException(status_code=404, detail=f"L'onglet '{tab_id}' n'existe pas.")

    paths_a = tab.get("paths_a", [])
    paths_b = tab.get("paths_b", [])
    check_column = tab.get("check_column", "a")
    max_depth = tab.get("max_depth", -1)

    if not paths_a or not paths_b:
        raise HTTPException(status_code=400, detail=f"Aucun chemin configuré pour l'onglet '{tab_id}'.")

    if check_column not in ["a", "b", "both"]:
        raise HTTPException(status_code=400, detail="Le paramètre check_column doit être 'a', 'b' ou 'both'.")

    task_id = str(uuid.uuid4())
    total_files = count_files(paths_a, max_depth) + count_files(paths_b, max_depth)
    
    current_time = time.time()
    scan_tasks[task_id] = {
        "status": "running",
        "progress": 0,
        "total": total_files,
        "current_file": "",
        "results": None,
        "errors": None,
        "created_at": current_time,
        "tab_id": tab_id
    }

    background_tasks.add_task(perform_scan_folder_task, task_id, paths_a, paths_b, check_column, max_depth)
    
    return {"task_id": task_id}

@app.get("/api/scan/status/{task_id}")
def get_scan_status(task_id: str):
    """Récupère l'état d'une tâche de scan."""
    logger.debug(f"🔍 Demande de statut pour la tâche: {task_id}")
    logger.debug(f"🗂️ Tâches disponibles: {list(scan_tasks.keys())}")
    
    task = scan_tasks.get(task_id)
    if not task:
        logger.error(f"❌ Tâche de scan non trouvée: {task_id}")
        logger.error(f"🗂️ Tâches actuellement en mémoire: {list(scan_tasks.keys())}")
        raise HTTPException(status_code=404, detail="Tâche de scan non trouvée.")
    
    logger.debug(f"✅ Statut trouvé pour {task_id}: {task.get('status', 'unknown')} ({task.get('progress', 0)}/{task.get('total', 0)})")
    return task