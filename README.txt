CONCORD ALDON - ONE-CLICK INVENTORY UPDATE
===========================================

WHAT THIS DOES
--------------
You export the inventory from RFMS, place the CSV in the "incoming" folder,
and double-click "Update Inventory.bat".

The updater:
- Uses the newest CSV file in incoming.
- Maps the RFMS export columns into the five catalog columns:
  Roll # -> Roll Number
  Style -> Style
  Color -> Color
  Width -> Width
  Qty Avail -> Amt Avail
- Does not require Style Number or Color Number; they are not in this RFMS export.
- Keeps rows where Style is exactly SILVER or GOLD, or begins with Z.
- Checks for the five required RFMS columns, blank roll numbers, and invalid Qty Avail values.
- Warns and asks for confirmation if the new result is less than half the current size.
- Backs up the previous inventory.csv.
- Commits only inventory.csv and pushes to origin/main.
- Moves the successfully published RFMS export into incoming\processed.

Your original export is not modified.

INSTALLATION
------------
1. Extract this package.
2. Copy these files into the ROOT of your existing catalog-test repository:
      update_inventory.py
      Update Inventory.bat
3. Create a folder named:
      incoming
4. Keep the existing inventory.csv, index.html, photos folder, and .git folder.
5. Do not put the updater inside the photos folder or a subfolder.

DAILY USE
---------
1. Export the inventory from RFMS as a CSV file.
2. Drop the CSV into catalog-test\incoming.
3. Double-click Update Inventory.bat.
4. Check the row counts shown.
5. Type Y only if the counts look reasonable.
6. Wait for SUCCESS.

If there is more than one CSV in incoming, the newest file is selected.
Older files remain there until a successful update; remove old exports or
move them elsewhere if you do not want them considered.

REQUIREMENTS
------------
- Windows
- Python 3 installed
- GitHub Desktop installed (the updater automatically looks for its bundled Git; a separate Git installation is not required)
- This folder must be a working clone of the catalog-test repository
- GitHub Desktop must have authenticated the GitHub account on that computer
- The local repository must be on the main branch

GITHUB SIGN-IN
--------------
On each computer:
1. Install GitHub Desktop.
2. Sign in with that person's own GitHub account.
3. Clone concordaldon1/catalog-test.
4. Open the cloned repository in File Explorer.
5. Put the updater files and incoming folder in that repository root.

The GitHub account must have write access to the repository. The repository owner
can grant this from GitHub.com:
Repository > Settings > Collaborators (or Collaborators and teams) > Add people.
Invite the VP's GitHub username/email and have them accept the invitation.

SAFETY
------
- The script does not change index.html or photos.
- The RFMS source export is preserved until a successful push.
- Previous inventory files are saved in inventory_backups.
- If the push fails, the new inventory is committed locally but not published.
  Open GitHub Desktop and click Push origin after fixing the sign-in/connection.
- Do not run this while another Git commit is already staged.
