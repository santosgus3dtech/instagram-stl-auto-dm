from __future__ import annotations

import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


class FollowAuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class InstagramLists:
    followers: dict[str, str]
    following: dict[str, str]


def ensure_audit_dirs(data_dir: Path) -> None:
    (data_dir / "inbox").mkdir(parents=True, exist_ok=True)
    (data_dir / "uploads").mkdir(parents=True, exist_ok=True)
    (data_dir / "snapshots").mkdir(parents=True, exist_ok=True)


def safe_upload_name(filename: str) -> str:
    clean = Path(filename or "instagram-export.zip").name
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", clean).strip("._")
    if not clean:
        clean = "instagram-export.zip"
    if not clean.lower().endswith(".zip"):
        clean = f"{clean}.zip"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{clean}"


def save_upload(data_dir: Path, filename: str, body: bytes) -> Path:
    ensure_audit_dirs(data_dir)
    if not body:
        raise FollowAuditError("Arquivo vazio.")
    path = data_dir / "uploads" / safe_upload_name(filename)
    path.write_bytes(body)
    return path


def import_latest_from_inbox(data_dir: Path) -> dict[str, Any]:
    ensure_audit_dirs(data_dir)
    latest = latest_snapshot(data_dir)
    imported_key = latest.get("source_key") if latest else None

    candidates = sorted(
        (data_dir / "inbox").glob("*.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return latest or empty_snapshot()

    newest = candidates[0]
    newest_key = source_key(newest)
    if imported_key == newest_key:
        return latest or empty_snapshot()
    return import_export_zip(data_dir, newest)


def import_export_zip(data_dir: Path, zip_path: Path) -> dict[str, Any]:
    ensure_audit_dirs(data_dir)
    lists = parse_instagram_export(zip_path)
    if not lists.followers and not lists.following:
        raise FollowAuditError(
            "Nao encontrei followers/following nesse ZIP. Exporte em JSON com 'Seguidores e seguindo'."
        )

    previous = latest_snapshot(data_dir)
    snapshot = build_snapshot(lists, zip_path, previous)
    snapshot_path = data_dir / "snapshots" / f"{snapshot['generated_at_slug']}.json"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=True, indent=2), encoding="utf-8")
    shutil.copyfile(snapshot_path, data_dir / "latest.json")
    return public_snapshot(snapshot)


def parse_instagram_export(zip_path: Path) -> InstagramLists:
    if not zipfile.is_zipfile(zip_path):
        raise FollowAuditError("O arquivo enviado nao parece ser um ZIP valido.")

    followers: dict[str, str] = {}
    following: dict[str, str] = {}

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".json"):
                continue
            basename = Path(info.filename).name.lower()
            bucket: dict[str, str] | None = None
            if basename.startswith("followers"):
                bucket = followers
            elif "following" in basename and "followers" not in basename:
                bucket = following
            if bucket is None:
                continue

            try:
                payload = json.loads(archive.read(info).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise FollowAuditError(f"JSON invalido dentro do ZIP: {info.filename}") from exc

            for username in usernames_from_json(payload):
                normalized = normalize_username(username)
                if normalized:
                    bucket.setdefault(normalized, username)

    return InstagramLists(followers=followers, following=following)


def usernames_from_json(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        string_list_data = payload.get("string_list_data")
        if isinstance(string_list_data, list):
            for item in string_list_data:
                if isinstance(item, dict):
                    value = item.get("value")
                    if isinstance(value, str) and is_probable_username(value):
                        found.append(value)
        for value in payload.values():
            found.extend(usernames_from_json(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(usernames_from_json(item))
    return found


def is_probable_username(value: str) -> bool:
    return bool(USERNAME_RE.match(value.strip().lstrip("@")))


def normalize_username(value: str) -> str:
    normalized = value.strip().lstrip("@").casefold()
    return normalized if is_probable_username(normalized) else ""


def build_snapshot(
    lists: InstagramLists,
    zip_path: Path,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    followers = set(lists.followers)
    following = set(lists.following)
    previous_followers = set((previous or {}).get("followers", []))
    previous_following = set((previous or {}).get("following", []))
    generated_at = datetime.now(timezone.utc)

    not_following_back = sorted(following - followers)
    fans = sorted(followers - following)
    new_followers = sorted(followers - previous_followers) if previous_followers else []
    lost_followers = sorted(previous_followers - followers) if previous_followers else []
    newly_following = sorted(following - previous_following) if previous_following else []
    unfollowed_by_you = sorted(previous_following - following) if previous_following else []

    return {
        "generated_at": generated_at.isoformat(),
        "generated_at_slug": generated_at.strftime("%Y%m%dT%H%M%SZ"),
        "source_file": zip_path.name,
        "source_key": source_key(zip_path),
        "followers_count": len(followers),
        "following_count": len(following),
        "not_following_back_count": len(not_following_back),
        "fans_count": len(fans),
        "new_followers_count": len(new_followers),
        "lost_followers_count": len(lost_followers),
        "newly_following_count": len(newly_following),
        "unfollowed_by_you_count": len(unfollowed_by_you),
        "followers": sorted(followers),
        "following": sorted(following),
        "not_following_back": usernames_with_display(not_following_back, lists.following),
        "fans": usernames_with_display(fans, lists.followers),
        "new_followers": usernames_with_display(new_followers, lists.followers),
        "lost_followers": usernames_with_display(lost_followers, previous_display(previous, "followers")),
        "newly_following": usernames_with_display(newly_following, lists.following),
        "unfollowed_by_you": usernames_with_display(
            unfollowed_by_you,
            previous_display(previous, "following"),
        ),
    }


def usernames_with_display(usernames: list[str], display_map: dict[str, str]) -> list[dict[str, str]]:
    return [{"username": display_map.get(username, username)} for username in usernames]


def previous_display(previous: dict[str, Any] | None, key: str) -> dict[str, str]:
    values = (previous or {}).get(key, [])
    if not isinstance(values, list):
        return {}
    return {str(item): str(item) for item in values}


def latest_snapshot(data_dir: Path) -> dict[str, Any] | None:
    path = data_dir / "latest.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def empty_snapshot() -> dict[str, Any]:
    return {
        "ready": False,
        "message": "Envie um ZIP JSON exportado pela Central de Contas.",
        "followers_count": 0,
        "following_count": 0,
        "not_following_back_count": 0,
        "fans_count": 0,
        "new_followers_count": 0,
        "lost_followers_count": 0,
        "not_following_back": [],
        "fans": [],
        "new_followers": [],
        "lost_followers": [],
    }


def public_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    public = dict(snapshot)
    public["ready"] = True
    public.pop("followers", None)
    public.pop("following", None)
    public.pop("source_key", None)
    public.pop("generated_at_slug", None)
    return public


def source_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{int(stat.st_mtime)}"
