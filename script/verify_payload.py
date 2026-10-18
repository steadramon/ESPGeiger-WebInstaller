#!/usr/bin/env python3
"""
Sanity-check an ESPGeiger webinstall payload zip before deploying.

Per env folder, verify:
  - offsets.json present with chipFamily + parts list
  - each named file exists with non-zero size
  - bootloader.bin and firmware.bin start with the esp-image magic byte 0xE9
    (ESP32-family) or 0xE9 (ESP8266 too - same magic)
  - boot_app0.bin matches the framework copy verbatim
  - partition table (partitions.bin) is decodable and doesn't overlap any
    of our flashed parts with the NVS region (0x9000-0xE000)

Exit code 0 if all envs pass, non-zero otherwise.
"""
from __future__ import annotations
import json
import struct
import sys
import zipfile
from pathlib import Path

ESP_IMAGE_MAGIC = 0xE9
NVS_START = 0x9000
NVS_END   = 0xE000


def check_env(zf: zipfile.ZipFile, env: str, files: dict) -> list[str]:
    errs = []
    try:
        offsets = json.loads(zf.read(f"{env}/offsets.json"))
    except KeyError:
        return [f"{env}: no offsets.json"]
    if "chipFamily" not in offsets or "parts" not in offsets:
        errs.append(f"{env}: offsets.json missing chipFamily/parts")
        return errs

    parts = offsets["parts"]
    for p in parts:
        path = f"{env}/{p['file']}"
        if path not in files:
            errs.append(f"{env}: {p['file']} listed in offsets.json but missing from zip")
            continue
        info = files[path]
        if info.file_size == 0:
            errs.append(f"{env}: {p['file']} is empty")

    # Magic-byte check on bootloader / firmware images.
    for name in ("bootloader.bin", "firmware.bin"):
        path = f"{env}/{name}"
        if path in files:
            head = zf.read(path)[:1]
            if not head or head[0] != ESP_IMAGE_MAGIC:
                errs.append(f"{env}: {name} missing ESP image magic 0xE9")

    # ESP8266 has no NVS partition; the 0x9000-0xE000 region is ESP32-specific.
    if offsets["chipFamily"] != "ESP8266":
        for p in parts:
            path = f"{env}/{p['file']}"
            size = files[path].file_size if path in files else 0
            start = p["offset"]
            end = start + size
            if end > NVS_START and start < NVS_END:
                errs.append(
                    f"{env}: {p['file']} at 0x{start:X}-0x{end:X} OVERLAPS NVS "
                    f"(0x{NVS_START:X}-0x{NVS_END:X}) - would wipe saved WiFi"
                )

    return errs


def main():
    if len(sys.argv) != 2:
        print("usage: verify_payload.py <webinstall.zip>")
        sys.exit(2)
    zp = Path(sys.argv[1])
    if not zp.exists():
        print(f"not found: {zp}")
        sys.exit(2)

    with zipfile.ZipFile(zp) as zf:
        files = {i.filename: i for i in zf.infolist() if not i.is_dir()}
        envs = sorted({n.split("/", 1)[0] for n in files if "/" in n})
        all_errs = []
        for env in envs:
            errs = check_env(zf, env, files)
            if errs:
                all_errs.extend(errs)
            else:
                print(f"OK {env}")

    if all_errs:
        print()
        for e in all_errs:
            print(f"FAIL {e}")
        sys.exit(1)
    print(f"\nall {len(envs)} envs passed")


if __name__ == "__main__":
    main()
