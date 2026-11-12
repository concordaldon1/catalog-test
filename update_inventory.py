#!/usr/bin/env python3
"""
One-click RFMS inventory updater for the Concord Aldon roll catalog.

Workflow:
  1. Put the RFMS CSV export in the "incoming" folder.
  2. Double-click "Update Inventory.bat".
  3. This script filters the export, validates it, updates inventory.csv,
     commits only inventory.csv, and pushes to origin/main.

Included styles: Style is exactly SILVER or GOLD, or begins with Z.
The source RFMS export is never modified.
"""

from __future__ import annotations

import csv
import io
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

KEEP = [
    "Roll Number",
    "Style",
    "Style Number",
    "Color",
    "Color Number",
    "Width",
    "Amt Avail",
]
SPECIAL_STYLES = {"SILVER", "GOLD"}
MINIMUM_ROWS = 1  # Never publish an empty inventory.


def stop(message: str, code: int = 1) -> None:
    print(f"\nERROR: {message}")
    raise SystemExit(code)


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        stop(f"Git command failed: git {' '.join(args)}\n{details}")
    return result


def read_export(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    stop("Could not read the export's text encoding.")


def filter_export(source: Path, destination: Path) -> tuple[int, dict[str, int], int]:
    content = read_export(source)
    first = content.split("\n", 1)[0]
    delimiter = "\t" if first.count("\t") >= first.count(",") else ","

    wanted = [name.lower() for name in KEEP]
    indexes = None
    output_rows = []
    counts = {"SILVER": 0, "GOLD": 0, "Z-prefixed": 0}
    excluded = 0

    for row in csv.reader(io.StringIO(content), delimiter=delimiter):
        cells = [cell.strip() for cell in row]
        lowered = [cell.lower() for cell in cells]

        if "roll number" in lowered:
            if indexes is None:
                missing = [name for name in KEEP if name.lower() not in lowered]
                if missing:
                    stop("Required columns missing from RFMS export: " + ", ".join(missing))
                indexes = [lowered.index(name) for name in wanted]
            continue

        if indexes is None or not any(cells):
            continue

        selected = [cells[i] if i < len(cells) else "" for i in indexes]
        style = " ".join(selected[1].split()).upper()

        if style not in SPECIAL_STYLES and not style.startswith("Z"):
            excluded += 1
            continue

        if style in SPECIAL_STYLES:
            counts[style] += 1
        else:
            counts["Z-prefixed"] += 1
        output_rows.append(selected)

    if indexes is None:
        stop("Could not find a header row containing 'Roll Number'.")
    if len(output_rows) < MINIMUM_ROWS:
        stop("The filtered inventory contains no rows. The live inventory was not changed.")

    # Require roll numbers and numeric available amounts on every retained row.
    roll_index = KEEP.index("Roll Number")
    avail_index = KEEP.index("Amt Avail")
    bad_rolls = sum(1 for row in output_rows if not row[roll_index].strip())
    if bad_rolls:
        stop(f"{bad_rolls} included row(s) have a blank Roll Number.")

    bad_amounts = []
    for line_number, row in enumerate(output_rows, start=2):
        value = row[avail_index].replace(",", "").strip()
        try:
            float(value)
        except ValueError:
            bad_amounts.append(line_number)
    if bad_amounts:
        sample = ", ".join(map(str, bad_amounts[:8]))
        stop(f"Amt Avail has non-numeric values in output row(s): {sample}")

    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(KEEP)
        writer.writerows(output_rows)

    return len(output_rows), counts, excluded


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def main() -> None:
    repo = Path(__file__).resolve().parent
    incoming = repo / "incoming"
    processed = incoming / "processed"
    backups = repo / "inventory_backups"
    live_inventory = repo / "inventory.csv"
    temp_inventory = repo / "inventory_new.csv"

    print("=" * 62)
    print("          CONCORD ALDON - INVENTORY UPDATE")
    print("=" * 62)

    if not (repo / ".git").exists():
        stop("This updater must be placed in the root of the catalog-test Git repository.")

    branch = run_git(repo, "branch", "--show-current").stdout.strip()
    if branch != "main":
        stop(f"The repository is on branch '{branch}', not 'main'. Open the main branch before updating.")

    origin = run_git(repo, "remote", "get-url", "origin").stdout.strip()
    if not origin:
        stop("No GitHub 'origin' remote is configured.")

    incoming.mkdir(exist_ok=True)
    candidates = [
        p for p in incoming.glob("*.csv")
        if p.is_file() and p.name.lower() != "inventory.csv"
    ]
    if not candidates:
        stop("No RFMS CSV export found. Drop the exported CSV into the 'incoming' folder.")

    source = max(candidates, key=lambda p: p.stat().st_mtime)
    if len(candidates) > 1:
        print(f"\nFound {len(candidates)} CSV exports. Using the newest one:")
    print(f"\nRFMS export: {source.name}")

    # Do not overwrite while another change is already staged for commit.
    staged = run_git(repo, "diff", "--cached", "--quiet", check=False)
    if staged.returncode != 0:
        stop("There are already staged Git changes. Open GitHub Desktop and commit/publish those first.")

    old_count = count_csv_rows(live_inventory)
    print(f"Current catalog rows: {old_count:,}")

    temp_inventory.unlink(missing_ok=True)
    new_count, counts, excluded = filter_export(source, temp_inventory)
    print(f"Filtered rows:        {new_count:,}")
    print(f"  SILVER:             {counts['SILVER']:,}")
    print(f"  GOLD:               {counts['GOLD']:,}")
    print(f"  Z-prefixed:         {counts['Z-prefixed']:,}")
    print(f"  Other styles out:   {excluded:,}")

    if old_count and new_count < old_count * 0.5:
        print("\nWARNING: The new inventory is less than half the size of the current catalog.")
        answer = input("This may indicate an incomplete RFMS export. Continue anyway? Type YES: ").strip()
        if answer != "YES":
            temp_inventory.unlink(missing_ok=True)
            stop("Cancelled. Your live inventory was left unchanged.", 0)

    answer = input("\nReady to replace inventory.csv and publish to the live catalog. Continue? (Y/N): ").strip().upper()
    if answer != "Y":
        temp_inventory.unlink(missing_ok=True)
        stop("Cancelled. Your live inventory was left unchanged.", 0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups.mkdir(exist_ok=True)
    if live_inventory.exists():
        shutil.copy2(live_inventory, backups / f"inventory_before_{timestamp}.csv")

    shutil.move(str(temp_inventory), str(live_inventory))

    # Stage and commit only inventory.csv; other un-staged files are not included.
    run_git(repo, "add", "--", "inventory.csv")
    run_git(repo, "commit", "-m", f"Update inventory {timestamp}")

    print("\nUploading inventory to GitHub main...")
    push = run_git(repo, "push", "origin", "main", check=False)
    if push.returncode != 0:
        details = push.stderr.strip() or push.stdout.strip()
        print("\nThe inventory was processed and committed locally, but the push failed.")
        print("Your previous inventory backup is in inventory_backups.")
        print("Open GitHub Desktop, sign in if prompted, and click Push origin.")
        print(f"\nGit message:\n{details}")
        raise SystemExit(2)

    # Archive the source export only after a successful push.
    processed.mkdir(parents=True, exist_ok=True)
    archive_target = processed / source.name
    if archive_target.exists():
        archive_target = processed / f"{source.stem}_{timestamp}{source.suffix}"
    shutil.move(str(source), str(archive_target))

    print("\nSUCCESS: The live catalog inventory has been updated.")
    print("The RFMS export was archived in incoming\\processed.")
    print("A backup of the previous inventory is in inventory_backups.")
    print("Allow a minute or two for the website to refresh.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"\nUNEXPECTED ERROR: {exc}")
        print("The source RFMS export has not been deleted.")
        raise SystemExit(1)
