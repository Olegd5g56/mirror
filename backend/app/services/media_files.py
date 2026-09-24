"""Шляхи файлів медіа і прибирання з диска.

Публічні імена з'являються лише після успішної обробки. Поки воркер працює,
результат лежить у temp/{id}.work.* — nginx цей каталог не віддає.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def incoming_path(root: Path, media_id: int) -> Path:
    return root / "temp" / f"{media_id}.incoming"


def work_video_path(root: Path, media_id: int) -> Path:
    return root / "temp" / f"{media_id}.work.mp4"


def work_image_path(root: Path, media_id: int) -> Path:
    return root / "temp" / f"{media_id}.work.jpg"


def work_thumb_path(root: Path, media_id: int) -> Path:
    return root / "temp" / f"{media_id}.work.webp"


def work_poster_path(root: Path, media_id: int) -> Path:
    return root / "temp" / f"{media_id}.work-poster.jpg"


def work_paths(root: Path, media_id: int) -> list[Path]:
    return [
        work_video_path(root, media_id),
        work_image_path(root, media_id),
        work_thumb_path(root, media_id),
        work_poster_path(root, media_id),
    ]


def air_paths(root: Path, media_id: int) -> list[Path]:
    return [
        root / "air" / f"{media_id}.mp4",
        root / "air" / f"{media_id}.jpg",
    ]


def public_paths(root: Path, media_id: int) -> list[Path]:
    return [
        *air_paths(root, media_id),
        root / "thumbs" / f"{media_id}.webp",
        root / "posters" / f"{media_id}.jpg",
    ]


def safe_under_root(root: Path, rel: str | None) -> Path | None:
    """Відносний шлях всередині media root. Абсолютні і з .. відкидаємо."""
    if not rel:
        return None
    parts = Path(rel).parts
    if not parts or rel.startswith(("/", "\\")) or ".." in parts:
        return None
    root_real = root.resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root_real)
    except ValueError:
        return None
    return candidate


def unlink_quiet(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def remove_artifacts(
    root: Path,
    media_id: int,
    *,
    public: bool = True,
    incoming: bool = True,
    work: bool = True,
    extra: tuple[str | None, ...] = (),
) -> None:
    paths: list[Path] = []
    if incoming:
        paths.append(incoming_path(root, media_id))
    if work:
        paths.extend(work_paths(root, media_id))
    if public:
        paths.extend(public_paths(root, media_id))
    for rel in extra:
        under = safe_under_root(root, rel)
        if under is not None:
            paths.append(under)
    for path in paths:
        unlink_quiet(path)


def start_action(
    *,
    row_exists: bool,
    ready: bool,
    incoming: bool,
    air: bool,
) -> str:
    """Що робити на старті задачі.

    cancel — рядка вже немає, дискові сліди треба прибрати і не ретраїти.
    done — файл уже опублікований, повторна доставка задачі нічого не кодує.
    mark_ready — цілий air є, а incoming уже знято (обрив після публікації).
    fail — обробляти ні з чого.
    process — incoming на місці, можна кодувати.
    """
    if not row_exists:
        return "cancel"
    if ready and air:
        return "done"
    if not incoming and air:
        return "mark_ready"
    if not incoming:
        return "fail"
    return "process"


def stop_process(process: subprocess.Popen, *, timeout: float = 10) -> None:
    """Зупинити дочірній процес, не чіпаючи сам воркер."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)
