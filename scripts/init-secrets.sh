#!/bin/sh
# Create ./secrets for Docker Compose (mode 0600). Never prints secret values.
#   ./scripts/init-secrets.sh                      # generate DB password and app key
#   ./scripts/init-secrets.sh --import-groq .env   # also copy GROQ_API_KEY from an env file, silently
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p secrets
chmod 700 secrets

gen() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }

[ -s secrets/postgres_password ] || gen 32 > secrets/postgres_password
[ -s secrets/app_secret_key ] || gen 48 > secrets/app_secret_key
[ -e secrets/groq_api_key ] || : > secrets/groq_api_key
[ -e secrets/openai_api_key ] || : > secrets/openai_api_key

if [ "${1:-}" = "--import-groq" ]; then
  src=${2:?usage: --import-groq <env-file>}
  value=$(sed -n 's/^[[:space:]]*GROQ_API_KEY[[:space:]]*=[[:space:]]*//p' "$src" | tail -n 1 | tr -d '"'"'"' \r')
  if [ -n "$value" ]; then
    printf '%s' "$value" > secrets/groq_api_key
    echo "GROQ_API_KEY importada para secrets/groq_api_key (valor não exibido)."
  else
    echo "GROQ_API_KEY não encontrada em $src" >&2
    exit 1
  fi
fi
chmod 600 secrets/*
echo "Secrets prontos em ./secrets (fora do Git)."
