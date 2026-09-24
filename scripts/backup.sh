#!/usr/bin/env bash
# Бекап Mirror: PostgreSQL + media/air + default.jpg + nginx/certs.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${MIRROR_BACKUP_DIR:-/backup/mirror}"
KEEP="${MIRROR_BACKUP_KEEP:-14}"
DATE=$(date +%Y%m%d-%H%M%S)

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
step()   { printf "\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n" "$*"; }
die() { red "ERROR: $*"; exit 1; }

[[ -d "$BACKUP_DIR" ]] || die "$BACKUP_DIR не існує. Створи його або задай MIRROR_BACKUP_DIR."
[[ -w "$BACKUP_DIR" ]] || die "$BACKUP_DIR не доступний для запису."
[[ -f .env ]] || die ".env відсутній"
set -a; source .env; set +a

command -v docker >/dev/null || die "docker не знайдено"
docker compose ps postgres --status running >/dev/null 2>&1 \
    || die "postgres не запущений"

step "Дамп PostgreSQL"
DB_DUMP="$BACKUP_DIR/db-$DATE.sql.gz"
docker compose exec -T postgres \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
    | gzip > "$DB_DUMP"
green "БД: $DB_DUMP ($(du -h "$DB_DUMP" | cut -f1))"

step "Синхронізую media/air + default.jpg"
PREV_LINK="$BACKUP_DIR/media-air-latest"
MEDIA_DEST="$BACKUP_DIR/media-air-$DATE"
mkdir -p "$MEDIA_DEST"
mkdir -p "$MEDIA_DEST/air"
if [[ -d "$PREV_LINK/air" ]]; then
    rsync -a --delete --link-dest="$PREV_LINK/air" media/air/ "$MEDIA_DEST/air/"
else
    rsync -a --delete media/air/ "$MEDIA_DEST/air/"
fi
if [[ -f media/default.jpg ]]; then
    cp -a media/default.jpg "$MEDIA_DEST/default.jpg"
fi
ln -sfn "$MEDIA_DEST" "$PREV_LINK.tmp"
mv -T "$PREV_LINK.tmp" "$PREV_LINK"
green "media: $MEDIA_DEST"

step "Сертифікати"
if ls nginx/certs/*.crt >/dev/null 2>&1; then
    tar -czf "$BACKUP_DIR/certs-$DATE.tar.gz" -C nginx certs
    green "certs: $BACKUP_DIR/certs-$DATE.tar.gz"
fi

step "Ротація (keep=$KEEP)"
# shellcheck disable=SC2012
ls -1dt "$BACKUP_DIR"/db-*.sql.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
ls -1dt "$BACKUP_DIR"/media-air-* 2>/dev/null | grep -v latest | tail -n +"$((KEEP + 1))" | xargs -r rm -rf
ls -1dt "$BACKUP_DIR"/certs-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

yellow "Нагадування: .env у бекап не входить. Секрети — окремо."
green "Готово."
