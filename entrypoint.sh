#!/bin/sh

#!/bin/sh

# Définit les UID/GID par défaut à 1000 s'ils ne sont pas fournis
PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Supprime les utilisateurs/groupes existants avec les UID/GID voulus
# puis supprime l'utilisateur/groupe appuser s'ils existent
if id -u ${PUID} >/dev/null 2>&1; then
    # Supprime l'utilisateur existant avec cet UID
    existing_user=$(id -nu ${PUID} 2>/dev/null || echo "")
    if [ -n "$existing_user" ]; then
        deluser "$existing_user" 2>/dev/null || true
    fi
fi

if getent group ${PGID} >/dev/null 2>&1; then
    # Supprime le groupe existant avec ce GID
    existing_group=$(getent group ${PGID} | cut -d: -f1)
    if [ -n "$existing_group" ]; then
        delgroup "$existing_group" 2>/dev/null || true
    fi
fi

# Supprime l'utilisateur/groupe appuser s'ils existent encore
if id -u appuser >/dev/null 2>&1; then
    deluser appuser 2>/dev/null || true
fi
if getent group appuser >/dev/null 2>&1; then
    delgroup appuser 2>/dev/null || true
fi

# Crée le nouveau groupe et utilisateur avec les UID/GID voulus
groupadd -g ${PGID} appuser
useradd -u ${PUID} -g appuser -s /bin/sh -d /app appuser

# Crée les répertoires nécessaires pour NGINX avec les bonnes permissions
mkdir -p /var/run/nginx
chown -R appuser:appuser /var/run/nginx
chmod 755 /var/run/nginx

# Donne la permission à notre nouvel utilisateur sur tous les dossiers nécessaires
chown -R appuser:appuser /app/config /app/logs /var/log/nginx /var/lib/nginx
chmod -R 755 /app/config /app/logs /var/log/nginx /var/lib/nginx

# Crée et configure les permissions pour le répertoire de config backend
mkdir -p /app/backend/config
chown -R appuser:appuser /app/backend/config
chmod -R 755 /app/backend/config

# Définit le port par défaut pour Nginx
# Si l'utilisateur n'est pas root (UID != 0), utilise un port non privilégié
if [ "${PUID}" != "0" ]; then
    export WEBUI_PORT=${WEBUI_PORT:-8080}
else
    export WEBUI_PORT=${WEBUI_PORT:-80}
fi
envsubst '${WEBUI_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

echo "Configuration Nginx avec le port ${WEBUI_PORT}"

# Lance le processus principal (Supervisor)
# Supervisord doit rester en tant que root pour pouvoir lancer nginx
exec /usr/bin/supervisord