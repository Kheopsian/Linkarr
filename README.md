# Linkarr

Linkarr est une application web full-stack conçue pour vous aider à gérer et organiser vos liens. Elle est composée d'un frontend en Vue.js et d'un backend en Python.

## Structure du Projet

- `frontend/`: Contient l'application frontend développée avec Vue.js et Vite.
- `backend/`: Contient l'API backend développée avec Python et Flask/Gunicorn.
- `config/`: Fichiers de configuration.
- `Dockerfile`: Pour construire l'image Docker de l'application.
- `nginx.conf`: Fichiers de configuration pour Nginx.
- `supervisord.conf`: Fichier de configuration pour Supervisor.

## Démarrage rapide avec Docker

L'application est entièrement conteneurisée avec Docker pour un déploiement et un développement faciles.

### Prérequis

- [Docker](https://docs.docker.com/get-docker/) installé sur votre machine.

### Build de l'image Docker

Pour construire l'image, exécutez la commande suivante à la racine du projet :

```bash
docker build -t linkarr .
```

### Lancer le conteneur

Pour lancer l'application, exécutez la commande suivante :

```bash
docker run -p 8899:8899 linkarr
```

L'application sera accessible à l'adresse [http://localhost:8899](http://localhost:8899).

### Changer le port

Par défaut, l'application est exposée sur le port `8899`. Vous pouvez changer ce port en utilisant la variable d'environnement `WEBUI_PORT`.

Par exemple, pour lancer l'application sur le port `8080` :

```bash
docker run -e WEBUI_PORT=8080 -p 8080:8080 linkarr
