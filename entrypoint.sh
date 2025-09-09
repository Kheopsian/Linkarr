#!/bin/sh
# entrypoint.sh

# Définit une valeur par défaut pour WEBUI_PORT si elle n'est pas fournie.
export WEBUI_PORT=${WEBUI_PORT:-8899}

# Remplace les variables dans le template et crée le fichier de config final pour Nginx.
envsubst '${WEBUI_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Lance le processus principal (Supervisor)
exec /usr/bin/supervisord