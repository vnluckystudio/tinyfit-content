# TinyFit Event Content

This directory is a self-contained public content site. Copy its contents to
the root of a dedicated GitHub repository when a publishing repository is
chosen. The repository should contain only content intended to be public.
There is no dashboard, admin login, token, private event, or server-side time
authority.

## Configure GitHub Pages

1. Create a dedicated repository for event content and copy this directory's
   contents into its root, including `.github/workflows/deploy-event-pages.yml`.
2. In the repository settings, set **Pages → Build and deployment → GitHub
   Actions**. The workflow validates content and deploys the site after pushes
   to `main` or a manual run.
3. Set the app's Xcode build setting `EVENT_BASE_URL` to the Pages root URL,
   including any project subpath and a trailing slash. For example:
   `https://vnluckystudio.github.io/tinyfit-content/`. TinyFit's checked-in value is a safe
   example placeholder; it is not a live event site.
4. Build the app with that public URL. No token or secret belongs in the app.

The workflow in this folder is intentionally portable to a separate content
repository. No repository was created and nothing was deployed for this task.

## Add an event

From the content repository root:

```sh
python3 scripts/event_content.py init-event \
  --id spring-2027 \
  --title "Spring Puzzle Event" \
  --description "A new seasonal puzzle." \
  --starts-at 2027-04-01T00:00:00Z \
  --ends-at 2027-04-15T00:00:00Z
```

The command creates `events/<id>/v1/event.json`, copies a sample cover into
`events/<id>/v1/cover.webp`, and adds an upcoming entry to `events.json`. Replace
the cover and complete the manifest with one or more puzzle entries before
publishing. Run:

```sh
python3 scripts/event_content.py validate
```

Each puzzle entry points to one `level.json`, one `level_regions.json`, a
TinyFit runtime recipe, and a checksummed `assets` list. Files are relative to
that event's `event.json` directory, so GitHub Pages project subpaths resolve
correctly. Keep each puzzle's files under its own versioned folder, such as
`puzzles/<puzzle-id>/v1/` (the sample uses `puzzles/sleepy-cat-picnic/`). The
puzzle's assets include the clean 720×720 WebP master, seam mask, per-piece
masks, level definition, regions, and recipe.
TinyFit uses its current mask-based runtime to build the seamed board, pieces,
and ghosts; a single image is not a playable puzzle.

The sample event `spring-picnic-2027` uses an existing TinyFit Meow Meadow
artwork master and World Card. It is scheduled for April 2027 and contains a
playable six-piece sample puzzle.

## Version and publish safely

- Treat published version folders as immutable. For a changed puzzle, copy its
  assets into `puzzles/<puzzle-id>/v2/`, update its paths/checksums and
  `contentVersion` in the manifest. A topology change gets a new puzzle
  content version. Local completion records are scoped to
  `(eventId, puzzleId, contentVersion)`.
- For any changed event manifest or schedule, publish a new event folder such
  as `events/<event-id>/v2/` (including its cover and manifest), update the
  catalog's `coverUrl`, `manifestUrl` and `contentVersion`, and match that
  version in `event.json`. Keep each new puzzle's files in its own immutable
  versioned folder. Do not replace bytes at an already published URL.
- Increment the catalog `contentVersion` whenever `events.json` changes.
- First publish the new version's assets and event manifest. Confirm their
  Pages URLs are live, then publish the `events.json` update that points to
  them. This prevents clients from observing a catalog entry before its
  content exists.
- To finish an event, set a future or past UTC `endsAt` in both catalog and
  manifest, increment the event version, validate, and publish the manifest
  before the catalog update. Keep ended events in `events.json` to retain their
  history and progress view.

Event times use the device clock and are displayed in the device's local
timezone. Users can change their device clock; this offline first release does
not prevent or detect that. An event not yet started is still public on Pages
and must not contain secret content.

## App behavior

- The event catalog and event manifests are fetched when opening the event
  area/details, with disk-cached metadata shown first where available.
- Covers are downloaded lazily. Puzzle assets are downloaded only after a
  player selects a puzzle, validated against size and SHA-256, then atomically
  committed to Application Support.
- A downloaded, valid puzzle can be played offline while its event is active.
  Expired events remain visible but do not start new rounds. A round already
  open can finish and save progress after the end time.
- Asset URLs and cache paths are versioned. Do not replace files at an existing
  version path.
- A project GitHub Pages site is public. Do not upload private or unreleased
  puzzle answers that must remain confidential.
