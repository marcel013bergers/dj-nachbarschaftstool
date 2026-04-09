from pathlib import Path
import runpy

PROJECT_DIR = Path(__file__).resolve().parent
TARGET = PROJECT_DIR / "app_STABLE_backup.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Expected stable app not found: {TARGET}")

runpy.run_path(str(TARGET), run_name="__main__")
