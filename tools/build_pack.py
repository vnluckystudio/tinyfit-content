#!/usr/bin/env python3
"""Build one complete 25-level TinyFit world pack from the private app checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_pack(pack_id: str) -> tuple[Path, dict, dict]:
    for path in (ROOT / "worlds").rglob("pack.json"):
        pack = read_json(path)
        if pack.get("id") == pack_id:
            world = read_json(path.parents[2] / "world.json")
            return path, pack, world
    raise ValueError(f"Unknown pack ID: {pack_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="TinyFit app repository checkout")
    parser.add_argument("--pack-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()

    if not VERSION_RE.fullmatch(args.version):
        parser.error("--version must use MAJOR.MINOR.PATCH, for example 1.0.0")

    try:
        pack_path, pack, world = find_pack(args.pack_id)
    except ValueError as error:
        parser.error(str(error))

    source = args.source_root.resolve()
    pack_source = source / "TinyFit/Resources/Artwork/Worlds" / f"{world['order']:02d}-{world['slug']}" / "Packs" / f"{pack['packNumber']:02d}"
    if pack_source.is_dir():
        levels_path = pack_source / "levels.json"
        regions_path = pack_source / "level_regions.json"
        art_dir = pack_source / "LevelArt"
        pieces_dir = pack_source / "LevelPieces"
    else:
        levels_path = source / "TinyFit/Resources/Levels/levels.json"
        regions_path = source / "TinyFit/Resources/Demo/level_regions.json"
        art_dir = source / "TinyFit/Resources/Demo/LevelArt"
        pieces_dir = source / "TinyFit/Resources/Demo/LevelPieces"
    for required in (levels_path, regions_path, art_dir, pieces_dir):
        if not required.exists():
            parser.error(f"Missing source path: {required}")

    old_to_new = read_json(ROOT / "migration/legacy-level-ids.json")["mapping"]
    new_to_old = {new_id: old_id for old_id, new_id in old_to_new.items()}
    all_levels = read_json(levels_path)["levels"]
    by_id = {level["id"]: level for level in all_levels}
    selected = []
    missing_levels = []
    for new_id in pack["levelIds"]:
        source_id = new_to_old.get(new_id, new_id)
        level = by_id.get(source_id) or by_id.get(new_id)
        if level is None:
            missing_levels.append(new_id)
        else:
            selected.append(level)
    if missing_levels:
        parser.error(
            f"Pack {args.pack_id} is incomplete: {len(missing_levels)} source levels are missing "
            f"({', '.join(missing_levels[:8])}{'...' if len(missing_levels) > 8 else ''}). "
            "Only complete 25-level packs can be published."
        )
    if len(selected) != 25:
        parser.error(f"Pack {args.pack_id} must contain exactly 25 levels; found {len(selected)}")
    if len({level["id"] for level in selected}) != 25:
        parser.error(f"Pack {args.pack_id} contains duplicate source level IDs")
    if any(level["theme"] != world["theme"] for level in selected):
        parser.error(f"Pack {args.pack_id} mixes level themes; a world must remain thematically coherent")

    all_regions = read_json(regions_path)
    pack_regions: dict[str, list[dict]] = {}
    files: dict[str, Path] = {}
    if pack["id"] == "w01-p01":
        map_source = source / "TinyFit/Resources/HomeMap"
        map_names = [*(f"meow-meadow-map-page-{number:02d}.png" for number in range(1, 11)),
                     "meow-meadow-cloud-left.png", "meow-meadow-cloud-right.png"]
        for name in map_names:
            map_path = map_source / name
            if not map_path.is_file():
                parser.error(f"Missing starter map artwork: {map_path}")
            files[f"HomeMap/{name}"] = map_path

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

    # Rewrite only the level IDs in the archive; every other gameplay field remains source-authored.
    packaged_levels = []
    source_to_new = {old_id: new_id for old_id, new_id in new_to_old.items()}
    for level in selected:
        item = dict(level)
        item["id"] = source_to_new.get(level["id"], level["id"])
        packaged_levels.append(item)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"tinyfit-{args.pack_id}-v{args.version}.zip"
    payloads: dict[str, bytes] = {
        "levels.json": (json.dumps({"levels": packaged_levels}, ensure_ascii=False, indent=2) + "\n").encode(),
        "level_regions.json": (json.dumps(pack_regions, ensure_ascii=False, indent=2) + "\n").encode(),
    }
    entries = []
    for archive_path, source_path in sorted(files.items()):
        data = source_path.read_bytes()
        payloads[archive_path] = data
        entries.append({"path": archive_path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    for archive_path, data in payloads.items():
        if archive_path.endswith(".json"):
            entries.append({"path": archive_path, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    manifest = {
        "schemaVersion": 1,
        "packId": pack["id"],
        "worldId": world["id"],
        "packNumber": pack["packNumber"],
        "version": args.version,
        "levelRange": pack["levelRange"],
        "levelIds": pack["levelIds"],
        "files": sorted(entries, key=lambda entry: entry["path"]),
    }
    payloads["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for archive_path, data in sorted(payloads.items()):
            archive.writestr(archive_path, data)

    print(f"Built {output} ({output.stat().st_size} bytes)")
    print(f"sha256 {sha256(output)}")


if __name__ == "__main__":
    main()
