# Concord Aldon RFMS Inventory Updater

This package updates the inventory data used by the `catalog-test` catalog. The updater keeps the existing validation, backup, confirmation, timestamp, commit, push, and export-archiving workflow.

## Package contents

- `update_inventory.py` — filter, validate, back up, update, commit, and publish the inventory.
- `Update Inventory.bat` — unchanged Windows launcher.
- `README.md` and `README.txt` — these instructions.
- `test_filter.py` — isolated synthetic-data check; it does not access Git or change catalog files.
- `synthetic_rfms.csv` — sample RFMS export used by the check.

## Install

1. In GitHub Desktop, open the `catalog-test` repository.
2. Choose **Repository → Show in Explorer**.
3. Make a copy of the current `update_inventory.py` somewhere safe.
4. Copy this package's `update_inventory.py` into the repository's root folder and replace the existing updater.
5. Replace the repository's `README.txt` with this package's `README.txt`. You may also replace `README.md` with this package's `README.md` if you want the online project instructions to match.
6. Keep the existing `Update Inventory.bat`; the included launcher is identical and optional to copy.
7. Do not replace `index.html`, `inventory.csv`, `inventory_date.txt`, `.gitignore`, photos, or photo-sync files with package files. The package contains no catalog page or photo files.
8. To install the updater change in GitHub, inspect the changed files in GitHub Desktop and commit/push them when you are ready. This install step is separate from running an inventory update.

## Synthetic test

Run this before using the updater with a real export. It writes only a temporary CSV under your system temporary folder and never calls Git, pushes, or changes the catalog.

1. Open PowerShell in the package folder.
2. Run `py -3 test_filter.py` (or `python test_filter.py` if the Python launcher is unavailable).
3. Confirm the final line says `PASS`.

The sample has four included rows and excluded examples for ZL93, ZL94, `ZL93 RUG MAT`, `ZG91 A1C2`, and another longer Z style. It also sets `Qty Avail` and `Avail Length` to different values; the test verifies `Amt Avail` is populated from `Avail Length`.

## Daily use

1. Export the inventory from RFMS.
2. Copy the RFMS CSV export into the repository's `incoming` folder.
3. Double-click `Update Inventory.bat`.
4. Review the selected export and row counts. The updater warns if the filtered inventory has fewer than half the current catalog rows.
5. At the final prompt, type `Y` only when you want to replace the inventory and allow the updater's existing commit-and-push workflow to publish it. Type `N` to leave the live files unchanged.
6. After a successful push (or verified no-change run), the source export moves into `incoming\processed`.

## Filtering rules

- Only exact `GOLD` and `SILVER` styles are included as Type `Vinyl`.
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
| Type | Generated from Style (`Vinyl` or `Carpet`) |

`Amt Avail` remains the catalog output heading and contains feet from `Avail Length`. `Qty Avail` (yardage) is not used.

## Inventory date

`inventory_date.txt` is written from the RFMS export's file **Last Modified** timestamp, converted to the local time zone. This preserves the existing behavior that displays the export's modified date/time rather than the local copy time.

## Safeguards and Git behavior

- The RFMS source export is never edited.
- The updater requires the repository to be on branch `main` and refuses to proceed if changes are already staged.
- It validates required headers, nonblank roll numbers, and numeric available lengths.
- It refuses an empty result and warns if the new inventory is less than half the current row count.
- It asks before replacing inventory files.
- It backs up the previous `inventory.csv` in `inventory_backups`.
- It stages and commits only `inventory.csv` and `inventory_date.txt`.
- If inventory and timestamp are unchanged, it skips an empty commit and push.
- If the push fails, the local commit remains available to push through GitHub Desktop.
- The source export is archived only after a successful push or verified no-change run.
- Keep `incoming/` and `inventory_backups/` ignored by Git.
