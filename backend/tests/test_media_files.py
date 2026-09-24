import subprocess
import time
from pathlib import Path

from app.services.media_files import (
    air_paths,
    incoming_path,
    public_paths,
    remove_artifacts,
    safe_under_root,
    start_action,
    stop_process,
    work_paths,
)


def test_work_files_stay_out_of_air(tmp_path: Path):
    work = work_paths(tmp_path, 7)
    air = air_paths(tmp_path, 7)
    assert all(path.parent == tmp_path / "temp" for path in work)
    assert all(path.parent == tmp_path / "air" for path in air)
    assert incoming_path(tmp_path, 7) == tmp_path / "temp" / "7.incoming"
    assert set(public_paths(tmp_path, 7)) >= set(air)


def test_remove_artifacts_drops_public_and_scratch(tmp_path: Path):
    paths = [
        *public_paths(tmp_path, 3),
        *work_paths(tmp_path, 3),
        incoming_path(tmp_path, 3),
    ]
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    remove_artifacts(tmp_path, 3)
    assert not any(path.exists() for path in paths)


def test_remove_artifacts_can_keep_public_file(tmp_path: Path):
    air = air_paths(tmp_path, 4)[0]
    work = work_paths(tmp_path, 4)[0]
    incoming = incoming_path(tmp_path, 4)
    for path in (air, work, incoming):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    remove_artifacts(tmp_path, 4, public=False)
    assert air.exists()
    assert not work.exists()
    assert not incoming.exists()


def test_safe_under_root_rejects_escape(tmp_path: Path):
    assert safe_under_root(tmp_path, "thumbs/1.webp") == (tmp_path / "thumbs" / "1.webp").resolve()
    assert safe_under_root(tmp_path, "../etc/passwd") is None
    assert safe_under_root(tmp_path, "/etc/passwd") is None
    assert safe_under_root(tmp_path, None) is None


def test_cancel_wins_over_a_leftover_air_file():
    assert start_action(row_exists=False, ready=False, incoming=True, air=True) == "cancel"
    assert start_action(row_exists=False, ready=False, incoming=False, air=True) == "cancel"


def test_start_action_publish_and_retry_cases():
    assert start_action(row_exists=True, ready=True, incoming=True, air=True) == "done"
    assert start_action(row_exists=True, ready=False, incoming=False, air=True) == "mark_ready"
    assert start_action(row_exists=True, ready=False, incoming=False, air=False) == "fail"
    assert start_action(row_exists=True, ready=False, incoming=True, air=False) == "process"


def test_stop_process_kills_child():
    process = subprocess.Popen(["sleep", "30"])
    started = time.monotonic()
    stop_process(process, timeout=2)
    assert process.poll() is not None
    assert time.monotonic() - started < 5
