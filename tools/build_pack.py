#!/usr/bin/env python3
"""Build a versioned TinyFit release ZIP from the app repository assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


PACKS_FILE = Path(__file__).resolve().parents[1] / "packs" / "packs.json"
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="TinyFit app repository checkout")
    parser.add_argument("--pack-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    if not VERSION_RE.fullmatch(args.version):
        parser.error("--version must use MAJOR.MINOR.PATCH, for example 1.0.0")

    source = args.source_root.resolve()
    levels_path = source / "TinyFit/Resources/Levels/levels.json"
    regions_path = source / "TinyFit/Resources/Demo/level_regions.json"
    art_dir = source / "TinyFit/Resources/Demo/LevelArt"
    pieces_dir = source / "TinyFit/Resources/Demo/LevelPieces"
    for required in (levels_path, regions_path, art_dir, pieces_dir):
        if not required.exists():
            parser.error(f"Missing source path: {required}")

    pack_index = read_json(PACKS_FILE)
    pack = next((entry for entry in pack_index["packs"] if entry["id"] == args.pack_id), None)
    if pack is None:
        parser.error(f"Unknown pack ID: {args.pack_id}")

    all_levels = read_json(levels_path)["levels"]
    by_id = {level["id"]: level for level in all_levels}
    missing_ids = [level_id for level_id in pack["levelIds"] if level_id not in by_id]
    if missing_ids:
        parser.error(f"Pack references missing level IDs: {', '.join(missing_ids)}")
    selected = [by_id[level_id] for level_id in pack["levelIds"]]
    if any(level["theme"] != pack["theme"] for level in selected):
        parser.error("Pack theme does not match one or more selected levels")

    all_regions = read_json(regions_path)
    pack_regions: dict[str, list[dict]] = {}
    files: dict[str, Path] = {}
    for level in selected:
        target_asset = level["targetAsset"]
        regions = all_regions.get(target_asset)
        if regions is None or len(regions) != len(level["pieces"]):
            parser.error(f"Region count does not match piece count for {level['id']}")
        pack_regions[target_asset] = regions
        master_path = art_dir / f"{target_asset}.png"
        if not master_path.is_file():
            parser.error(f"Missing master artwork: {master_path}")
        files[f"LevelArt/{master_path.name}"] = master_path
        for region in regions:
            for suffix in (".png", "_ghost.png"):
                piece_path = pieces_dir / f"{region['asset']}{suffix}"
                if not piece_path.is_file():
                    parser.error(f"Missing piece artwork: {piece_path}")
                files[f"LevelPieces/{piece_path.name}"] = piece_path

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"tinyfit-{args.pack_id}-v{args.version}.zip"
    level_manifest = {"levels": selected}
    payloads: dict[str, bytes] = {
        "levels.json": (json.dumps(level_manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        "level_regions.json": (json.dumps(pack_regions, ensure_ascii=False, indent=2) + "\n").encode(),
    }
    file_entries = []
    for archive_path, source_path in sorted(files.items()):
        payloads[archive_path] = source_path.read_bytes()
        file_entries.append({"path": archive_path, "size": source_path.stat().st_size, "sha256": sha256(source_path)})
    for archive_path, data in payloads.items():
        if archive_path.endswith(".json"):
            file_entries.append({"path": archive_path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest = {
        "schemaVersion": 1,
        "packId": pack["id"],
        "version": args.version,
        "theme": pack["theme"],
        "sequence": pack["sequence"],
        "levelIds": [level["id"] for level in selected],
        "files": sorted(file_entries, key=lambda entry: entry["path"]),
    }
    payloads["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for archive_path, data in sorted(payloads.items()):
            archive.writestr(archive_path, data)

    print(f"Built {output} ({output.stat().st_size} bytes)")
    print(f"sha256 {sha256(output)}")


if __name__ == "__main__":
    main()
