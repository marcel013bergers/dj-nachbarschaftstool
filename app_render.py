from pathlib import Path
import runpy
import sqlite3

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "dj_tool.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS playlist_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS library_tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS saved_combos (
        id INTEGER PRIMARY KEY AUTOINCREMENT
    )
    """)

    conn.commit()
    conn.close()

# 👉 DAS IST DER FIX
init_db()

TARGET = PROJECT_DIR / "app_STABLE_backup.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Missing app: {TARGET}")

runpy.run_path(str(TARGET), run_name="__main__")
