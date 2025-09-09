# backend/config_manager.py
import json
import os
import logging
import shutil
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Chemin absolu pour Docker avec fallback pour développement local
CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config/settings.json")

# Fallback pour développement local si le chemin Docker n'existe pas
if not os.path.exists(os.path.dirname(CONFIG_PATH)) and not CONFIG_PATH.startswith("/app"):
    CONFIG_PATH = os.getenv("CONFIG_PATH", "config/settings.json")

def get_default_config() -> Dict[str, Any]:
    """Retourne la configuration par défaut."""
    return {
        "tabs": [
            {
                "id": "movies",
                "name": "Films",
                "scan_mode": "file",
                "check_column": "a",
                "max_depth": -1,
                "min_depth": 0,
                "paths_a": ["/data/downloads/movies"],
                "paths_b": ["/data/media/movies"],
                "name_a": "Downloads",
                "name_b": "Media"
            },
            {
                "id": "series",
                "name": "Séries",
                "scan_mode": "folder",
                "check_column": "a",
                "max_depth": -1,
                "min_depth": 0,
                "paths_a": ["/data/downloads/series"],
                "paths_b": ["/data/media/series"],
                "name_a": "Downloads",
                "name_b": "Media"
            }
        ]
    }

def create_default_config():
    """Crée un fichier de configuration par défaut s'il n'existe pas."""
    if os.path.exists(CONFIG_PATH):
        logger.info(f"Configuration existante trouvée : {CONFIG_PATH}")
        return
    
    logger.info(f"Création de la configuration par défaut : {CONFIG_PATH}")
    default_config = get_default_config()
    save_config(default_config)
    logger.info("Configuration par défaut créée avec succès")

def backup_config():
    """Crée une sauvegarde de la configuration actuelle."""
    if not os.path.exists(CONFIG_PATH):
        logger.warning("Aucune configuration à sauvegarder")
        return
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(CONFIG_PATH), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    backup_path = os.path.join(backup_dir, f"settings_{timestamp}.json")
    try:
        shutil.copy2(CONFIG_PATH, backup_path)
        logger.info(f"Sauvegarde créée : {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde : {e}")
        return None

def load_config() -> Dict[str, Any]:
    """Charge la configuration depuis le fichier JSON."""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.debug(f"Configuration chargée depuis : {CONFIG_PATH}")
            return config
    except FileNotFoundError:
        logger.warning(f"Fichier de configuration non trouvé : {CONFIG_PATH}")
        logger.info("Retour à la configuration par défaut")
        return get_default_config()
    except json.JSONDecodeError as e:
        logger.error(f"Erreur de format JSON dans {CONFIG_PATH} : {e}")
        # Créer une sauvegarde du fichier corrompu
        backup_path = f"{CONFIG_PATH}.corrupt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(CONFIG_PATH, backup_path)
            logger.info(f"Fichier corrompu sauvegardé : {backup_path}")
        except Exception:
            pass
        logger.info("Retour à la configuration par défaut")
        return get_default_config()
    except Exception as e:
        logger.error(f"Erreur inattendue lors du chargement de la configuration : {e}")
        return get_default_config()

def save_config(config: Dict[str, Any]):
    """Sauvegarde la configuration dans le fichier JSON."""
    try:
        # Crée le répertoire parent s'il n'existe pas
        config_dir = os.path.dirname(CONFIG_PATH)
        os.makedirs(config_dir, exist_ok=True)
        
        # Sauvegarde la configuration
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Configuration sauvegardée : {CONFIG_PATH}")
        
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de la configuration : {e}")
        raise

def validate_config(config: Dict[str, Any]) -> bool:
    """Valide la structure de la configuration."""
    try:
        if not isinstance(config, dict):
            return False
        
        if "tabs" not in config:
            return False
        
        if not isinstance(config["tabs"], list):
            return False
        
        # Validation basique des onglets
        for tab in config["tabs"]:
            if not isinstance(tab, dict):
                return False
            required_fields = ["id", "name", "scan_mode", "paths_a", "paths_b"]
            if not all(field in tab for field in required_fields):
                return False
        
        return True
        
    except Exception:
        return False