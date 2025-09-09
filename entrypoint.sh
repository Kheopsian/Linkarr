#!/bin/sh

# Définit les UID/GID par défaut à 1000 s'ils ne sont pas fournis
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Supprime l'utilisateur/groupe par défaut et les recrée avec les IDs fournis
deluser appuser
delgroup appuser
groupadd -g ${PGID} appuser
useradd -u ${PUID} -g appuser -s /bin/sh -d /app appuser

# Donne la permission à notre nouvel utilisateur sur tous les dossiers nécessaires
chown -R appuser:appuser /app/config /var/log/nginx /var/lib/nginx /run/nginx

# Définit le port par défaut pour Nginx
export WEBUI_PORT=${WEBUI_PORT:-80}
envsubst '${WEBUI_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Lance le processus principal (Supervisor)
exec /usr/bin/supervisord