from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist"

if OUTPUT.exists():
    shutil.rmtree(OUTPUT)
OUTPUT.mkdir()
shutil.copy2(ROOT / "index.html", OUTPUT / "index.html")
print("Built Pages site in dist/ (catalog HTML only; inventory and photos stay in R2).")
