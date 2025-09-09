# backend/scanner.py
import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def count_files(paths: list[str]) -> int:
    """Compte le nombre total de fichiers dans une liste de chemins."""
    logger.info(f"📊 Comptage des fichiers dans {len(paths)} chemins...")
    total = 0
    for path in paths:
        try:
            path_total = 0
            for _, _, files in os.walk(path):
                path_total += len(files)
            total += path_total
            logger.debug(f"📁 {path}: {path_total} fichiers")
        except FileNotFoundError:
            logger.warning(f"❌ Chemin non trouvé lors du comptage: {path}")
            continue
        except Exception as e:
            logger.error(f"❌ Erreur lors du comptage dans {path}: {str(e)}")
            continue
    
    logger.info(f"📊 Total de fichiers comptés: {total}")
    return total

def analyze_hardlinks(paths_a: list[str], paths_b: list[str], task_id: str, tasks_db: dict):
    """
    Analyse les liens durs (hardlinks) entre deux listes de répertoires.
    """
    logger.info(f"🔍 Analyse des hardlinks démarrée pour la tâche {task_id}")
    
    inodes_map = defaultdict(lambda: {"A": [], "B": []})
    errors = []
    files_processed = 0

    def scan_directory(directory_path: str, column: str):
        """Scanne un répertoire et remplit la map d'inodes."""
        nonlocal files_processed
        logger.info(f"📁 Scan du répertoire {column}: {directory_path}")
        try:
            for root, _, files in os.walk(directory_path):
                logger.debug(f"🔍 Scan du dossier: {root} ({len(files)} fichiers)")
                for filename in files:
                    files_processed += 1
                    if tasks_db.get(task_id):
                        tasks_db[task_id]["progress"] += 1
                        tasks_db[task_id]["current_file"] = filename
                        # Log de progression tous les 100 fichiers
                        if files_processed % 100 == 0:
                            logger.info(f"📊 Progression: {files_processed} fichiers traités...")
                    
                    filepath = os.path.join(root, filename)
                    try:
                        stat = os.stat(filepath)
                        # Clé unique pour un appareil et un inode
                        inode_key = (stat.st_dev, stat.st_ino)
                        inodes_map[inode_key][column].append(filepath)
                    except FileNotFoundError:
                        # Le fichier a peut-être été supprimé pendant le scan
                        logger.debug(f"⚠️ Fichier non trouvé pendant le scan: {filepath}")
                        continue
                    except Exception as e:
                        logger.warning(f"❌ Erreur lors du traitement du fichier {filepath}: {str(e)}")
                        errors.append({"path": filepath, "error": str(e)})
        except FileNotFoundError:
            logger.error(f"❌ Dossier non trouvé: {directory_path}")
            errors.append({"path": directory_path, "error": "Le dossier n'existe pas."})
        except Exception as e:
            logger.error(f"❌ Erreur lors du scan du dossier {directory_path}: {str(e)}")
            errors.append({"path": directory_path, "error": str(e)})

    # Scanne tous les dossiers fournis
    for path in paths_a:
        scan_directory(path, "A")
    for path in paths_b:
        scan_directory(path, "B")

    # Analyse des résultats
    results = {
        "synced": [],
        "orphans_a": [], # Présent en A, mais pas en B
        "orphans_b": [], # Présent en B, mais pas en A
        "conflicts": []  # Plus de 2 hardlinks au total
    }

    for inode_key, paths in inodes_map.items():
        count_a = len(paths["A"])
        count_b = len(paths["B"])

        # Cas parfait : 1 hardlink en A et 1 en B
        if count_a == 1 and count_b == 1:
            results["synced"].append({"path_a": paths["A"][0], "path_b": paths["B"][0]})
        
        # Orphelin en A : au moins un lien en A, aucun en B
        elif count_a > 0 and count_b == 0:
            results["orphans_a"].extend(paths["A"])
            
        # Orphelin en B : au moins un lien en B, aucun en A
        elif count_b > 0 and count_a == 0:
            results["orphans_b"].extend(paths["B"])
            
        # Tous les autres cas sont des "conflits" à examiner
        # (ex: 2 en A et 1 en B, 2 en A et 0 en B, etc.)
        else:
            results["conflicts"].append({"paths_a": paths["A"], "paths_b": paths["B"]})

    return results, errors

def analyze_hardlinks_by_folder(paths_a: list[str], paths_b: list[str], check_column: str, task_id: str, tasks_db: dict):
    """
    Analyse les liens durs (hardlinks) par dossier.
    """
    logger.info(f"🔍 Analyse des hardlinks par dossier démarrée pour la tâche {task_id} (colonne: {check_column})")
    
    inodes_map = defaultdict(lambda: {"A": [], "B": []})
    errors = []
    files_processed = 0
    
    synced_folders = defaultdict(set)
    
    def scan_directory(directory_path: str, column: str):
        """Scanne un répertoire et remplit la map d'inodes."""
        nonlocal files_processed
        logger.info(f"📁 Scan par dossier du répertoire {column}: {directory_path}")
        try:
            for root, _, files in os.walk(directory_path):
                logger.debug(f"🔍 Scan du dossier: {root} ({len(files)} fichiers)")
                for filename in files:
                    files_processed += 1
                    if tasks_db.get(task_id):
                        tasks_db[task_id]["progress"] += 1
                        tasks_db[task_id]["current_file"] = filename
                        # Log de progression tous les 100 fichiers
                        if files_processed % 100 == 0:
                            logger.info(f"📊 Progression scan par dossier: {files_processed} fichiers traités...")
                    
                    filepath = os.path.join(root, filename)
                    try:
                        stat = os.stat(filepath)
                        # Clé unique pour un appareil et un inode
                        inode_key = (stat.st_dev, stat.st_ino)
                        inodes_map[inode_key][column].append(filepath)
                    except FileNotFoundError:
                        # Le fichier a peut-être été supprimé pendant le scan
                        logger.debug(f"⚠️ Fichier non trouvé pendant le scan: {filepath}")
                        continue
                    except Exception as e:
                        logger.warning(f"❌ Erreur lors du traitement du fichier {filepath}: {str(e)}")
                        errors.append({"path": filepath, "error": str(e)})
        except FileNotFoundError:
            logger.error(f"❌ Dossier non trouvé: {directory_path}")
            errors.append({"path": directory_path, "error": "Le dossier n'existe pas."})
        except Exception as e:
            logger.error(f"❌ Erreur lors du scan du dossier {directory_path}: {str(e)}")
            errors.append({"path": directory_path, "error": str(e)})

    # Scanne tous les dossiers fournis
    for path in paths_a:
        scan_directory(path, "A")
    for path in paths_b:
        scan_directory(path, "B")

    # Identifie les dossiers qui ont au moins un fichier synchronisé
    for inode_key, paths in inodes_map.items():
        if len(paths["A"]) > 0 and len(paths["B"]) > 0:
            # Pour chaque fichier synchronisé, marquer son dossier comme synchronisé
            for path in paths["A"] + paths["B"]:
                if check_column == 'a' and path.startswith(tuple(paths_a)):
                    folder_path = os.path.dirname(path)
                    synced_folders['A'].add(folder_path)
                elif check_column == 'b' and path.startswith(tuple(paths_b)):
                    folder_path = os.path.dirname(path)
                    synced_folders['B'].add(folder_path)
                # Si check_column est 'both', on marque les deux côtés
                elif check_column == 'both':
                    if path.startswith(tuple(paths_a)):
                        folder_path = os.path.dirname(path)
                        synced_folders['A'].add(folder_path)
                    elif path.startswith(tuple(paths_b)):
                        folder_path = os.path.dirname(path)
                        synced_folders['B'].add(folder_path)

    # Analyse des résultats
    results = {
        "synced": [],
        "synced_folders": {
            "A": list(synced_folders['A']),
            "B": list(synced_folders['B'])
        },
        "orphans_a": [], # Présent en A, mais pas en B
        "orphans_b": [], # Présent en B, mais pas en A
        "conflicts": []  # Plus de 2 hardlinks au total
    }

    for inode_key, paths in inodes_map.items():
        count_a = len(paths["A"])
        count_b = len(paths["B"])

        # Cas parfait : 1 hardlink en A et 1 en B
        if count_a == 1 and count_b == 1:
            results["synced"].append({"path_a": paths["A"][0], "path_b": paths["B"][0]})
        
        # Orphelin en A : au moins un lien en A, aucun en B
        elif count_a > 0 and count_b == 0:
            # Vérifier si le dossier est déjà marqué comme synchronisé
            folder_path = os.path.dirname(paths["A"][0])
            if folder_path not in synced_folders['A']:
                results["orphans_a"].extend(paths["A"])
            
        # Orphelin en B : au moins un lien en B, aucun en A
        elif count_b > 0 and count_a == 0:
            # Vérifier si le dossier est déjà marqué comme synchronisé
            folder_path = os.path.dirname(paths["B"][0])
            if folder_path not in synced_folders['B']:
                results["orphans_b"].extend(paths["B"])
            
        # Tous les autres cas sont des "conflits" à examiner
        # (ex: 2 en A et 1 en B, 2 en A et 0 en B, etc.)
        else:
            results["conflicts"].append({"paths_a": paths["A"], "paths_b": paths["B"]})

    return results, errors

# --- Section pour tester le script directement ---
if __name__ == "__main__":
    # Crée une structure de test pour simuler votre cas d'usage
    print("Création d'une structure de dossiers de test...")
    os.makedirs("test_structure/downloads/movie1", exist_ok=True)
    os.makedirs("test_structure/media/movies/Movie One (2023)", exist_ok=True)
    os.makedirs("test_structure/downloads/movie2_orphan", exist_ok=True)
    os.makedirs("test_structure/media/movies/Movie Three (2023)_orphan", exist_ok=True)

    # Fichier 1 : Synchronisé
    with open("test_structure/downloads/movie1/movie1.mkv", "w") as f:
        f.write("movie data")
    os.link("test_structure/downloads/movie1/movie1.mkv", "test_structure/media/movies/Movie One (2023)/Movie One.mkv")

    # Fichier 2 : Orphelin dans downloads
    with open("test_structure/downloads/movie2_orphan/movie2.mkv", "w") as f:
        f.write("orphan data A")

    # Fichier 3 : Orphelin dans media
    with open("test_structure/media/movies/Movie Three (2023)_orphan/Movie Three.mkv", "w") as f:
        f.write("orphan data B")

    print("Structure de test créée.")
    print("\nLancement de l'analyse...")
    
    # Définir les chemins à scanner
    col_a_paths = ["test_structure/downloads"]
    col_b_paths = ["test_structure/media/movies"]
    
    scan_results, scan_errors = analyze_hardlinks(col_a_paths, col_b_paths)
    
    print("\n--- RÉSULTATS DE L'ANALYSE ---")
    import json
    print(json.dumps(scan_results, indent=2))

    if scan_errors:
        print("\n--- ERREURS RENCONTRÉES ---")
        print(json.dumps(scan_errors, indent=2))