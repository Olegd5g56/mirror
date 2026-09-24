# Operations

## Code

The backend and frontend trees are not mounted into the containers.
A code change needs a new image.

```bash
docker compose up -d --build backend worker
docker compose up -d --build frontend
```

Frontend is a one-shot container: it builds the page and copies it into a volume.
Reload the browser with the cache bypassed after that.

Playback and file-path tests, no database:

```bash
docker compose exec backend pytest -q
```

## Commands

```bash
docker compose exec backend python -m app.cli create-user admin
docker compose exec backend python -m app.cli regen-thumbs
docker compose exec backend python -m app.cli vacuum-temp --apply
./scripts/backup.sh
```

`vacuum-temp` removes unfinished files in `media/temp` older than 48 hours.
It is not on cron. Without `--apply` it only prints the list.

Backup writes a Postgres dump and `media/air` to `/backup/mirror`
(`MIRROR_BACKUP_DIR` overrides the directory) and stores the certificates next to them.

## Certificate and port 80

Bootstrap leaves a self-signed certificate for whatever `DOMAIN` is set to in `.env`.
Production keeps the same paths: `nginx/certs/mirror.crt` and `mirror.key`,
with a certificate issued for that domain.

Compose publishes 8066 and 443. Both hit the same nginx. Remove `"8066:443"` if you
only want 443. The HTTP-to-HTTPS redirect is already in nginx. Publish it by adding
`"80:80"` to the `nginx` service.

## TV contract

The TV client is not in this repository. Point it at `https://<DOMAIN>:8066/`
or `https://<DOMAIN>/`. These requests are unauthenticated:

```
POST /api.php
{"action":"whatNow"}

→ {"type":"image"|"video","path":"media/8.mp4"}

GET  /media/8.mp4
GET  /media/8.jpg
GET  /media/default.jpg
HEAD /
```

The client builds the request as `serverURL + "/api.php"`, so it actually sends
`//api.php`. nginx passes it to the backend as `/api.php`.

`path` has no leading slash. The client appends it to `serverURL`, which ends with `/`.
If `path` did not change, the player does not restart.

## Import from the old Mirror

The command keeps file, event, and slot ids. An event whose same-day window
reaches 23:00 or later, and an event named `LOGO`, get `until_midnight`.
A second run skips ids that already exist.

```bash
docker compose run --rm --no-deps \
  -v "$PWD/legacy/media:/legacy-media:ro" \
  backend python -m app.cli import-legacy \
  --source-url "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/legacy" \
  --source-media /legacy-media

docker compose exec backend python -m app.cli regen-thumbs
```

A dump from the old Postgres 17 restores into local Postgres 16 after
`\restrict`, `\unrestrict`, and `SET transaction_timeout` are removed from the file.
