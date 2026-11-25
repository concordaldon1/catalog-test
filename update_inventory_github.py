#!/usr/bin/env python3
"""
One-click RFMS inventory updater for the Concord Aldon roll catalog.

Workflow:
  1. Put the RFMS CSV export in the "incoming" folder.
  2. Double-click "Update Inventory.bat".
  3. This script filters the export, validates it, updates inventory.csv,
     updates inventory.csv and inventory_date.txt, commits them, and pushes to origin/main.

Included styles: Style is exactly SILVER or GOLD, or is a 4-character Z style
(Z plus three letters/digits, like ZG91), except ZL93 and ZL94. Longer styles
such as "ZL93 RUG MAT" and "ZG91 A1C2" are left out, never truncated.
Amt Avail is sourced from RFMS Avail Length (feet), not Qty Avail (yardage).
The source RFMS export is never modified.
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Catalog columns and their matching RFMS export headers.
# Style Number and Color Number are not present in this RFMS export.
COLUMN_MAP = [
    ("Roll Number", "Roll #"),
    ("Style", "Style"),
    ("Color", "Color"),
    ("Width", "Width"),
    ("Amt Avail", "Avail Length"),
]

# Type is derived from Style; it is not a separate RFMS export field.
OUTPUT_HEADERS = [catalog_name for catalog_name, _ in COLUMN_MAP] + ["Type"]
# A Z style is exactly 4 characters: Z plus three letters/digits (ZG91, ZU42).
Z_STYLE = re.compile(r"^Z[A-Z0-9]{3}$")
SPECIAL_STYLES = {"SILVER", "GOLD"}
EXCLUDED_Z_STYLES = {"ZL93", "ZL94"}
MINIMUM_ROWS = 1  # Never publish an empty inventory.
GIT_EXE: str | None = None


def find_git() -> str:
    """Find Git on PATH or use the copy bundled with GitHub Desktop."""
    on_path = shutil.which("git")
    if on_path:
        return on_path

    roots = []
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "GitHubDesktop")
    roots.extend([
        Path.home() / "AppData" / "Local" / "GitHubDesktop",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "GitHub Desktop",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "GitHub Desktop",
    ])

    candidates = []
    for root in roots:
        if root.exists():
            for pattern in (
                "app-*/resources/app/git/cmd/git.exe",
                "app-*/resources/app/git/mingw64/bin/git.exe",
                "app-*/resources/app/git/bin/git.exe",
                "resources/app/git/cmd/git.exe",
            ):
                candidates.extend(root.glob(pattern))

    candidates = [p for p in candidates if p.is_file()]
    if candidates:
        # The newest versioned GitHub Desktop installation is normally the best choice.
        return str(max(candidates, key=lambda p: p.stat().st_mtime))

    stop(
        "Could not find Git. GitHub Desktop should include it; make sure GitHub Desktop "
        "is installed, then reopen it and try again."
    )


def stop(message: str, code: int = 1) -> None:
    print(f"\nERROR: {message}")
    raise SystemExit(code)


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    global GIT_EXE
    if GIT_EXE is None:
        GIT_EXE = find_git()
    result = subprocess.run(
        [GIT_EXE, *args],
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

    wanted = [rfms_name.lower() for _, rfms_name in COLUMN_MAP]
    indexes = None
    output_rows = []
    counts = {
        "SILVER": 0,
        "GOLD": 0,
        "Z-prefixed": 0,
        "ZL93/ZL94 (left out)": 0,
        "Z longer (left out)": 0,
    }
    excluded = 0

    for row in csv.reader(io.StringIO(content), delimiter=delimiter):
        cells = [cell.strip() for cell in row]
        lowered = [cell.lower() for cell in cells]

        if "roll #" in lowered:
            if indexes is None:
                missing = [rfms_name for _, rfms_name in COLUMN_MAP if rfms_name.lower() not in lowered]
                if missing:
                    stop("Required RFMS columns missing from export: " + ", ".join(missing))
                indexes = [lowered.index(name) for name in wanted]
            continue

        if indexes is None or not any(cells):
            continue

        selected = [cells[i] if i < len(cells) else "" for i in indexes]
        style = " ".join(selected[1].split()).upper()

        if style in EXCLUDED_Z_STYLES:
            counts["ZL93/ZL94 (left out)"] += 1
            excluded += 1
            continue

        if style not in SPECIAL_STYLES and not Z_STYLE.fullmatch(style):
            if style.startswith("Z"):
                counts["Z longer (left out)"] += 1
            excluded += 1
            continue

        if style in SPECIAL_STYLES:
            counts[style] += 1
            inventory_type = "Vinyl"
        else:
            counts["Z-prefixed"] += 1
            inventory_type = "Carpet"
        output_rows.append(selected + [inventory_type])

    if indexes is None:
        stop("Could not find a header row containing 'Roll #'. Check that this is the RFMS export.")
    if len(output_rows) < MINIMUM_ROWS:
        stop("The filtered inventory contains no rows. The live inventory was not changed.")

    # Require roll numbers and numeric available lengths on every retained row.
    roll_index = OUTPUT_HEADERS.index("Roll Number")
    avail_index = OUTPUT_HEADERS.index("Amt Avail")
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
        stop(f"Amt Avail (RFMS Avail Length) has non-numeric values in output row(s): {sample}")

    with destination.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(OUTPUT_HEADERS)
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

    GIT_EXE = find_git()
    print(f"Git found: {GIT_EXE}")

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
    print(f"  Z styles (4 char):  {counts['Z-prefixed']:,}")
    print(f"  ZL93/ZL94 excluded: {counts['ZL93/ZL94 (left out)']:,}")
    print(f"  Longer Z left out:  {counts['Z longer (left out)']:,}")
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

    # "Inventory as of" note shown on the catalog: the date/time the RFMS export was saved.
    # Use Last Modified, not Created: copying the RFMS export from the remote
    # desktop updates Created/Accessed locally but preserves its Modified time.
    stamp = datetime.fromtimestamp(source.stat().st_mtime).astimezone()
    (repo / "inventory_date.txt").write_text(stamp.isoformat(timespec="minutes"), encoding="utf-8")
    print(f"Inventory as of:      {stamp.strftime('%b %d, %Y %I:%M %p')}")

    # Stage and commit only inventory.csv and inventory_date.txt; other un-staged files are not included.
    run_git(repo, "add", "--", "inventory.csv", "inventory_date.txt")
    staged_inventory = run_git(repo, "diff", "--cached", "--quiet", "--", "inventory.csv", "inventory_date.txt", check=False)

    if staged_inventory.returncode == 0:
        # RFMS export produced the exact same catalog file. This is a successful
        # no-op: do not attempt an empty Git commit, but still archive the export.
        print("\nNo inventory changes detected. The live catalog already matches this RFMS export.")
    else:
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

    # Archive the source export after a successful push or a verified no-change run.
    processed.mkdir(parents=True, exist_ok=True)
    archive_target = processed / source.name
    if archive_target.exists():
        archive_target = processed / f"{source.stem}_{timestamp}{source.suffix}"
    shutil.move(str(source), str(archive_target))

    if staged_inventory.returncode == 0:
        print("\nSUCCESS: No publishing was necessary; the live catalog is already up to date.")
    else:
        print("\nSUCCESS: The live catalog inventory has been updated.")
    print("The RFMS export was archived in incoming\\processed.")
    print("A backup of the previous inventory is in inventory_backups.")
    if staged_inventory.returncode != 0:
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
