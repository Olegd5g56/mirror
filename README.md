# Mirror

On-air screen for one Android TV. The admin schedules files and daily events.
Every 5 seconds the TV asks what to show and plays a single file fullscreen.

## Run

Docker, Docker Compose v2, and OpenSSL.

```bash
./scripts/bootstrap.sh
```

The script writes `.env` with generated secrets, creates a self-signed certificate
for the `DOMAIN` in that file, starts the stack, and asks for the first admin password.
Set `DOMAIN` in `.env` before the first run. `TZ` is the clock used for the schedule.
Nothing else is tied to a particular hostname.

Open `https://<DOMAIN>:8066/` or `https://<DOMAIN>/`.
Both ports serve the same site. The `8066` mapping is only there for a TV that
was configured with that port. Delete the line in `docker-compose.yml` if you do not need it.
If the name is not in DNS yet, point it at this machine in `/etc/hosts`.

The browser will warn about the self-signed certificate. For production, replace
`nginx/certs/mirror.crt` and `nginx/certs/mirror.key` with a certificate for your
`DOMAIN`, then run `docker compose up -d nginx`. The filenames stay `mirror.crt`
and `mirror.key`; only the hostname inside the certificate changes.

Playback, API, and UI: [docs/spec.md](docs/spec.md).
Rebuilds, backups, and the old-database import: [docs/ops.md](docs/ops.md).
