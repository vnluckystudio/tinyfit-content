# TinyFit content packs

Public distribution repository for TinyFit's downloadable puzzle packs. Pack artwork is published as versioned GitHub Release assets; binary artwork is intentionally not committed to Git history.

## Pilot

The pilot contains the 30 current levels, grouped into five theme packs of six levels each:

| Pack | Theme | Levels |
| --- | --- | --- |
| `cats-01` | Cats | `cat_001`–`cat_006` |
| `food-01` | Food | `food_001`–`food_006` |
| `ocean-01` | Ocean | `ocean_001`–`ocean_006` |
| `space-01` | Space | `space_001`–`space_006` |
| `vehicles-01` | Vehicles | `vehicle_001`–`vehicle_006` |

Pack IDs and level IDs are stable. A correction to a published pack increments its semantic version and gets a new release tag; an existing release asset is never replaced.

## Build and publish

The app source repository is private, so pack archives are built locally from a checkout of both repositories. No app credential or GitHub token is included in the app or in the pack.

```sh
python3 tools/build_pack.py \
  --source-root /path/to/tinyfit \
  --pack-id cats-01 \
  --version 1.0.0 \
  --output-dir dist
```

The tool validates source assets, writes a deterministic ZIP, and emits its SHA-256. Review the archive, then publish it as a GitHub Release asset:

```sh
gh release create cats-01-v1.0.0 \
  dist/tinyfit-cats-01-v1.0.0.zip \
  --repo vnluckystudio/tinyfit-content \
  --title 'Cats pack 01 v1.0.0' \
  --notes 'TinyFit pilot content pack: cats_001–cats_006.'
```

After publication, update `catalog/catalog.json` with the release URL, byte size, and SHA-256. The catalog is the app-facing index. Pack assets are public and do not require a password.

## Archive layout

Each release ZIP contains a `manifest.json`, the selected levels and region definitions, their master artwork, and only the generated piece/ghost artwork referenced by those levels:

```text
manifest.json
levels.json
level_regions.json
LevelArt/*.png
LevelPieces/*.png
```

Artwork must retain the master dimensions and seam-derived piece boundaries from the source project. This pack pipeline copies existing approved assets; it does not generate or infer seams.

## ROI for the pilot

Use GitHub's per-release download counts as a first-party distribution signal. Once the app downloads packs, measure install success and the share of players who proceed to another pack before funding production of the remaining 970 levels. The release download count alone does not measure in-app completion or conversion.
