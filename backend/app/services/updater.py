from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import APP_VERSION, GITHUB_RELEASE_URLS, PROJECT_ROOT

_SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")


def parse_version(tag: str) -> tuple[int, int, int]:
    cleaned = tag.strip().lstrip("vV")
    parts = re.findall(r"\d+", cleaned)
    nums = [int(p) for p in parts[:3]]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def is_trusted_github_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            return False
        host = (parsed.hostname or "").lower()
        return (
            host == "github.com"
            or host.endswith(".github.com")
            or host.endswith(".githubusercontent.com")
        )
    except Exception:
        return False


def cleanup_old_updates() -> None:
    dirs = [PROJECT_ROOT / "updates", Path(tempfile.gettempdir())]
    for d in dirs:
        try:
            if not d.exists():
                continue
            for f in d.glob("RS3GETracker_Update_*.exe"):
                try:
                    f.unlink(missing_ok=True)
                except Exception:
                    pass
        except Exception:
            pass


def _extract_expected_sha256(checksum_text: str, target_filename: str) -> str | None:
    lines = [ln.strip() for ln in checksum_text.splitlines() if ln.strip()]
    target_lower = Path(target_filename).name.lower()

    for line in lines:
        if line.lower().startswith("sha256") and target_lower in line.lower():
            if "=" in line:
                candidate = line.rsplit("=", 1)[-1].strip()
                if _SHA256_RE.match(candidate):
                    return candidate.upper()

        parts = line.split()
        if len(parts) >= 2 and _SHA256_RE.match(parts[0]):
            file_part = " ".join(parts[1:]).lstrip("* ").lower()
            if file_part == target_lower or file_part.endswith(target_lower):
                return parts[0].upper()
        elif len(lines) == 1 and len(parts) == 1 and _SHA256_RE.match(parts[0]):
            return parts[0].upper()

    return None


async def check_for_updates() -> dict[str, Any]:
    headers = {
        "User-Agent": f"RS3-GE-Tracker-Updater/{APP_VERSION}",
        "Accept": "application/vnd.github+json",
    }
    release_data: dict[str, Any] | None = None
    last_error: str | None = None

    async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
        for url in GITHUB_RELEASE_URLS:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("tag_name"):
                        release_data = data
                        break
                elif resp.status_code == 404:
                    continue
                else:
                    last_error = f"HTTP {resp.status_code}"
            except Exception as e:
                last_error = str(e)

    if not release_data:
        return {
            "update_available": False,
            "current_version": APP_VERSION,
            "latest_version": APP_VERSION,
            "download_url": None,
            "checksum_url": None,
            "asset_name": None,
            "release_url": "https://github.com/Dave-Debugs/RS3-GE-Tracker/releases",
            "error": last_error,
        }

    tag_name = str(release_data.get("tag_name") or APP_VERSION)
    latest_clean = tag_name.lstrip("vV")
    assets = release_data.get("assets") or []

    setup_asset = None
    fallback_exe = None
    checksum_asset = None

    for a in assets:
        name = str(a.get("name") or "")
        lower = name.lower()
        if lower == "checksum.txt":
            checksum_asset = a
        elif lower.endswith(".exe"):
            if "setup" in lower and setup_asset is None:
                setup_asset = a
            elif fallback_exe is None:
                fallback_exe = a

    chosen_exe = setup_asset or fallback_exe
    has_newer = parse_version(tag_name) > parse_version(APP_VERSION)

    return {
        "update_available": bool(has_newer and chosen_exe),
        "current_version": APP_VERSION,
        "latest_version": latest_clean,
        "download_url": chosen_exe.get("browser_download_url") if chosen_exe else None,
        "checksum_url": checksum_asset.get("browser_download_url") if checksum_asset else None,
        "asset_name": chosen_exe.get("name") if chosen_exe else None,
        "release_url": release_data.get("html_url") or "https://github.com/Dave-Debugs/RS3-GE-Tracker/releases",
        "error": None,
    }


async def download_and_apply_update(
    download_url: str,
    checksum_url: str | None = None,
    asset_name: str = "RS3-GE-Tracker-Setup.exe",
) -> dict[str, Any]:
    if not is_trusted_github_url(download_url):
        raise ValueError("Untrusted download URL")
    if checksum_url and not is_trusted_github_url(checksum_url):
        raise ValueError("Untrusted checksum URL")

    update_dir = PROJECT_ROOT / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    installer_path = update_dir / f"RS3GETracker_Update_{uuid.uuid4().hex}.exe"

    headers = {"User-Agent": f"RS3-GE-Tracker-Updater/{APP_VERSION}"}
    expected_hash: str | None = None

    try:
        async with httpx.AsyncClient(headers=headers, timeout=180.0, follow_redirects=True) as client:
            if checksum_url:
                chk_resp = await client.get(checksum_url)
                chk_resp.raise_for_status()
                expected_hash = _extract_expected_sha256(chk_resp.text, asset_name)
                if not expected_hash:
                    raise ValueError("Checksum file did not contain a valid SHA-256 hash")

            sha256 = hashlib.sha256()
            async with client.stream("GET", download_url) as resp:
                resp.raise_for_status()
                with open(installer_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        sha256.update(chunk)

        actual_hash = sha256.hexdigest().upper()
        if expected_hash and actual_hash != expected_hash:
            installer_path.unlink(missing_ok=True)
            raise ValueError("SHA-256 checksum mismatch; update aborted")

        is_setup = "setup" in asset_name.lower()
        args = [str(installer_path)]
        if is_setup:
            args.extend(["/SILENT", "/NORESTART"])

        subprocess.Popen(args, cwd=str(update_dir))

        return {
            "ok": True,
            "applied": bool(getattr(sys, "frozen", False)),
            "started": True,
            "message": "Installer launched! RS3 GE Tracker will now update.",
            "installer_path": str(installer_path),
            "sha256": actual_hash,
        }
    except Exception:
        installer_path.unlink(missing_ok=True)
        raise
