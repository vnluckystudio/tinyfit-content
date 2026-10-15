#!/usr/bin/env python3
"""Create event scaffolds and validate TinyFit GitHub Pages content."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import struct
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_instant(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label}: expected an ISO 8601 string with timezone")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError(f"{label}: invalid ISO 8601 date: {value}") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label}: timezone is required (UTC Z is recommended)")
    return parsed


def relative_file(root: Path, base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise ValueError(f"{label}: must be a relative URL/path")
    parts = PurePosixPath(value).parts
    if any(part in {"", ".", ".."} for part in parts) or not re.fullmatch(r"[A-Za-z0-9._/-]+", value):
        raise ValueError(f"{label}: unsafe relative path {value!r}")
    path = (base / Path(*parts)).resolve()
    if root.resolve() not in path.parents:
        raise ValueError(f"{label}: path escapes content root")
    if not path.is_file():
        raise ValueError(f"{label}: referenced file does not exist: {path.relative_to(root.resolve())}")
    return path


def verify_png(path: Path, label: str) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"{label}: invalid PNG file")
    return struct.unpack(">II", data[16:24])


def validate_puzzle(root: Path, event_root: Path, puzzle: dict[str, Any], seen_ids: set[str]) -> None:
    puzzle_id = puzzle.get("id")
    if not isinstance(puzzle_id, str) or not ID_PATTERN.fullmatch(puzzle_id):
        raise ValueError("puzzle id must use lowercase letters, digits, '-' or '_'")
    if puzzle_id in seen_ids:
        raise ValueError(f"duplicate puzzle id: {puzzle_id}")
    seen_ids.add(puzzle_id)
    if not isinstance(puzzle.get("title"), str) or not puzzle["title"].strip():
        raise ValueError(f"{puzzle_id}: title is required")
    if not isinstance(puzzle.get("sortOrder"), int):
        raise ValueError(f"{puzzle_id}: sortOrder must be an integer")
    if not isinstance(puzzle.get("contentVersion"), str) or not puzzle["contentVersion"].strip():
        raise ValueError(f"{puzzle_id}: contentVersion is required")

    records = puzzle.get("assets")
    if not isinstance(records, list) or not records:
        raise ValueError(f"{puzzle_id}: assets must be a non-empty array")
    assets: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{puzzle_id}: each asset record must be an object")
        path_value = record.get("path")
        if not isinstance(path_value, str) or path_value in assets:
            raise ValueError(f"{puzzle_id}: invalid or duplicate asset path {path_value!r}")
        path = relative_file(root, event_root, path_value, f"{puzzle_id}.assets.path")
        size = record.get("sizeBytes")
        digest = record.get("sha256")
        if not isinstance(size, int) or size <= 0 or path.stat().st_size != size:
            raise ValueError(f"{puzzle_id}: byte size mismatch for {path_value}")
        if not isinstance(digest, str) or not HEX_PATTERN.fullmatch(digest):
            raise ValueError(f"{puzzle_id}: invalid SHA-256 for {path_value}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"{puzzle_id}: SHA-256 mismatch for {path_value}")
        assets[path_value] = record

    level_url = puzzle.get("levelUrl")
    regions_url = puzzle.get("regionsUrl")
    recipe_url = puzzle.get("recipeUrl")
    for field, value in (("levelUrl", level_url), ("regionsUrl", regions_url), ("recipeUrl", recipe_url)):
        if value not in assets:
            raise ValueError(f"{puzzle_id}: {field} must also appear in assets with a checksum")
    level_doc = read_json(relative_file(root, event_root, level_url, f"{puzzle_id}.levelUrl"))
    regions = read_json(relative_file(root, event_root, regions_url, f"{puzzle_id}.regionsUrl"))
    recipe = read_json(relative_file(root, event_root, recipe_url, f"{puzzle_id}.recipeUrl"))

    levels = level_doc.get("levels")
    if not isinstance(levels, list) or len(levels) != 1 or not isinstance(levels[0], dict):
        raise ValueError(f"{puzzle_id}: level data must contain exactly one TinyFit level")
    level = levels[0]
    target = level.get("targetAsset")
    pieces = level.get("pieces")
    piece_count = level.get("pieceCount")
    if not isinstance(target, str) or not isinstance(pieces, list) or not pieces:
        raise ValueError(f"{puzzle_id}: level is missing targetAsset or pieces")
    if not isinstance(piece_count, int) or piece_count != len(pieces):
        raise ValueError(f"{puzzle_id}: pieceCount does not match the piece definitions")
    piece_ids = [piece.get("id") for piece in pieces if isinstance(piece, dict)]
    if len(piece_ids) != len(pieces) or len(set(piece_ids)) != len(pieces):
        raise ValueError(f"{puzzle_id}: piece IDs must be unique")
    for piece in pieces:
        if any(not isinstance(piece.get(key), (int, float)) or not 0 <= piece[key] <= 1 for key in ("targetX", "targetY")):
            raise ValueError(f"{puzzle_id}: each piece needs normalized targetX and targetY coordinates")

    target_regions = regions.get(target)
    if not isinstance(target_regions, list) or len(target_regions) != piece_count:
        raise ValueError(f"{puzzle_id}: level_regions is missing one region per piece")
    for region in target_regions:
        if not isinstance(region, dict) or not isinstance(region.get("asset"), str):
            raise ValueError(f"{puzzle_id}: invalid level_regions entry")
        if any(not isinstance(region.get(key), (int, float)) for key in ("sourceX", "sourceY", "regionX", "regionY", "regionWidth", "regionHeight")):
            raise ValueError(f"{puzzle_id}: invalid region coordinates")

    if recipe.get("version") != 1 or recipe.get("width") != 720 or recipe.get("height") != 720:
        raise ValueError(f"{puzzle_id}: runtime recipe must use supported 720x720 version 1 format")
    recipe_pieces = recipe.get("pieces")
    region_assets = {region["asset"] for region in target_regions}
    if not isinstance(recipe_pieces, list) or {piece.get("asset") for piece in recipe_pieces if isinstance(piece, dict)} != region_assets:
        raise ValueError(f"{puzzle_id}: recipe piece assets do not match TinyFit regions")
    master = recipe.get("masterAsset")
    seam_mask = recipe.get("seamMask")
    if not isinstance(master, str) or not isinstance(seam_mask, str):
        raise ValueError(f"{puzzle_id}: recipe needs masterAsset and seamMask")
    referenced = {f"LevelArt/{master}.webp", f"LevelMasks/{seam_mask}"}
    masks = [seam_mask]
    for piece in recipe_pieces:
        mask = piece.get("mask")
        if not isinstance(mask, str):
            raise ValueError(f"{puzzle_id}: recipe piece is missing its mask")
        referenced.add(f"LevelMasks/{mask}")
        masks.append(mask)
        for key in ("x", "y", "width", "height"):
            if not isinstance(piece.get(key), int) or piece[key] < 0:
                raise ValueError(f"{puzzle_id}: invalid recipe piece {key}")
    puzzle_directory = str(PurePosixPath(level_url).parent)
    if str(PurePosixPath(regions_url).parent) != puzzle_directory or not recipe_url.startswith(puzzle_directory + "/"):
        raise ValueError(f"{puzzle_id}: level, regions and recipe files must share a versioned puzzle directory")
    referenced = {level_url, regions_url, recipe_url} | {f"{puzzle_directory}/{path}" for path in referenced}
    missing = referenced - set(assets)
    if missing:
        raise ValueError(f"{puzzle_id}: missing checksummed runtime files: {', '.join(sorted(missing))}")
    image = relative_file(root, event_root, f"{puzzle_directory}/LevelArt/{master}.webp", f"{puzzle_id}.master").read_bytes()
    if image[:4] != b"RIFF" or image[8:12] != b"WEBP":
        raise ValueError(f"{puzzle_id}: master image must be WebP")
    for mask in masks:
        width, height = verify_png(relative_file(root, event_root, f"{puzzle_directory}/LevelMasks/{mask}", f"{puzzle_id}.mask"), f"{puzzle_id}.mask")
        if width <= 0 or height <= 0:
            raise ValueError(f"{puzzle_id}: empty mask {mask}")


def validate(root: Path = ROOT) -> list[str]:
    catalog = read_json(root / "events.json")
    if catalog.get("schemaVersion") != 1 or not isinstance(catalog.get("contentVersion"), str):
        raise ValueError("events.json: unsupported or incomplete schema")
    events = catalog.get("events")
    if not isinstance(events, list):
        raise ValueError("events.json: events must be an array")
    seen: set[str] = set()
    report: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("events.json: each event must be an object")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not ID_PATTERN.fullmatch(event_id) or event_id in seen:
            raise ValueError(f"events.json: invalid or duplicate event id {event_id!r}")
        seen.add(event_id)
        for field in ("title", "description", "contentVersion"):
            if not isinstance(event.get(field), str) or not event[field].strip():
                raise ValueError(f"{event_id}: {field} is required")
        minimum_version = event.get("minAppVersion")
        if minimum_version is not None and (
            not isinstance(minimum_version, str)
            or not re.fullmatch(r"\d+(?:\.\d+)*", minimum_version)
        ):
            raise ValueError(f"{event_id}: minAppVersion must be a dotted numeric version")
        starts = parse_instant(event.get("startsAt"), f"{event_id}.startsAt")
        ends = parse_instant(event.get("endsAt"), f"{event_id}.endsAt")
        if ends <= starts:
            raise ValueError(f"{event_id}: endsAt must be after startsAt")
        if not isinstance(event.get("sortOrder"), int):
            raise ValueError(f"{event_id}: sortOrder must be an integer")
        cover = relative_file(root, root, event.get("coverUrl"), f"{event_id}.coverUrl")
        cover_data = cover.read_bytes()
        if cover.suffix.lower() != ".webp" or cover_data[:4] != b"RIFF" or cover_data[8:12] != b"WEBP":
            raise ValueError(f"{event_id}: cover must be WebP")
        manifest_path = relative_file(root, root, event.get("manifestUrl"), f"{event_id}.manifestUrl")
        manifest = read_json(manifest_path)
        if manifest.get("schemaVersion") != 1 or manifest.get("eventId") != event_id:
            raise ValueError(f"{event_id}: manifest schema or eventId mismatch")
        if manifest.get("contentVersion") != event.get("contentVersion"):
            raise ValueError(f"{event_id}: catalog and manifest contentVersion must match")
        if manifest.get("startsAt") != event.get("startsAt") or manifest.get("endsAt") != event.get("endsAt"):
            raise ValueError(f"{event_id}: catalog and manifest schedule must match")
        puzzles = manifest.get("puzzles")
        if not isinstance(puzzles, list) or not puzzles:
            raise ValueError(f"{event_id}: add at least one puzzle before publishing")
        puzzle_ids: set[str] = set()
        sort_orders: set[int] = set()
        event_root = manifest_path.parent
        for puzzle in puzzles:
            if not isinstance(puzzle, dict):
                raise ValueError(f"{event_id}: each puzzle must be an object")
            validate_puzzle(root, event_root, puzzle, puzzle_ids)
            order = puzzle["sortOrder"]
            if order in sort_orders:
                raise ValueError(f"{event_id}: duplicate puzzle sortOrder {order}")
            sort_orders.add(order)
        report.append(f"{event_id}: {len(puzzles)} puzzle(s), {cover.relative_to(root.resolve())}")
    return report


def increment_version(value: str) -> str:
    match = re.fullmatch(r"(.*?)(\d+)", value)
    return f"{match.group(1)}{int(match.group(2)) + 1}" if match else f"{value}-2"


def create_scaffold(event_id: str, title: str, description: str, starts_at: str, ends_at: str, root: Path = ROOT) -> Path:
    if not ID_PATTERN.fullmatch(event_id):
        raise ValueError("event id must use lowercase letters, digits, '-' or '_'")
    starts, ends = parse_instant(starts_at, "startsAt"), parse_instant(ends_at, "endsAt")
    if ends <= starts or not title.strip() or not description.strip():
        raise ValueError("provide a title, description, and a valid event date range")
    catalog_path = root / "events.json"
    catalog = read_json(catalog_path)
    current_events = catalog.get("events", [])
    if any(event.get("id") == event_id for event in current_events if isinstance(event, dict)):
        raise ValueError(f"event id already exists: {event_id}")
    event_root = root / "events" / event_id / "v1"
    event_root.mkdir(parents=True, exist_ok=False)
    shutil.copy2(root / "templates" / "cover.webp", event_root / "cover.webp")
    event_entry = {
        "id": event_id, "title": title, "description": description,
        "startsAt": starts_at, "endsAt": ends_at,
        "coverUrl": f"events/{event_id}/v1/cover.webp",
        "manifestUrl": f"events/{event_id}/v1/event.json",
        "contentVersion": "1", "sortOrder": len(current_events) + 1, "minAppVersion": "1.0.2",
    }
    write_json(event_root / "event.json", {
        "schemaVersion": 1, "contentVersion": "1", "eventId": event_id,
        "title": title, "description": description, "startsAt": starts_at, "endsAt": ends_at,
        "puzzles": [],
    })
    write_json(catalog_path, {
        **catalog, "contentVersion": increment_version(catalog["contentVersion"]),
        "events": [*current_events, event_entry],
    })
    return event_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init-event", help="create a versioned event scaffold and catalog entry")
    init.add_argument("--id", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--description", required=True)
    init.add_argument("--starts-at", required=True, help="ISO 8601 with timezone, for example 2027-04-01T00:00:00Z")
    init.add_argument("--ends-at", required=True)
    subparsers.add_parser("validate", help="validate catalog, manifests, puzzle definitions and asset checksums")
    args = parser.parse_args()
    try:
        if args.command == "init-event":
            path = create_scaffold(args.id, args.title, args.description, args.starts_at, args.ends_at)
            print(f"Created {path.relative_to(ROOT)}. Add at least one puzzle, then run validate.")
        else:
            print("Event content validation passed:")
            for line in validate():
                print(f"- {line}")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f"Event content validation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
