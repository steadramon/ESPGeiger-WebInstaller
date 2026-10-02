#!/usr/bin/env python3
"""
Sync this static site's bin/ tree from an ESPGeiger release.

For each release we expect a `ESPGeiger_webinstall.<version>.zip` asset
containing one folder per env, each holding bootloader/partitions/boot_app0/
firmware bins (ESP32) or just firmware.bin (ESP8266) plus an offsets.json
naming the chipFamily and per-part offsets.

This script reads bin/_groups.json (which env belongs to which webinstaller
group) and writes one manifest.json per group with the actual offsets, plus
copies the bin files into the group's directory so esp-web-tools can fetch
them at install time.

Usage:
  script/sync_release.py <version>
  script/sync_release.py <version> --zip /path/to/local.zip
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BIN_DIR = REPO / "bin"
GROUPS_FILE = BIN_DIR / "_groups.json"

DEFAULT_OPTS = {
    "new_install_prompt_erase": True,
    "new_install_improv_wait_time": 10,
}

RELEASE_URL_TMPL = (
    "https://github.com/steadramon/ESPGeiger/releases/download/"
    "v{version}/ESPGeiger_webinstall.{version}.zip"
)


def fetch_zip(version: str, local):
    if local:
        return local
    url = RELEASE_URL_TMPL.format(version=version)
    tmp = Path(tempfile.mkdtemp()) / f"webinstall.{version}.zip"
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, tmp)
    return tmp


def extract(zip_path: Path, dest: Path) -> Path:
    print(f"extracting {zip_path.name}")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return dest


def build_group(group: dict, payload_root: Path, version: str) -> bool:
    group_dir = BIN_DIR / group["path"]
    group_dir.mkdir(parents=True, exist_ok=True)

    # Wipe any previously-deployed per-env subfolders so stale envs don't
    # linger when _groups.json drops a chipFamily.
    for child in group_dir.iterdir():
        if child.is_dir() and child.name not in {"oled"}:
            shutil.rmtree(child)
        elif child.is_file() and child.suffix == ".bin":
            child.unlink()

    builds = []
    missing = []
    for chip, env in group["envs"].items():
        src = payload_root / env
        offsets_file = src / "offsets.json"
        if not offsets_file.exists():
            missing.append(env)
            continue
        offsets = json.loads(offsets_file.read_text())
        # Copy the env's payload into the group's directory under its env
        # name (keeps multi-env groups tidy and avoids filename collisions).
        env_dest = group_dir / env
        env_dest.mkdir(parents=True, exist_ok=True)
        for part in offsets["parts"]:
            shutil.copy2(src / part["file"], env_dest / part["file"])
        # Version on each path so a new release always invalidates browser cache
        # for the firmware bins (the bins themselves overwrite at stable URLs).
        builds.append({
            "chipFamily": offsets["chipFamily"],
            "parts": [{"path": f"{env}/{p['file']}?v={version}", "offset": p["offset"]}
                      for p in offsets["parts"]],
        })

    if not builds:
        print(f"  {group['path']}: no envs available, skipping")
        return False
    if missing:
        print(f"  {group['path']}: partial - {len(builds)} present, missing {missing}")

    manifest = {
        "name": group["name"],
        "version": version,
        **DEFAULT_OPTS,
        "builds": builds,
    }
    out = group_dir / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  {group['path']}: {len(builds)} chip families")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="release version (e.g. 0.12.0)")
    ap.add_argument("--zip", type=Path, help="local zip to use instead of downloading")
    args = ap.parse_args()

    groups = json.loads(GROUPS_FILE.read_text())["groups"]

    work = Path(tempfile.mkdtemp(prefix="webinstall_sync_"))
    try:
        zip_path = fetch_zip(args.version, args.zip)
        payload = extract(zip_path, work / "payload")
        for g in groups:
            build_group(g, payload, args.version)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # Update index.htm: bump the visible "ESPGeiger vX.Y.Z" string AND replace
    # bare {version} placeholders (used for download links + the cache-buster
    # query on the manifest URL).
    idx = REPO / "index.htm"
    if idx.exists():
        text = idx.read_text()
        new = re.sub(r"(ESPGeiger v)[0-9.]+(?:-[a-z0-9.]+)?",
                     rf"\g<1>{args.version}", text)
        new = new.replace("{version}", args.version)
        if new != text:
            idx.write_text(new)
            print(f"updated index.htm to v{args.version}")

    print("done")


if __name__ == "__main__":
    main()
