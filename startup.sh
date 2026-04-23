#!/bin/bash
set -e

# Install ODBC Driver 18
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list
apt-get update -qq
ACCEPT_EULA=Y apt-get install -y -q msodbcsql18

# Start gunicorn
exec gunicorn --bind 0.0.0.0:8000 app:app