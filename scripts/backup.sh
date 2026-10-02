#!/bin/sh
# Application-aware backup of the local Compose stack:
#   PostgreSQL custom-format dump + uploaded images + manifest (sha256, counts, schema).
#   ./scripts/backup.sh [output-dir]      (default ./backups)
set -eu
cd "$(dirname "$0")/.."
umask 077
out=${1:-./backups}
ts=$(date -u +%Y%m%dT%H%M%SZ)
dir="$out/pricetracker-$ts"
mkdir -p "$dir"
chmod 700 "$dir"

dc() { docker compose "$@"; }
psql_q() { dc exec -T db psql -U pricetracker -d pricetracker -Atc "$1"; }

dc exec -T db pg_dump -U pricetracker -d pricetracker --format=custom --no-owner > "$dir/db.dump"
dc run --rm --no-deps -T --entrypoint tar api -C /data -czf - uploads > "$dir/uploads.tar.gz"

schema=$(psql_q "select version_num from alembic_version")
counts=$(psql_q "select json_build_object('users',(select count(*) from users),'products',(select count(*) from products),'list_items',(select count(*) from list_items),'runs',(select count(*) from runs),'observations',(select count(*) from observations),'images',(select count(*) from images),'stores',(select count(*) from stores))")
uploads=$(tar -tzf "$dir/uploads.tar.gz" | grep -vc '/$' || true)
db_sha=$(shasum -a 256 "$dir/db.dump" | cut -d' ' -f1)
up_sha=$(shasum -a 256 "$dir/uploads.tar.gz" | cut -d' ' -f1)
cat > "$dir/manifest.json" <<JSON
{
  "created_at_utc": "$ts",
  "schema_version": "$schema",
  "counts": $counts,
  "upload_files": $uploads,
  "files": {
    "db.dump": {"sha256": "$db_sha", "bytes": $(wc -c < "$dir/db.dump" | tr -d ' ')},
    "uploads.tar.gz": {"sha256": "$up_sha", "bytes": $(wc -c < "$dir/uploads.tar.gz" | tr -d ' ')}
  }
}
JSON
echo "$dir"
