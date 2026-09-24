# Mirror

On-air screen for one Android TV. The admin plans files, daily events, and a schedule.
Every 5 seconds the TV calls `whatNow` and shows one file fullscreen.

The UI is Ukrainian. The TV client is not in this repository.
Its contract below is frozen.

## Decisions

- Admin: Vue 3, Vite, Tailwind.
- One admin. No roles and no signup. `create-user` creates the account.
- A media id is a `serial` and is never reused after delete.
- Time is `Europe/Kyiv` everywhere, including the calendar in the browser.
- `DOMAIN` in `.env` is the public hostname. Local bootstrap writes a self-signed certificate for it.

## 1. On air

Three layers, highest priority first:

1. **Event** — a daily `TIME` window. If several are active, the one with the later `start_at` wins.
2. **Schedule** — a one-off slot at a `timestamptz`. It has no duration.
   The screen keeps the latest slot that has already started today in Kyiv, until the next slot or midnight.
3. **`media/default.jpg`**.

Only `media.status = ready` is shown. Pending and `failed` are skipped.
The previous ready slot from today plays instead of the default image.

`whatNow` and `GET /api/now` load every event and only the slots of the current Kyiv day,
from midnight through the end of that day. Past slots stay in the table.
They are calendar history, not the broadcast. The schedule is never purged automatically.

### Events: from–to

The window is a clock range: `09:00–09:03` or `19:00–23:59`.

- `end_at == 23:59` sets `until_midnight`. The event stays active from `start_at` until 24:00,
  even when the stored `duration` is shorter. It does not continue after midnight,
  and yesterday's schedule does not carry into the new day.
- Otherwise `duration = end − start`. A window that crosses midnight is allowed.
- Overlapping windows return 409.

An evening block that ends at 23:59 therefore runs until the end of the day.
A short window such as 09:00–09:03 sits on top of the schedule, then the day's slot returns.

## 2. TV contract

The TV base URL is `https://<DOMAIN>/` or `https://<DOMAIN>:8066/` when that port is published.
`<DOMAIN>` is the `DOMAIN` value from `.env`.

```
POST {base}/api.php
Content-Type: application/json
{"action": "whatNow"}

→ {"type": "image"|"video", "path": "media/8.mp4"}

GET  {base}/media/8.mp4
GET  {base}/media/8.jpg
GET  {base}/media/default.jpg
HEAD {base}/     → 200
```

- `path` has no leading slash. The client builds `serverURL + path`.
- `serverURL` ends with `/`.
- `whatNow` and on-air files need no authentication.
- Port 8066 is TLS for the TV. Port 443 is the same site for people.
- Compose publishes 8066 and 443. The redirect from port 80 is already in nginx.
  Publishing port 80 means adding `"80:80"`.
- `/api.php` accepts only `whatNow`.

The TV does not restart the player when `path` is unchanged.
`/screen` reads the same payload from `GET /api/now` and draws it with `object-fit: contain`.

## 3. Stack

| Service | Role |
|---------|------|
| nginx | TLS on 443 and 8066, SPA, `/api`, `/api.php`, tus, on-air files |
| backend | FastAPI, JWT, tus hooks, alembic on startup |
| worker | Same image, Celery, concurrency=1 |
| tusd | Resumable uploads |
| postgres 16 | Data |
| redis | Broker |
| frontend | One-shot build copied into the `frontend_build` volume |

nginx resolves `backend` and `tusd` through Docker DNS (`resolver 127.0.0.11`)
on every request, so recreating the backend does not leave nginx on a stale IP.

```
/media/
├── default.jpg
├── temp/          tusd, {id}.incoming and {id}.work.* while processing
├── air/           {id}.mp4 | {id}.jpg   public
├── thumbs/        {id}.webp             cookie
└── posters/       {id}.jpg              cookie
```

## 4. Data

### users

`id uuid`, `username unique`, `password_hash argon2id`, `created_at`.

### media

`id serial` is the on-air URL. `name unique`. `type` is `image` or `video`.
`status` is `pending`, `processing`, `converting`, `ready`, or `failed`.
`progress` is 0–100. Also `mime_type`, `size_bytes`, `duration_sec`, `width`, `height`,
`thumb_path`, `poster_path`, and `uploaded_by` → users.

Delete takes `FOR UPDATE` on the media row, removes schedule slots and events
that point at it, then the row, then the files under `air/`, thumbs, posters,
`temp/{id}.incoming`, and `temp/{id}.work.*`.
There is no 409 for "this file is in use".
A worker still encoding that id does not publish it to `air/`.

### events

`name unique`, `start_at time unique`, `duration` between 0 and 24 hours,
`until_midnight bool default false`, `media_id` ON DELETE RESTRICT.

### schedule

`media_id` ON DELETE RESTRICT, `start_at timestamptz unique`.
A naive ISO timestamp from the admin is read as Kyiv.
Past slots are not deleted. The calendar shows them when the month changes.

Migrations: `0001_initial`, `0002` (duration up to 24 hours), `0003` (`until_midnight`).

## 5. Upload

```
browser --tus--> tusd --pre-create/pre-finish--> backend
  pre-create: JWT, MIME allowlist, unique name
  pre-finish: media row pending, temp → temp/{id}.incoming, celery delay
worker process_media:
  magic MIME; jpeg is copied, png/webp go through Pillow
  video is copied when it is mp4 + h264 + aac (or no audio)
  otherwise ffmpeg libx264 veryfast crf 18, aac or -an, +faststart
  all of that lands in temp/{id}.work.*, not in air/
  publish under FOR UPDATE:
    row gone — delete the work files and exit without a retry
    otherwise os.replace into air/ + thumb + poster, status=ready, commit, then drop incoming
  during ffmpeg the row is checked once a second; if it is gone, that ffmpeg process is stopped
```

Allowed MIME types: jpeg, png, webp, mp4, webm, quicktime.

Celery uses `acks_late`, `reject_on_worker_lost`, prefetch 1, and up to 3 retries,
with a soft limit of 30 minutes and a hard limit of 35.
A bad MIME type, or a job with neither incoming nor an air file, becomes `failed`
immediately, and the work files plus any partial air file are removed.
On worker start, stuck `pending`, `processing`, and `converting` rows are recovered:
incoming present means requeue; incoming gone and a complete file in `air/` means `ready`;
otherwise `failed`. A partial file is never moved into `air/`.

## 6. API

JWT is accepted as a Bearer header and as the HttpOnly cookie `mirror_token`.
TTL is 7 days, SameSite=Strict, Secure.

```
POST /api/auth/login   {username, password} → {token, user}
POST /api/auth/logout
GET  /api/auth/me
GET  /api/auth/verify          nginx auth_request, 204/401

GET    /api/media
GET    /api/media/{id}
DELETE /api/media/{id}         also removes slots and events that use the file

GET    /api/events
POST   /api/events             {name, start_at, end_at, media_id}
                               end_at 23:59 → until_midnight
DELETE /api/events/{id}

GET    /api/schedule           ?from=&to= or ?date=   (Kyiv dates)
POST   /api/schedule           {media_id, start_at}
DELETE /api/schedule/{id}

GET    /api/now                same payload as whatNow
GET    /api/health
POST   /api.php                whatNow, no session
POST   /api/hooks/tusd         internal, ?secret=
```

An event response also includes `end_at`, `duration`, and `until_midnight`.

## 7. UI

Dark theme. The calendar fills the screen. Days are `Europe/Kyiv`.
Today is a 36×36 circle with the same gradient as the header and the slot count.
A 4px stripe runs down the left edge of that cell, gradient from top to bottom.
The cell background matches the neighbouring days.

Login is a centered card. The title is only «Mirror».
«Логін» and «Пароль» sit inside the fields: centered while empty,
and smaller at the top when the field is focused or filled.

Errors on login, files, events, schedule, and `/screen` are a plaque
with an icon, a red border, and a dark red fill.
An unsupported file says «Тип … не підтримується».
Allowed types are JPEG, PNG, WebP, MP4, WebM, and MOV.

The header centers a segment «Файли | Події | Екран» with icons.
There is no product name and no username. «Вийти» is on the right.

Modals:

- Title centered, × on the right, «Назад» on the left of a form.
- Events and schedule open on a list, with a full-width «Додати» under it.
  The form replaces the list and returns to the updated list after save.
- An event has a name, from, to, and a file picker with a preview. 23:59 means until the end of the day.
- A schedule slot has a time and the same picker. It holds until the next slot or midnight.
- Files open on a list, with «Додати» under it. The form is a name plus a drop zone.
  After save the list is back, with preview, progress, and delete.
- The file picker is a list with thumbnails, not a `<select>`.
- Delete is another step in the same modal, not `alert` or `confirm`.
  «Назад» and «Скасувати» delete nothing. «Видалити» is red.
  - Unused file: «Видалити „назва“?».
  - A file that is in use: «використовується і буде видалений з усіх місць, де він стоїть».
    No list of places and no counts. Its slots and events are removed with it.
  - Event: «Видалити подію „назва“?».
  - Slot: «Видалити слот „файл“ о ГГ:ХХ?».
- Deleting a slot or a file reloads the visible month immediately.

`/screen` draws the image or video with `object-fit: contain`. Video is muted and loops.
It polls `/api/now` every 5 seconds.

An existing slot is not edited. Delete it and add another.

## 8. Import from the old database

```
python -m app.cli import-legacy \
  --source-url postgresql://... \
  --source-media /legacy-media
python -m app.cli regen-thumbs
```

Ids are preserved. `until_midnight` is set when the same-day window reaches
23:00 or later, or when the event is named `LOGO`.
A second run skips ids that already exist. The exact commands are in [ops.md](ops.md).

## 9. Out of scope

- The Android client.
- Several screens, playlists, SSO, roles.
- UUIDs instead of serial media ids.

## 10. Checks

1. `bootstrap` starts the stack, runs alembic, and creates the user.
2. Login sets a cookie for 7 days.
3. `POST /api.php {"action":"whatNow"}` returns `{type, path}` with no auth.
4. `GET /media/{id}.ext` and `default.jpg` need no auth. `HEAD /` returns 200.
5. 09:00–09:03 is active at 09:01 and not at 09:03.
6. 19:00–23:59 (`until_midnight`) is active at 23:30 and does not fall through to the morning slot.
7. At 00:05 yesterday's schedule is not playing.
8. A schedule slot holds until the next slot of that day or until midnight.
9. Overlapping events return 409. Deleting a file that is in use removes its slots and events.
10. PNG and WebM land in `air/` as jpg and mp4.
11. The calendar and slots use Europe/Kyiv.
12. Ports 8066 and 443 serve the same TLS certificate.
13. Recreating the backend does not leave a permanent 502.
14. After a restart the worker picks up unfinished `incoming` files.
