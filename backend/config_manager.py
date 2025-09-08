# backend/config_manager.py
import json
import os
from typing import Dict, Any

# Le chemin est défini par rapport à l'intérieur du conteneur plus tard
# Pour le développement local, il pointera vers le dossier config que nous avons créé
CONFIG_PATH = os.getenv("CONFIG_PATH", "config/settings.json")

def load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier JSON."""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Si le fichier n'existe pas ou est corrompu, retourne une config par défaut
        return {
          "tabs": [
            {
              "id": "movies",
              "name": "Films",
              "scan_mode": "file",
              "paths_a": [],
              "paths_b": [],
              "name_a": "Downloads",
              "name_b": "Media"
            },
            {
              "id": "series",
              "name": "Séries",
              "scan_mode": "folder",
              "check_column": "a",
              "paths_a": [],
              "paths_b": [],
              "name_a": "Downloads",
              "name_b": "Media"
            }
          ]
        }

def save_config(config: Dict[str, Any]):
    """Sauvegarde la configuration dans le fichier JSON."""
    # Crée le répertoire parent s'il n'existe pas
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)