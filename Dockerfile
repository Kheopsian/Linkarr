# --- STAGE 1: Build du Frontend ---
FROM node:20-alpine AS builder
WORKDIR /app
# Copie package.json ET yarn.lock
COPY frontend/package.json frontend/yarn.lock ./
# Installe les dépendances avec yarn
RUN yarn install
COPY frontend/ .
# Lance le build avec yarn
RUN yarn build

# --- STAGE 2: Application Finale ---
FROM python:3.11-slim

# Installer Nginx et Supervisor
RUN apt-get update && apt-get install -y nginx supervisor

# Définir le répertoire de travail
WORKDIR /app

# Copier les dépendances Python et les installer
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code du backend
COPY backend/ ./backend/

# Copier les fichiers statiques du frontend buildés depuis le stage 1
COPY --from=builder /app/dist /var/www/html

# Copier les fichiers de configuration de Nginx et Supervisor
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Exposer le port 80 (le seul port public, géré par Nginx)
EXPOSE 80

# Lancer Supervisor, qui lancera Nginx et Gunicorn
CMD ["/usr/bin/supervisord"]