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

## Offline and prefetch plan

Only `w01-p01` is bundled for offline play at first install. The app should prefetch the next 25-level pack near the end of the active pack and keep the active and next packs cached. Players finish all 50 levels in a world before the next world opens. Previously completed packs can be downloaded again if evicted; progress is stored separately from artwork.

## Content status

Source-completeness fields track approved authoring inputs and remain separate from binary availability. `publishedPacks` lists the versioned assets currently available to the app; the three first world packs are published from the reviewed app artwork. A release can be downloadable while additional source approval or authoring work remains.

The TinyFit app's world/pack loader reads this catalog for downloadable content. The existing pilot releases and their catalog are preserved under `archive/pilot-30/`.

Artwork must be copied from approved masters and split only along the visible seams in those masters. The pack builder does not generate seams or infer piece boundaries.

## Artwork delivery format

Keep approved PNGs as source artwork. Content pack ZIPs use WebP delivery images:
masters at Q10, pieces and ghosts at Q5, and maps at Q30. Encode with
`-alpha_q 100 -exact` and verify that every decoded alpha mask matches its PNG
source. If both formats exist beside a source asset, pack builders must prefer
WebP and include only that format in the ZIP. The app reads WebP and retains PNG
support for older packs.

## Build a complete pack

The private app repository is the source for level definitions and artwork. Build from a local checkout after all 25 level masters, piece images, and region records are present:

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
