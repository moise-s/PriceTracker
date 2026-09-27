#!/bin/sh
# DESTRUCTIVE: replace the live local stack's database and uploads with a backup.
#   ./scripts/restore.sh backups/pricetracker-<timestamp> --yes
set -eu
cd "$(dirname "$0")/.."
dir=${1:?usage: restore.sh <backup-dir> --yes}
[ "${2:-}" = "--yes" ] || { echo "Refusing to overwrite live data without --yes" >&2; exit 2; }
./scripts/restore-drill.sh "$dir"
docker compose stop web api worker scheduler
docker compose exec -T db psql -U pricetracker -d postgres -c "DROP DATABASE IF EXISTS pricetracker WITH (FORCE);" -c "CREATE DATABASE pricetracker OWNER pricetracker;"
docker compose exec -T db pg_restore -U pricetracker -d pricetracker --no-owner --exit-on-error < "$dir/db.dump"
docker compose run --rm --no-deps -T --entrypoint sh --user 10001 api -c 'rm -rf /data/uploads && tar -C /data -xzf -' < "$dir/uploads.tar.gz"
docker compose up -d
echo "Restored $dir"
