# backend/main.py
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List
from fastapi.middleware.cors import CORSMiddleware

from .scanner import analyze_hardlinks, analyze_hardlinks_by_folder
from .config_manager import load_config, save_config
# Importe nos modules
from .scanner import analyze_hardlinks, analyze_hardlinks_by_folder
from .config_manager import load_config, save_config

# Constante pour la base de navigation (pour la sécurité)
# Dans Docker, ce sera le point de montage de vos données, ex: /data
BROWSE_BASE_PATH = os.path.abspath(os.getenv("BROWSE_BASE_PATH", "."))

app = FastAPI()

# --- AJOUTS POUR CORS ---
origins = [
    "http://localhost:5173", # L'adresse de notre frontend de dev
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/api/scan/{tab_id}")
def run_scan(tab_id: str):
    """
    Lance une analyse sur un onglet en utilisant les chemins de la configuration sauvegardée.
    """
    config = load_config()
    
    # Trouver l'onglet correspondant à l'ID
    tab = None
    for t in config.get("tabs", []):
        if t.get("id") == tab_id:
            tab = t
            break
    
    if not tab:
        raise HTTPException(status_code=404, detail=f"L'onglet '{tab_id}' n'existe pas.")
    
    if not tab.get("paths_a") or not tab.get("paths_b"):
        raise HTTPException(status_code=404, detail=f"Aucun chemin configuré pour l'onglet '{tab_id}'.")
    
    results, errors = analyze_hardlinks(tab["paths_a"], tab["paths_b"])
    
    return {"results": results, "errors": errors}


# --- Endpoint pour le Scan par dossier (nouveau) ---

@app.post("/api/scan-folder/{tab_id}")
def run_scan_folder(tab_id: str, check_column: str = 'a'):
    """
    Lance une analyse sur un onglet en utilisant les chemins de la configuration sauvegardée
    et en considérant qu'un dossier est synchronisé s'il contient au moins un fichier hardlink.
    
    Args:
        tab_id: L'ID de l'onglet à analyser
        check_column: La colonne à vérifier pour les dossiers synchronisés ('a', 'b' ou 'both')
    """
    if check_column not in ["a", "b", "both"]:
        raise HTTPException(status_code=400, detail="Le paramètre check_column doit être 'a', 'b' ou 'both'.")

    config = load_config()
    
    # Trouver l'onglet correspondant à l'ID
    tab = None
    for t in config.get("tabs", []):
        if t.get("id") == tab_id:
            tab = t
            break
    
    if not tab:
        raise HTTPException(status_code=404, detail=f"L'onglet '{tab_id}' n'existe pas.")
    
    if not tab.get("paths_a") or not tab.get("paths_b"):
        raise HTTPException(status_code=404, detail=f"Aucun chemin configuré pour l'onglet '{tab_id}'.")
    
    results, errors = analyze_hardlinks_by_folder(
        tab["paths_a"],
        tab["paths_b"],
        check_column
    )
    
    return {"results": results, "errors": errors}