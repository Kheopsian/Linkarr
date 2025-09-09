# backend/scanner.py
import os
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

def count_files(paths: list[str], max_depth: int = -1) -> int:
    """Compte le nombre total de fichiers dans une liste de chemins."""
    logger.info(f"📊 Comptage des fichiers dans {len(paths)} chemins (profondeur max: {max_depth if max_depth >= 0 else 'illimitée'})...")
    total = 0
    for path in paths:
        try:
            path_total = 0
            for root, dirs, files in os.walk(path, topdown=True):
                # Calculer la profondeur actuelle par rapport au chemin de base
                if max_depth >= 0:
                    relative_path = os.path.relpath(root, path)
                    if relative_path == '.':
                        depth = 0
                    else:
                        depth = len(relative_path.split(os.sep))
                    
                    # Empêcher la descente si on atteint la profondeur maximale
                    if depth >= max_depth:
                        dirs.clear()
                    
                    # Ignorer si on dépasse la profondeur maximale
                    if depth > max_depth:
                        continue
                
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

def analyze_hardlinks(paths_a: list[str], paths_b: list[str], task_id: str = None, tasks_db: dict = None, max_depth: int = -1):
    """
    Analyse les liens durs (hardlinks) entre deux listes de répertoires.
    """
    task_info = f"pour la tâche {task_id}" if task_id else "sans tâche"
    logger.info(f"🔍 Analyse des hardlinks démarrée {task_info} (profondeur max: {max_depth if max_depth >= 0 else 'illimitée'})")
    
    inodes_map = defaultdict(lambda: {"A": [], "B": []})
    errors = []
    files_processed = 0

    def scan_directory(directory_path: str, column: str):
        """Scanne un répertoire et remplit la map d'inodes."""
        nonlocal files_processed
        logger.info(f"📁 Scan du répertoire {column}: {directory_path}")
        try:
            for root, dirs, files in os.walk(directory_path, topdown=True):
                # Calculer la profondeur actuelle par rapport au chemin de base
                if max_depth >= 0:
                    relative_path = os.path.relpath(root, directory_path)
                    if relative_path == '.':
                        depth = 0
                    else:
                        depth = len(relative_path.split(os.sep))
                    
                    # Empêcher la descente si on atteint la profondeur maximale
                    if depth >= max_depth:
                        dirs.clear()
                    
                    # Ignorer si on dépasse la profondeur maximale
                    if depth > max_depth:
                        continue
                
                logger.debug(f"🔍 Scan du dossier: {root} ({len(files)} fichiers)")
                for filename in files:
                    files_processed += 1
                    # Mise à jour du progrès seulement si on a un task_id et tasks_db valides
                    if task_id and tasks_db and task_id in tasks_db:
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

def analyze_hardlinks_by_folder(paths_a: list[str], paths_b: list[str], check_column: str, task_id: str = None, tasks_db: dict = None, max_depth: int = -1):
    """
    Analyse les liens durs (hardlinks) par dossier.
    """
    task_info = f"pour la tâche {task_id}" if task_id else "sans tâche"
    logger.info(f"🔍 Analyse des hardlinks par dossier démarrée {task_info} (colonne: {check_column}, profondeur max: {max_depth if max_depth >= 0 else 'illimitée'})")
    
    inodes_map = defaultdict(lambda: {"A": [], "B": []})
    errors = []
    files_processed = 0
    
    synced_folders = defaultdict(set)
    
    def scan_directory(directory_path: str, column: str):
        """Scanne un répertoire et remplit la map d'inodes."""
        nonlocal files_processed
        logger.info(f"📁 Scan par dossier du répertoire {column}: {directory_path}")
        try:
            for root, dirs, files in os.walk(directory_path, topdown=True):
                # Calculer la profondeur actuelle par rapport au chemin de base
                if max_depth >= 0:
                    relative_path = os.path.relpath(root, directory_path)
                    if relative_path == '.':
                        depth = 0
                    else:
                        depth = len(relative_path.split(os.sep))
                    
                    # Empêcher la descente si on atteint la profondeur maximale
                    if depth >= max_depth:
                        dirs.clear()
                    
                    # Ignorer si on dépasse la profondeur maximale
                    if depth > max_depth:
                        continue
                
                logger.debug(f"🔍 Scan du dossier: {root} ({len(files)} fichiers)")
                for filename in files:
                    files_processed += 1
                    # Mise à jour du progrès seulement si on a un task_id et tasks_db valides
                    if task_id and tasks_db and task_id in tasks_db:
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
def delete_orphan_files(paths_a: list[str], paths_b: list[str], column: str = "b", dry_run: bool = False, task_id: str = None, tasks_db: dict = None, max_depth: int = -1):
    """
    Supprime les fichiers orphelins d'une colonne spécifique.
    
    Args:
        paths_a: Liste des chemins de la colonne A
        paths_b: Liste des chemins de la colonne B
        column: Colonne à nettoyer ('a', 'b', ou 'both')
        dry_run: Si True, ne supprime pas réellement les fichiers
        task_id: ID de la tâche pour le suivi
        tasks_db: Base de données des tâches pour le suivi
        max_depth: Profondeur maximale de scan
    
    Returns:
        dict: Résultats de la suppression avec les fichiers supprimés et les erreurs
    """
    logger.info(f"🗑️ Début de la suppression des orphelins (colonne: {column}, dry_run: {dry_run})")
    
    # D'abord, scanner pour identifier les orphelins
    results, scan_errors = analyze_hardlinks(paths_a, paths_b, task_id, tasks_db, max_depth)
    
    deletion_results = {
        "deleted_files": [],
        "errors": scan_errors.copy(),
        "dry_run": dry_run,
        "total_deleted": 0,
        "total_errors": 0
    }
    
    files_to_delete = []
    
    # Déterminer quels fichiers supprimer selon la colonne
    if column in ["a", "both"]:
        files_to_delete.extend(results.get("orphans_a", []))
        logger.info(f"📂 Fichiers orphelins colonne A à traiter: {len(results.get('orphans_a', []))}")
    
    if column in ["b", "both"]:
        files_to_delete.extend(results.get("orphans_b", []))
        logger.info(f"📂 Fichiers orphelins colonne B à traiter: {len(results.get('orphans_b', []))}")
    
    logger.info(f"📊 Total de fichiers à {'simuler' if dry_run else 'supprimer'}: {len(files_to_delete)}")
    
    if not files_to_delete:
        logger.info("✅ Aucun fichier orphelin trouvé à supprimer")
        return deletion_results
    
    # Traitement des fichiers
    files_processed = 0
    for file_path in files_to_delete:
        files_processed += 1
        
        # Mise à jour du progrès si on a un task_id
        if task_id and tasks_db and task_id in tasks_db:
            tasks_db[task_id]["progress"] = files_processed
            tasks_db[task_id]["current_file"] = os.path.basename(file_path)
            
            # Log de progression tous les 10 fichiers
            if files_processed % 10 == 0:
                logger.info(f"📊 Progression suppression: {files_processed}/{len(files_to_delete)} fichiers traités...")
        
        try:
            if dry_run:
                # Mode simulation : vérifier seulement que le fichier existe
                if os.path.exists(file_path):
                    deletion_results["deleted_files"].append({
                        "path": file_path,
                        "size": os.path.getsize(file_path),
                        "action": "would_delete"
                    })
                    logger.debug(f"🔍 [DRY RUN] Fichier à supprimer: {file_path}")
                else:
                    logger.warning(f"⚠️ [DRY RUN] Fichier non trouvé: {file_path}")
                    deletion_results["errors"].append({
                        "path": file_path,
                        "error": "Fichier non trouvé"
                    })
            else:
                # Mode réel : supprimer le fichier
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    os.remove(file_path)
                    deletion_results["deleted_files"].append({
                        "path": file_path,
                        "size": file_size,
                        "action": "deleted"
                    })
                    logger.info(f"🗑️ Fichier supprimé: {file_path}")
                    
                    # Tentative de suppression du dossier parent s'il est vide
                    try:
                        parent_dir = os.path.dirname(file_path)
                        if parent_dir and os.path.exists(parent_dir) and not os.listdir(parent_dir):
                            os.rmdir(parent_dir)
                            logger.info(f"📁 Dossier vide supprimé: {parent_dir}")
                    except OSError:
                        # Le dossier n'est pas vide ou ne peut pas être supprimé
                        pass
                else:
                    logger.warning(f"⚠️ Fichier non trouvé lors de la suppression: {file_path}")
                    deletion_results["errors"].append({
                        "path": file_path,
                        "error": "Fichier non trouvé lors de la suppression"
                    })
                    
        except PermissionError as e:
            error_msg = f"Permission refusée: {str(e)}"
            logger.error(f"❌ {error_msg} pour {file_path}")
            deletion_results["errors"].append({
                "path": file_path,
                "error": error_msg
            })
        except Exception as e:
            error_msg = f"Erreur inattendue: {str(e)}"
            logger.error(f"❌ {error_msg} pour {file_path}")
            deletion_results["errors"].append({
                "path": file_path,
                "error": error_msg
            })
    
    deletion_results["total_deleted"] = len(deletion_results["deleted_files"])
    deletion_results["total_errors"] = len(deletion_results["errors"]) - len(scan_errors)
    
    action = "Simulation terminée" if dry_run else "Suppression terminée"
    logger.info(f"✅ {action}: {deletion_results['total_deleted']} fichiers traités, {deletion_results['total_errors']} erreurs")
    
    return deletion_results

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