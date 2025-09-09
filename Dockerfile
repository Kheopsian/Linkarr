# --- STAGE 1: Build du Frontend ---
FROM node:20-alpine AS builder
WORKDIR /app
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install
COPY frontend/ .
RUN yarn build

# --- STAGE 2: Application Finale ---
FROM python:3.11-slim

# Installer les dépendances, y compris gettext-base pour envsubst
RUN apt-get update && apt-get install -y nginx supervisor gettext-base

WORKDIR /app

# Copier et installer les dépendances Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Créer le répertoire de config pour la gestion des permissions
RUN mkdir -p /app/config

COPY backend/ ./backend/

# Copier les fichiers statiques du frontend
COPY --from=builder /app/dist /var/www/html

# Copier le TEMPLATE Nginx et le script d'entrée
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh

# Rendre le script exécutable
RUN chmod +x /entrypoint.sh

# Exposer le port par défaut
EXPOSE 80

# Définir le script d'entrée comme point de lancement du conteneur
ENTRYPOINT ["/entrypoint.sh"]