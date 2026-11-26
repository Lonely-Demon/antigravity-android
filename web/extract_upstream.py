#!/usr/bin/env python3
"""
web/extract_upstream.py - Extracts the embedded upstream Jetski Web bundle
directly from the language_server binary into a destination directory.
"""
import io
import os
import shutil
import struct
import sys
import zipfile


def find_embedded_web_zip(bin_path: str) -> bytes:
    with open(bin_path, "rb") as f:
        data = f.read()

    # Anchor on an asset unique to the embedded Jetski Web bundle.
    for marker in (b"antigravityCascadeDone.mp3", b"compiled_tailwind.css"):
        pos = data.find(marker)
        if pos == -1:
            continue
        eocd = data.find(b"PK\x05\x06", pos)
        while eocd != -1:
            if eocd + 22 <= len(data):
                disk, cd_disk, entries_disk, entries_total, cd_size, cd_offset, comment_len = (
                    struct.unpack_from("<HHHHIIH", data, eocd + 4)
                )
                if disk == 0 and cd_disk == 0 and entries_disk == entries_total and entries_total > 10:
                    zip_start = eocd - cd_size - cd_offset
                    if zip_start >= 0 and data[zip_start:zip_start + 4] == b"PK\x03\x04":
                        return data[zip_start:eocd + 22 + comment_len]
            eocd = data.find(b"PK\x05\x06", eocd + 4)

    raise RuntimeError(f"Embedded web bundle ZIP not found in: {bin_path}")


def extract_upstream_web(bin_path: str, dest_dir: str) -> int:
    zbytes = find_embedded_web_zip(bin_path)
    zf = zipfile.ZipFile(io.BytesIO(zbytes))

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    dest_real = os.path.realpath(dest_dir)
    count = 0
    for info in zf.infolist():
        if info.is_dir():
            continue
        rel = info.filename.lstrip("/")
        if not rel:
            continue
        out_path = os.path.realpath(os.path.join(dest_real, rel))
        if not out_path.startswith(dest_real + os.sep):
            raise RuntimeError(f"Unsafe zip entry path: {info.filename}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with zf.open(info, "r") as src, open(out_path, "wb") as dst:
            shutil.copyfileobj(src, dst)
        count += 1

    for required in ("index.html", "main.js"):
        if not os.path.isfile(os.path.join(dest_real, required)):
            raise RuntimeError(f"Upstream web bundle missing required file: {required}")

    return count


def main() -> int:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <language_server_bin> <dest_web_dir>", file=sys.stderr)
        return 2
    bin_path, dest_dir = sys.argv[1], sys.argv[2]
    count = extract_upstream_web(bin_path, dest_dir)
    print(f"[web-extract] Extracted {count} upstream web files -> {dest_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
