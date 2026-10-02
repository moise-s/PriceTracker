#!/bin/sh
# Restore a backup into a throwaway PostgreSQL container and verify it against the
# manifest (checksums, schema version, row counts, upload files). Touches nothing live.
#   ./scripts/restore-drill.sh backups/pricetracker-<timestamp>
set -eu
cd "$(dirname "$0")/.."
dir=${1:?usage: restore-drill.sh <backup-dir>}
image="postgres:17.10-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
name="pricetracker-restore-drill-$$"
work=$(mktemp -d)
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT

json() { python3 -c "import json,sys; d=json.load(open('$dir/manifest.json')); print($1)"; }
for f in db.dump uploads.tar.gz; do
  want=$(json "d['files']['$f']['sha256']")
  got=$(shasum -a 256 "$dir/$f" | cut -d' ' -f1)
  [ "$want" = "$got" ] || { echo "FAIL checksum $f"; exit 1; }
done
echo "checksums ok"

docker run -d --name "$name" -e POSTGRES_PASSWORD=drill -e POSTGRES_USER=pricetracker -e POSTGRES_DB=pricetracker "$image" >/dev/null
i=0; until docker exec "$name" pg_isready -U pricetracker -d pricetracker >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 60 ] && { echo "FAIL postgres did not start"; exit 1; }; sleep 1; done
sleep 1
docker exec -i "$name" pg_restore -U pricetracker -d pricetracker --no-owner --exit-on-error < "$dir/db.dump"
q() { docker exec "$name" psql -U pricetracker -d pricetracker -Atc "$1"; }
schema=$(q "select version_num from alembic_version")
[ "$schema" = "$(json "d['schema_version']")" ] || { echo "FAIL schema $schema"; exit 1; }
for table in users products list_items runs observations images stores; do
  got=$(q "select count(*) from $table")
  want=$(json "d['counts']['$table']")
  [ "$got" = "$want" ] || { echo "FAIL $table: restored $got, expected $want"; exit 1; }
  echo "  $table: $got"
done
tar -xzf "$dir/uploads.tar.gz" -C "$work"
files=$(find "$work/uploads" -type f | wc -l | tr -d ' ')
[ "$files" = "$(json "d['upload_files']")" ] || { echo "FAIL uploads: $files files"; exit 1; }
echo "  upload files: $files"
echo "PASS restore drill: $dir (schema $schema)"
