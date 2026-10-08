# TinyFit world content

Public catalog and GitHub Release distribution for TinyFit's world-based puzzle content. The game is planned as 20 worlds × 50 levels. Each world has two packs of 25 levels and stays thematically self-contained.

## Layout

- `catalog/catalog.json` is the world and pack index used by clients.
- `worlds/<order>-<slug>/world.json` describes one world.
- `worlds/<order>-<slug>/packs/01/pack.json` and `02/pack.json` define its two level ranges.
- `migration/legacy-level-ids.json` maps current pilot progress IDs to the new stable IDs.
- `archive/pilot-30/` preserves the previous five-pack catalog and definitions. The existing release tags remain available as history.
- Binary artwork is distributed as versioned ZIP assets on GitHub Releases, not committed to Git.

Pack IDs are `w01-p01` through `w20-p02`; level IDs are stable (`w01-001`–`w01-050`, etc.). Release tags use `<pack-id>-v<version>`, for example `w01-p01-v1.0.0`.

## Startup download and cache plan

The app has no bundled puzzle or map artwork. On first launch it downloads `w01-p01` (levels 1–25 plus Meow Meadow map artwork), then keeps the pack cached for offline play. The next 25-level pack can be prefetched near the end of the active pack; players finish all 50 levels in a world before the next world opens. Previously completed packs can be downloaded again if cleaned; progress is stored separately from artwork.

## Content status

The 25-level `w01-p01` Meow Meadow startup pack is published as `w01-p01-v1.0.2`, including ten map pages and two cloud transition images. The 25-artwork `w01-p02` follow-up pack remains published as `w01-p02-v1.0.0`; the public catalog lists both for client downloads.

The TinyFit app downloads the startup pack on first launch, reads the published-pack catalog, verifies and installs release archives, and prefetches Meow Meadow Pack 02 when the player reaches level 20. The remaining worlds stay planned until the Meow Meadow flow is confirmed. Existing pilot releases and their catalog are preserved under `archive/pilot-30/`.

Artwork must be copied from approved masters and split only along the visible seams in those masters. The pack builder does not generate seams or infer piece boundaries.

## Build a complete pack

The private app repository is the source for level definitions and artwork. New packs are built from `TinyFit/Resources/Artwork/Worlds/<world>/Packs/<pack>`; legacy pilot content remains a fallback. Build from a local checkout after all 25 level masters, piece images, and region records are present:

```sh
python3 tools/build_pack.py \
  --source-root /path/to/tinyfit \
  --pack-id w01-p01 \
  --version 1.0.0 \
  --output-dir dist
```

The tool refuses to package a partial 25-level pack. Review the generated ZIP and its SHA-256, then publish it as a public GitHub Release asset. Update the pack metadata and `catalog/catalog.json` only after the release upload succeeds. Never overwrite an existing release asset; publish a new version.

## Pilot ROI

Use release download counts as an initial demand signal. App telemetry is needed to measure checksum/install success, offline play, pack completion, and how often players continue to the next pack. Use those results before producing the remaining artwork for all 1,000 levels.
