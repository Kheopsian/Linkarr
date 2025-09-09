# Linkarr

Application de monitoring de hardlinks pour synchroniser les fichiers entre deux répertoires.

## Description

Linkarr est une application qui permet de scanner des fichiers à la recherche de hardlinks (liens durs) entre deux répertoires. Elle est composée d'un backend Python qui effectue le scanning et d'un frontend Vue.js qui permet de configurer les chemins à scanner et d'afficher les résultats.

## Fonctionnalités

- Scan de fichiers pour détecter les hardlinks
- Interface web pour configurer les chemins de scan
- Affichage des fichiers synchronisés, orphelins et en conflit
- Support des PUID/PGID pour une meilleure compatibilité Docker

## Technologies utilisées

- Backend : Python, FastAPI
- Frontend : Vue.js, Tailwind CSS
- Infrastructure : Docker, NGINX, Gunicorn, Supervisor

## Configuration Docker

L'application supporte les variables d'environnement suivantes :

- `PUID` : User ID pour l'utilisateur appuser (par défaut : 1000)
- `PGID` : Group ID pour le groupe appuser (par défaut : 1000)
- `WEBUI_PORT` : Port d'écoute pour l'interface web (par défaut : 80)
- `BROWSE_BASE_PATH` : Chemin de base pour la navigation dans les fichiers (par défaut : ".")

### Exemple d'utilisation

```bash
docker run -d \
  --name linkarr \
  -e PUID=1000 \
  -e PGID=1000 \
  -e WEBUI_PORT=8080 \
  -e BROWSE_BASE_PATH=/data \
  -p 8080:8080 \
  -v /chemin/vers/downloads:/data/downloads \
  -v /chemin/vers/media:/data/media \
  linkarr:latest
```

## Résolution des problèmes de permissions

Les problèmes de permissions NGINX ont été résolus en :

1. Créant le répertoire `/var/run/nginx` avec les bonnes permissions dans le Dockerfile
2. Mettant à jour le entrypoint.sh pour gérer correctement les PUID/PGID
3. Modifiant supervisord.conf pour éviter les warnings liés à l'exécution en tant que root
4. Ajoutant la directive `pid` dans nginx.conf.template pour définir le fichier PID dans un emplacement accessible

Ces corrections permettent à l'application de fonctionner correctement même avec des PUID/PGID différents de 1000.
