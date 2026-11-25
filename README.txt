# Concord Aldon RFMS Inventory Catalog

The public catalog is served by Cloudflare Pages. Inventory and photos are stored in Cloudflare R2 and are published by the private desktop tools. GitHub stores the website source and deploys code changes; inventory and photos are not part of the Pages build.

## Package contents

- `update_inventory.py` — filter and validate RFMS exports, back up the previous inventory, and publish the approved inventory and export timestamp to Cloudflare.
- `update_inventory_github.py` — preserved copy of the prior GitHub-publishing updater for reference or rollback; it still pushes inventory to GitHub when run.
- `cloudflare_configure.py` — creates the private local upload settings and a random upload token.
- `Update Inventory.bat` — unchanged Windows launcher.
- `Update Inventory - Copy.bat` — existing alternate launcher for the preserved GitHub updater, when present in this checkout.
- `cloudflare_publish.py` — shared private upload helper used by the desktop tools.
- `cloudflare/photo_sync_r2.py` — photo sync tool for the Desktop Photo Sync folder.
- `functions/[[path]].js` — public R2 reads and token-protected upload endpoints.
- `scripts/build_site.py` — builds a Pages folder containing only `index.html`.
- `cloudflare/README.md` — Cloudflare resource setup and publishing notes.

## Install

1. Complete the Cloudflare setup in `cloudflare/README.md` before publishing from the desktop tools.
2. In GitHub Desktop, open the `catalog-test` repository and choose **Repository → Show in Explorer**.
3. Keep a copy of your current updater and photo-sync script until the first Cloudflare update and photo sync succeed.
4. Install `cloudflare_publish.py` in the repository root. Replace the repository's `update_inventory.py` with this version.
5. Copy `cloudflare_publish.py` and `cloudflare/photo_sync_r2.py` into the Desktop Photo Sync folder, replacing its `photo_sync.py` with `photo_sync_r2.py` renamed to `photo_sync.py`. Keep the existing `photo_sync_config.json` and `Run Photo Sync.bat`.
6. Configure the local Cloudflare publishing settings as described in `cloudflare/README.md`. The private token must not be committed.
7. Commit/push the code and README changes through GitHub Desktop. Do not commit `inventory.csv` or photos as part of the Cloudflare deployment setup; Pages builds only `index.html` into `dist/`.
8. Upload the current photos and inventory to R2 after the Pages project is deployed and its R2 binding and secret are configured.

The Windows inventory launcher continues to run `update_inventory.py` (the Cloudflare version). To use the preserved GitHub workflow temporarily, run `py -3 update_inventory_github.py` manually instead; that version pushes inventory to GitHub.

## Daily use

1. Export the inventory from RFMS.
2. Copy the RFMS CSV export into the repository's `incoming` folder.
3. Double-click `Update Inventory.bat`.
4. Review the selected export and row counts. The updater warns if the filtered inventory has fewer than half the current catalog rows.
5. At the final prompt, type `Y` only when you want to publish the approved data to the live Cloudflare catalog. Type `N` to leave the live catalog unchanged.
6. After a successful upload (or verified no-change run), the source export moves into `incoming\processed`.

## Filtering rules

- Only exact `GOLD` and `SILVER` styles are included as Type `Vinyl`.
- Exact `CT` styles are included as Type `Carpet Tile`; their Color value is kept as the RFMS color code.
- Only exact four-character styles matching `Z` plus three letters or digits are included as Type `Carpet`.
- `ZL93` and `ZL94` are explicitly excluded, even though they otherwise match the four-character format.
- Longer values are excluded in full; they are never shortened to a valid prefix. For example, `ZL93 RUG MAT`, `ZG91 A1C2`, and `ZL95 RUG MAT` are excluded.
- Style matching ignores capitalization and leading/trailing or repeated spaces, as in the current updater. Spaces within a longer style still make it a non-match.

## Output fields and RFMS mapping

| Catalog column | RFMS export column |
|---|---|
| Roll Number | Roll # |
| Style | Style |
| Color | Color |
| Width | Width |
| Amt Avail | Avail Length |
| Type | Generated from Style (`Vinyl`, `Carpet`, or `Carpet Tile`) |

`Amt Avail` remains the catalog output heading and comes from RFMS `Avail Length`. Carpet and Vinyl values are feet; Carpet Tile values are yards. Carpet Tile rows have blank Roll Number and Width fields, and the website aggregates them by Style and Color without showing roll details. `Qty Avail` is not used. The website shows each entry's product type and labels totals in feet or yards accordingly. The catalog does not display prices.

## Inventory date

The public `inventory_date.txt` is updated from the RFMS export's file **Last Modified** timestamp, converted to the local time zone. The updater does not change the tracked local inventory files or push inventory data to GitHub.

## Safeguards and Git behavior

- The RFMS source export is never edited.
- The updater requires the repository to be on branch `main` and refuses to proceed if changes are already staged.
- It validates required headers, nonblank roll numbers, and numeric available lengths.
- It refuses an empty result and warns if the new inventory is less than half the current row count.
- It asks before publishing inventory.
- It saves a local backup and the Pages Function also backs up the prior inventory and date label in R2.
- If inventory and timestamp are unchanged, it skips the upload.
- The source export is archived only after a successful upload or verified no-change run.
- Keep `incoming/` and `inventory_backups/` ignored by Git.
