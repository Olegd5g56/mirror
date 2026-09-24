#!/usr/bin/env bash
# Перший запуск Mirror на чистому хості.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
step()   { printf "\n\033[1;34m==>\033[0m \033[1m%s\033[0m\n" "$*"; }
die() { red "ERROR: $*"; exit 1; }

step "Перевіряю передумови"
command -v docker >/dev/null   || die "docker не знайдено в PATH"
command -v openssl >/dev/null  || die "openssl не знайдено в PATH"
docker compose version >/dev/null 2>&1 || die "docker compose v2 не знайдено"

green "docker / compose / openssl — на місці"

step "Перевіряю .env"
if [[ -f .env ]]; then
    yellow ".env вже існує — залишаю без змін"
else
    [[ -f .env.example ]] || die ".env.example відсутній"
    cp .env.example .env
    POSTGRES_PASSWORD=$(openssl rand -hex 24)
    JWT_SECRET=$(openssl rand -hex 32)
    TUSD_HOOK_SECRET=$(openssl rand -hex 32)
    awk -v pw="$POSTGRES_PASSWORD" -v jwt="$JWT_SECRET" -v tus="$TUSD_HOOK_SECRET" '
        /^POSTGRES_PASSWORD=/  { print "POSTGRES_PASSWORD=" pw;  next }
        /^JWT_SECRET=/         { print "JWT_SECRET=" jwt;        next }
        /^TUSD_HOOK_SECRET=/   { print "TUSD_HOOK_SECRET=" tus;  next }
        { print }
    ' .env > .env.tmp && mv .env.tmp .env
    chmod 600 .env
    green ".env створений з реальними секретами (chmod 600)"
    yellow "⚠️  Зроби копію .env в менеджері секретів"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

step "Перевіряю права на media/ і logs/"
NEED_CHOWN=0
for d in media media/air media/temp media/thumbs media/posters logs; do
    [[ -d "$d" ]] || mkdir -p "$d"
    owner=$(stat -c '%u:%g' "$d")
    if [[ "$owner" != "1000:1000" ]]; then
        NEED_CHOWN=1
        break
    fi
done

if [[ $NEED_CHOWN -eq 1 ]]; then
    yellow "Папки media/ і logs/ не належать UID 1000 — роблю chown"
    if [[ $EUID -eq 0 ]]; then
        chown -R 1000:1000 media logs
    else
        sudo chown -R 1000:1000 media logs
    fi
    green "Права виставлені"
else
    yellow "Права вже коректні (UID 1000:1000)"
fi

step "Перевіряю TLS-сертифікати"
CRT="nginx/certs/mirror.crt"
KEY="nginx/certs/mirror.key"
if [[ -f "$CRT" && -f "$KEY" ]]; then
    yellow "Сертифікати вже існують — залишаю"
else
    bash nginx/make-certs.sh
    yellow "Self-signed for ${DOMAIN:-localhost}. Replace nginx/certs/mirror.crt and mirror.key for production."
fi

step "Піднімаю postgres + redis, чекаю healthy"
docker compose up -d postgres redis

for i in $(seq 1 30); do
    state=$(docker compose ps --format json postgres 2>/dev/null | grep -o '"Health":"[a-z]*"' | head -1 | cut -d'"' -f4 || true)
    if [[ "$state" == "healthy" ]]; then
        green "postgres healthy"
        break
    fi
    if [[ $i -eq 30 ]]; then
        red "postgres не став healthy за 90с"
        red "Подивись логи: docker compose logs postgres"
        exit 1
    fi
    sleep 3
done

step "Синхронізую пароль БД з .env"
set +e
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -c "ALTER USER \"$POSTGRES_USER\" WITH PASSWORD '$POSTGRES_PASSWORD';" \
    >/dev/null 2>&1
psql_rc=$?
set -e
if [[ $psql_rc -ne 0 ]]; then
    red "Не вдалося синхронізувати пароль БД."
    red "Якщо в БД немає нічого цінного: docker compose down -v && ./scripts/bootstrap.sh"
    exit 1
fi
green "Пароль БД синхронізований"

step "Білдю і піднімаю стек"
docker compose up -d --build
green "Контейнери підняті"

step "Чекаю поки backend стане healthy"
for i in $(seq 1 40); do
    state=$(docker compose ps --format json backend 2>/dev/null | grep -o '"Health":"[a-z]*"' | head -1 | cut -d'"' -f4 || true)
    if [[ "$state" == "healthy" ]]; then
        green "backend healthy"
        break
    fi
    if [[ $i -eq 40 ]]; then
        red "backend не став healthy"
        red "Подивись логи: docker compose logs backend"
        exit 1
    fi
    sleep 3
done

step "Створення першого адміна"
existing=$(docker compose exec -T postgres \
    psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
    "SELECT count(*) FROM users;" 2>/dev/null | tr -d '[:space:]' || echo "0")

if [[ "$existing" != "0" ]]; then
    yellow "В БД вже $existing користувач(ів) — пропускаю створення адміна"
else
    echo "Введи логін адміна (за замовчуванням: admin):"
    read -r admin_user
    admin_user=${admin_user:-admin}
    docker compose exec backend python -m app.cli create-user "$admin_user"
    green "Адмін '$admin_user' створений"
fi

echo
green "================================================================="
green "Готово. Mirror: https://${DOMAIN:-localhost}:8066"
green "================================================================="
echo
yellow "Перевір що домен резолвиться (DNS або /etc/hosts)."
yellow "Корисні команди:"
yellow "  docker compose ps"
yellow "  docker compose logs -f"
yellow "  ./scripts/backup.sh"
yellow "  docker compose exec backend python -m app.cli import-legacy --help"
