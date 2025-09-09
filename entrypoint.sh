#!/bin/sh

# Définit les UID/GID par défaut à 1000 s'ils ne sont pas fournis
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Crée le groupe et l'utilisateur avec les bons IDs
groupadd -g ${PGID} appuser
useradd -u ${PUID} -g appuser -s /bin/sh -d /app appuser

# Donne la permission à notre nouvel utilisateur sur le dossier de configuration
chown -R appuser:appuser /app/config

# Définit le port par défaut pour Nginx
export WEBUI_PORT=${WEBUI_PORT:-80}
envsubst '${WEBUI_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Lance le processus principal (Supervisor)
exec /usr/bin/supervisord