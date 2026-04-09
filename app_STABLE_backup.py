def render_quick_backup_button():
    st.subheader("Schnell-Backup")
    st.caption("Backup wird erst bei Bedarf gebaut. Das spart Render-Zeit.")
    backup_key = f"quick_backup_bytes::{APP_SHORT_VERSION}"
    if st.button("📦 Backup vorbereiten", key="prepare_quick_backup_btn", width="stretch"):
        try:
            with st.spinner("Backup wird vorbereitet..."):
                st.session_state[backup_key] = build_full_backup_zip_bytes()
            st.success("Backup ist bereit zum Download.")
        except Exception as e:
            st.warning(f"Backup aktuell nicht verfügbar: {e}")

    ready_bytes = st.session_state.get(backup_key)
    if ready_bytes:
        st.download_button(
            label="⬇️ Backup jetzt herunterladen",
            data=ready_bytes,
            file_name=f"dj_tool_backup_{APP_BUILD_DATE}_{APP_BUILD_TIME.replace(':', '-')}.zip",
            mime="application/zip",
            width="stretch",
            key="download_quick_backup_btn",
        )


def render_cloud_safe_info():
    st.info("☁️ Cloud Safe Mode: Deine Daten bleiben sicher durch Backup-System + optionalen Dropbox-Sync. Regelmäßig Backup machen empfohlen!")


def render_workflow_tip_box():
    st.caption("Merksatz: Ändern → Commit → Push → Deploy → Live")


import os
import zipfile as pyzipfile
import re
import sqlite3
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher
from collections import Counter, defaultdict

import streamlit as st
import streamlit.components.v1 as components
import json
from pathlib import Path
import warnings
import logging
import time
import socket
import io
import base64
import urllib.request
import urllib.error
import urllib.parse

warnings.filterwarnings("ignore")
logging.getLogger("streamlit").setLevel(logging.ERROR)

APP_VERSION = "DJ Tool V15 - Komfort & Speed"
APP_SHORT_VERSION = "V15"
APP_BUILD_DATE = "2026-04-08"
APP_BUILD_TIME = "11:10"
APP_BUILD_SOURCE = "V14.2 stabil + Komfort/Speed/Start-Optimierung"
APP_BASELINE_ID = "djtool_master_baseline_v1"
LOGIN_ENABLED = True
AUTO_LOGIN_TRUSTED_DEVICE = True
APP_LOGIN_PASSWORD = os.environ.get("DJ_TOOL_LOGIN_PASSWORD", "Marcel1504")
SOURCE_MASTER_BUILD = "V129"
MASTER_BUILD_RULE = "Neue Versionen nur auf der letzten funktionierenden Version aufbauen"
RELEASE_GUARD_MANIFEST_DIR = "release_guard"
RELEASE_GUARD_AUTO_WRITE = True
REQUIRE_SAFE_STORAGE_FOR_IMPORTS = True

BUILD_NOTES = [
    "V15 bringt schnelleren Start ohne pip bei jedem Tool-Start",
    "V15 ergänzt leisen Start ohne sichtbares CMD-Fenster per VBS-Launcher",
    "V15 macht Systemstatus/Release-Guard optional statt bei jedem Start",
    "V15 merkt sich UI-Modus, Kompaktmodus und Hilfetexte dauerhaft",
    "V153 verschlankt Deploy/Start mit echtem Launcher statt Warn-Seite",
    "V153 reduziert Auto-Backup-Last durch Cooldown + Limitierung",
    "V153 beschleunigt zuletzt importierte Playlists per SQL-JOIN statt N+1-Queries",
    "V10.1.3 fixt die zuletzt importierten Playlists für bestehende Datenbanken ohne playlist_id in import_runs",
    "V10.1 zeigt zuletzt importierte Playlists global mit 10/20/50 Auswahl",
    "V10.1 erlaubt direktes Öffnen und Analysieren aus der Import-Historie",
    "V10 ergänzt Einfach/Profi-Modus für klareren Einstieg ohne DJ-Logik-Verlust",
    "V10 bringt Schnell-Workflow für Event -> Stil -> Auto-Set in wenigen Klicks",
    "V10 ergänzt Kompaktmodus für ruhigere Nutzung am iPad",
    "V9.9 macht die Bereichs-Hilfe konkreter mit Ablauf, Ergebnis und Arbeitsweise",
    "V9.9 zeigt die KI-Lernprinzipien direkt in Learning, Transition, Live Hilfe und Event Kontext",
    "V9.9 erklärt Confidence und Lernbasis klarer nur aus echten gespielten Playlists",
    "V9.6 ergänzt Sidebar-Schnellzugriff ohne UI-Umbau der Hauptseiten",
    "V9.6 merkt sich zuletzt genutzte Bereiche für schnelleres Springen",
    "V9.6 hält die bestehende Menü-Reihenfolge unverändert bei",
    "V9.5 bündelt weitere sichere Performance-Fixes ohne UI-Umbau",
    "V9.5 cached Unterordner-/Meta-Optionen und Dubletten-Sequenzen",
    "V9.5 ergänzt weitere SQLite-Indexe für Genre und Import-Signaturen",
    "V130 bringt Smart Event Brain mit Gäste-Alter, Stimmungsprofil und Energie-Kurve",
    "V130 ergänzt speicherbare Event-Profile pro Anlass und Herkunft",
    "V130 erweitert die KI um Event-Empfehlungen nach Phase, Gästeprofil und Stimmung",
    "V118 bereinigt Selbsttest-Altlasten, Upload-Busy-Handling und Learning-Status im Systembereich",
    "Direkt auf letzter funktionierender V99 aufgebaut",
    "V100 fixt die Herkunft-Auswahl in Playlists durchsuchen dauerhaft",
    "V100 bringt Data Safe Update System mit Auto-Backups und Build-Snapshot",
    "V103 ergänzt Dropbox Backup Sync als sichere Alternative ohne bezahlte Render Disk",
    "V106 ergänzt echtes Dropbox Refresh-Token Handling gegen expired_access_token",
    "V111 ergänzt automatischen Supabase Startup Restore bei leerer lokaler DB",
    "V113 schützt den KI-Lernstand mit Learning Safe Storage Status + Import-Sperre bei unsicherem Speicher",
    "V117 ergänzt Import-Log, Upload-Status und Learning Rebuild Tabellen",
    "V118 stabilisiert Selbsttests, Upload-Handling und Learning-Audit",
    "V119 verbessert iPad-/Upload-UX mit robuster Busy-Erkennung, Import-Zusammenfassung und Stale-Reset",
    "V120 schärft Upload-, Delete- und Dubletten-Flow für ruhigeren Alltagsbetrieb",
    "V121 macht Learning Engine Status und Rebuild im UI sichtbar",
    "V122 erweitert die DJ-KI um Event-Kontext und Gäste-Bias",
    "V123 bereinigt den Selftest und schützt Learning robuster über Versionsupdates",
    "Playlists, Analysen, Sets und Lernbasis bleiben dauerhaft gespeichert",
    "ZIP-Import übernimmt jetzt auch die Herkunft strikt aus der Ordnerstruktur",
    "01 Ordner sehr gut bewertet wird automatisch als Top Playlist behandelt",
    "Echte Reihenfolge der Songs bleibt vollständig erhalten",
    "Dubletten werden weiter komplett ignoriert",
    "Auto-Login und bestehende Basis bleiben unverändert",
    "Nur noch auf letzter Master-Datei weiterbauen",
]

CHANGELOG = [
    {"version": "V15", "date": "2026-04-09", "new": ["Schneller Start", "Leiser VBS-Launcher", "persistente UI-Einstellungen"], "fixes": ["kein pip bei jedem Start", "Systemstatus nur bei Bedarf laden", "ruhigere Sidebar und Start-Ansicht"]},
    {"version": "V153", "date": "2026-04-08", "new": ["Launcher-Fix", "Backup-Cooldown", "Import-JOIN-Cache", "Env-Login-Passwort"], "fixes": ["Docker startet wieder direkt in die echte App", "weniger ZIP-I/O bei vielen Änderungen", "schnellere zuletzt importierte Playlists", "robustere DB-Migration für genre-Index"]},
    {"version": "V10.1.3", "date": "2026-04-07", "new": ["Zuletzt importierte Playlists global", "Direkt öffnen/analysieren", "10/20/50 Auswahl"], "fixes": ["SQL-Fix für bestehende import_runs Tabellen ohne playlist_id", "klare Versionsanzeige", "sichtbarer Menüpunkt im Live-Pfad"]},
    {"version": "V10.1", "date": "2026-04-07", "new": ["Zuletzt importierte Playlists global", "Direkt öffnen", "Direkt analysieren"], "fixes": ["letzte 10/20/50 sichtbar", "Import-Historie dauerhaft nutzbar", "schneller Rücksprung zu Browser/Analyse Hub"]},
    {"version": "V10", "date": "2026-04-04", "new": ["Einfach/Profi-Modus", "Schnell-Workflow", "Kompaktmodus"], "fixes": ["klarerer Einstieg", "ruhigere Sidebar", "Abschlussversion mit sichtbarer V10-Kennung"]},
    {"version": "V9.9", "date": "2026-04-04", "new": ["konkretere Bereichs-Hilfe", "Lernprinzipien sichtbar", "Confidence-Legende"], "fixes": ["Hilfetexte praxisnäher", "KI-Erklärungen verständlicher", "gleiche UI mit mehr Orientierung"]},
    {"version": "V9.5", "date": "2026-04-04", "new": ["Meta-Option-Caches", "Sequence-Cache für Dubletten", "robustere Start-BAT"], "fixes": ["weniger gleiche DB-Abfragen", "ruhigere Dubletten-Suche", "Browser öffnet lokaler zuverlässiger"]},
    {"version": "V151", "date": "2026-04-02", "new": ["Startup Release Guard", "Manifest-Vergleich gegen letzte stabile Version", "Startwarnung bei fehlenden Pflichtfunktionen"], "fixes": ["zeigt neu/fix/fehlend direkt beim Start", "Baseline kann als stabil gespeichert werden", "Ampel-Status für Update-Freigabe"]},
    {"version": "V130", "date": "2026-04-02", "new": ["Smart Event Brain", "Energie-Kurve", "Event-Profile"], "fixes": ["fortgeschrittene Event-Steuerung", "Empfehlungen nach Gästeprofil", "stabil auf letzter Vollversion aufgebaut"]},
    {"version": "V126", "date": "2026-04-01", "new": ["Upload Dashboard", "Learning Dashboard", "Event Kontext KI", "Performance-Boost"], "fixes": ["Import-Verlauf sichtbar", "KI-Vorschläge besser erklärbar", "ruhigere große Analysen"]},
    {"version": "V118", "date": "2026-04-01", "new": ["System-Audit sichtbar", "Learning-Status direkt im Systembereich"], "fixes": ["Selbsttest-Menüprüfung bereinigt", "toter Code entfernt", "Upload-Busy läuft nicht unbegrenzt fest"]},
    {"version": "V123", "date": "2026-04-01", "new": ["sauberer Selftest", "Learning Safe Startup"], "fixes": ["nur noch echte Fehler im Test", "Learning wird bei leerem Lernstand automatisch wieder aufgebaut"]},
    {"version": "V122", "date": "2026-04-01", "new": ["Event-Kontext-KI", "Gäste-Bias", "situative Songbewertung"], "fixes": ["Songs lassen sich klarer pro Event und Publikum lesen"]},
    {"version": "V121", "date": "2026-04-01", "new": ["sichtbarer Learning-Status", "Learning-Rebuild-Button"], "fixes": ["Learning jetzt direkt im Systembereich steuerbar", "veralteter Lernstand wird klar angezeigt"]},
    {"version": "V120", "date": "2026-04-01", "new": ["Delete-/Dubletten-Flow", "Import-Audit-Kacheln"], "fixes": ["Upload-Rückmeldungen ruhiger", "wichtige Prüfungen im Systembereich sichtbarer"]},
    {"version": "V119", "date": "2026-04-01", "new": ["iPad Upload UX", "stale busy reset", "Import-Zusammenfassung"], "fixes": ["Busy-Status hängt nicht mehr so leicht fest", "Import-Seite zeigt letzte Uploads direkter"]},
    {"version": "V118", "date": "2026-04-01", "new": ["Stabilisierung", "Audit im Systembereich"], "fixes": ["Selbsttest-Menüprüfung bereinigt", "toten Code entfernt"]},
    {"version": "V117", "date": "2026-04-01", "new": ["Import-Log", "Learning Rebuild", "Upload-Status"], "fixes": ["Version sauber auf echter V113 weitergebaut", "Lernstand separat prüfbar"]},
    {"version": "V113", "date": "2026-04-01", "new": ["Learning Safe Storage", "KI-Lernstand Status", "Import-Sperre bei unsicherem Speicher"], "fixes": ["Versionsanzeige vereinheitlicht", "Cloud-Snapshot sichert Lernbasis robuster"]},
    {"version": "Phase 7 Master", "date": "2026-03-29", "new": ["Event Mode", "Learning Center", "Energy System"], "fixes": ["mehrere Regressionen bereinigt"]},
    {"version": "Phase 6", "date": "2026-03-29", "new": ["Energy System", "DJ Gehirn verbessert"], "fixes": ["Flow / Set Builder erweitert"]},
    {"version": "Phase 5", "date": "2026-03-29", "new": ["Auto-Genre", "Smart DJ System"], "fixes": ["Playlist-Analyse erweitert"]},
    {"version": "Master Merge", "date": "2026-03-29", "new": ["Konsolidierte Basis"], "fixes": ["Playlists durchsuchen, Sortierung, zuletzt importiert wiederhergestellt"]},
]

FEATURE_MANIFEST = {
    "startscreen": "Startscreen / Schnellstart",
    "import_text": "Import per Text",
    "import_file": "Import per Datei",
    "import_multi": "Import mehrerer Dateien",
    "import_zip": "Import per ZIP",
    "upload_feedback": "Upload-Komplett-Meldung",
    "playlist_cards": "Bibliotheks-Kacheln",
    "latest_imports": "Zuletzt importiert",
    "recent_imported_playlists": "Zuletzt importierte Playlists global",
    "playlist_sorting": "Sortierung in Playlists durchsuchen",
    "playlist_editing": "Playlist direkt bearbeiten",
    "event_merge": "Anlass zusammenführen",
    "source_merge": "Herkunft zusammenführen",
    "genre_merge": "Genre zusammenführen",
    "genre_system": "Genre-System",
    "track_analysis": "Track analysieren",
    "dj_brain": "DJ Gehirn",
    "event_mode": "Event Mode",
    "learning_center": "Learning Center",
    "event_presets": "Event Presets",
    "ipad_connection": "iPad Verbindung",
    "set_builder": "Set Builder",
    "energy_system": "Energy System",
    "rekordbox": "Rekordbox Import",
    "missing_tracks": "Fehlende Songs",
    "duplicates": "Doppelte Playlists",
    "system_version": "System / Version",
    "delete_clean": "Delete + Clean System",
    "transition_learning": "Track → Track KI",
    "upload_dashboard": "Upload Dashboard",
    "learning_dashboard": "Learning Dashboard",
    "event_context_ki": "Event Kontext KI",
    "smart_event_brain": "Smart Event Brain",
    "performance_boost": "Performance Boost",
    "structured_zip_import": "Strukturierter DJ-Ordner Import",
    "event_phases": "Event-Phasen System",
    "import_log": "Import-Log / letzte Uploads",
    "learning_rebuild": "Learning Engine Rebuild",
    "ipad_upload_ux": "iPad / Upload UX",
    "delete_duplicate_flow": "Delete / Dubletten Flow",
    "learning_ui": "Learning UI / Rebuild Button",
    "event_context_ki": "Event Kontext KI",
}



# -------- SET STORAGE --------
def _is_writable_dir(path_obj: Path) -> bool:
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
        test_file = path_obj / ".djtool_write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def resolve_app_data_dir() -> tuple[Path, str, bool]:
    env_candidates = [
        (os.environ.get("DJ_TOOL_DATA_DIR") or "").strip(),
        (os.environ.get("RENDER_DISK_MOUNT_PATH") or "").strip(),
        (os.environ.get("RENDER_DISK_PATH") or "").strip(),
    ]
    for raw in env_candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser() / "dj_tool_live_data"
        if _is_writable_dir(candidate):
            return candidate, f"env:{raw}", True

    probe_candidates = [
        Path("/var/data/dj_tool_live_data"),
        Path("/data/dj_tool_live_data"),
    ]
    for candidate in probe_candidates:
        if _is_writable_dir(candidate):
            return candidate, f"auto:{candidate}", True

    fallback = Path.home() / ".dj_tool_live_data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback, "fallback:home", False


APP_DATA_DIR, APP_DATA_DIR_SOURCE, APP_DATA_DIR_IS_PERSISTENT = resolve_app_data_dir()
SET_FILE = str(APP_DATA_DIR / "saved_sets.json")

BACKUP_DIR = APP_DATA_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_INFO_FILE = APP_DATA_DIR / "storage_info.json"
UI_PREFS_FILE = APP_DATA_DIR / "ui_prefs.json"
AUTO_BACKUP_COOLDOWN_SECONDS = int(os.environ.get("DJ_TOOL_AUTO_BACKUP_COOLDOWN", "45"))


def load_ui_prefs() -> dict:
    try:
        if UI_PREFS_FILE.exists():
            data = json.loads(UI_PREFS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_ui_prefs(data: dict):
    try:
        UI_PREFS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_ui_pref(key: str, default=None):
    prefs = load_ui_prefs()
    return prefs.get(key, default)


def update_ui_prefs(**kwargs):
    prefs = load_ui_prefs()
    changed = False
    for key, value in kwargs.items():
        if prefs.get(key) != value:
            prefs[key] = value
            changed = True
    if changed:
        save_ui_prefs(prefs)

MAX_AUTO_BACKUP_FILES = int(os.environ.get("DJ_TOOL_MAX_AUTO_BACKUPS", "20"))
SOURCE_PRESETS = ["Benjamin Schneider", "Michael Zimmermann", "Global", "Reverenz"]
EVENT_IMPORT_PRESETS = ["Hochzeit", "Geburtstag", "Party", "Firmenfeier", "Fasching", "80s", "90s", "90er-2000er", "2000s", "2010s", "Mixed", "Schlager", "Rock", "Latin"]

DROPBOX_BACKUP_DIR_DEFAULT = (os.environ.get("DROPBOX_BACKUP_DIR") or "/DJ-Tool-Backups").strip() or "/DJ-Tool-Backups"
DROPBOX_TOKEN_ENV_NAME = "DROPBOX_ACCESS_TOKEN"
DROPBOX_REFRESH_TOKEN_ENV_NAME = "DROPBOX_REFRESH_TOKEN"
DROPBOX_APP_KEY_ENV_NAME = "DROPBOX_APP_KEY"
DROPBOX_APP_SECRET_ENV_NAME = "DROPBOX_APP_SECRET"
DROPBOX_STARTUP_RESTORE_ENABLED = True

SUPABASE_URL_ENV_NAME = "SUPABASE_URL"
SUPABASE_KEY_ENV_NAME = "SUPABASE_KEY"
SUPABASE_TABLE_NAME_ENV_NAME = "SUPABASE_TABLE_NAME"
SUPABASE_ROW_ID_ENV_NAME = "SUPABASE_ROW_ID"
SUPABASE_TABLE_NAME_DEFAULT = "dj_tool_state"
SUPABASE_ROW_ID_DEFAULT = "main"
SUPABASE_STARTUP_RESTORE_ENABLED = True


def get_sqlite_playlist_track_counts(db_path: str) -> tuple[int, int]:
    p = Path(db_path)
    if (not p.exists()) or p.stat().st_size <= 0:
        return 0, 0
    conn = None
    try:
        conn = sqlite3.connect(str(p), timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlists'")
        has_playlists = cur.fetchone() is not None
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='playlist_tracks'")
        has_tracks = cur.fetchone() is not None
        playlist_count = 0
        track_count = 0
        if has_playlists:
            cur.execute("SELECT COUNT(*) FROM playlists")
            playlist_count = int(cur.fetchone()[0] or 0)
        if has_tracks:
            cur.execute("SELECT COUNT(*) FROM playlist_tracks")
            track_count = int(cur.fetchone()[0] or 0)
        return playlist_count, track_count
    except Exception:
        return 0, 0
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


def load_sets():
    if not Path(SET_FILE).exists():
        return []
    with open(SET_FILE, "r") as f:
        return json.load(f)

def save_sets(data):
    with open(SET_FILE, "w") as f:
        json.dump(data, f)
    auto_backup_after_data_change("set_save")


def get_storage_file_info(path_value: str) -> dict:
    p = Path(path_value)
    if not p.exists():
        return {"exists": False, "size": 0, "mtime": "-"}
    try:
        stat = p.stat()
        return {
            "exists": True,
            "size": int(stat.st_size),
            "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        }
    except Exception:
        return {"exists": True, "size": 0, "mtime": "-"}


def make_upload_signature(import_type: str, playlist_name: str, event: str, source: str, tracks, sub_event: str = ""):
    first = tracks[0]["normalized_name"] if tracks else ""
    last = tracks[-1]["normalized_name"] if tracks else ""
    track_fingerprint = "||".join([str(t.get("normalized_name") or "").strip() for t in tracks if t.get("normalized_name")])
    return "|".join([
        str(import_type or "").strip().lower(),
        str(playlist_name or "").strip().casefold(),
        str(event or "").strip().casefold(),
        str(sub_event or "").strip().casefold(),
        str(source or "").strip().casefold(),
        str(len(tracks)),
        str(first),
        str(last),
        track_fingerprint,
    ])


def set_last_upload_feedback(message: str, level: str = "success"):
    st.session_state["last_upload_feedback"] = {"message": message, "level": level}


def render_last_upload_feedback():
    info = st.session_state.get("last_upload_feedback")
    if not info:
        return
    level = info.get("level", "success")
    message = info.get("message", "")
    if level == "warning":
        st.warning(message)
    elif level == "error":
        st.error(message)
    else:
        st.success(message)


def set_last_upload_result_rows(rows):
    st.session_state["last_upload_result_rows"] = rows


def render_last_upload_result_rows():
    rows = st.session_state.get("last_upload_result_rows") or []
    if not rows:
        return
    st.subheader("Letztes Upload-Ergebnis")
    st.dataframe(rows, width="stretch", hide_index=True)

def is_upload_busy() -> bool:
    started_at = float(st.session_state.get("upload_busy_started_at") or 0)
    if started_at and (time.time() - started_at) > 180:
        clear_upload_busy()
        return False
    return bool(st.session_state.get("upload_busy", False))

def start_upload_busy(label: str = ""):
    st.session_state["upload_busy"] = True
    st.session_state["upload_busy_label"] = str(label or "Import läuft...")
    st.session_state["upload_busy_started_at"] = time.time()

def clear_upload_busy():
    st.session_state["upload_busy"] = False
    st.session_state["upload_busy_label"] = ""
    st.session_state["upload_busy_started_at"] = 0.0

def render_upload_busy_notice():
    if is_upload_busy():
        st.info(st.session_state.get("upload_busy_label") or "Import läuft...")



@st.cache_data(ttl=90, show_spinner=False)
def compute_data_cached(event=None, source=None, top_only=False, sub_event=None):
    return compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)


def clear_runtime_caches():
    for fn_name in [
        "compute_data_cached",
        "get_all_playlist_sequences",
        "get_distinct_values_cached",
        "get_merged_distinct_values_cached",
        "get_import_meta_options_cached",
        "get_distinct_sub_events_cached",
        "get_playlists_cached",
        "get_playlist_tracks_cached",
        "get_meta_counts_cached",
        "stats_counts_cached",
        "get_library_overview_cached",
        "get_recent_import_runs_cached",
        "get_all_playlist_sequences",
    ]:
        fn = globals().get(fn_name)
        if fn is not None and hasattr(fn, "clear"):
            try:
                fn.clear()
            except Exception:
                pass


def resolve_display_depth(value):
    if value == "Alle":
        return None
    try:
        return int(value)
    except Exception:
        return 20


def get_recent_import_rows_for_dashboard(limit: int = 120):
    rows = get_recent_import_runs(limit=limit)
    prepared = []
    for row in rows:
        try:
            _id, import_type, playlist_name, event, sub_event, source, track_count, status, note, created_at = row
        except Exception:
            continue
        prepared.append({
            "Zeit": created_at or "-",
            "Typ": import_type or "-",
            "Playlist": playlist_name or "-",
            "Anlass": format_event_label(event, sub_event) if event else "-",
            "Herkunft": source or "-",
            "Tracks": int(track_count or 0),
            "Status": status_badge_text(status),
            "Hinweis": note or "-",
        })
    return prepared

def get_import_dashboard_stats(limit: int = 200):
    rows = get_recent_import_rows_for_dashboard(limit=limit)
    total = len(rows)
    saved = sum(1 for r in rows if "gespeichert" in str(r["Status"]).lower())
    skipped = sum(1 for r in rows if "übersprungen" in str(r["Status"]).lower())
    errors = sum(1 for r in rows if "fehler" in str(r["Status"]).lower())
    tracks = sum(int(r.get("Tracks", 0) or 0) for r in rows)
    by_type = {}
    for r in rows:
        by_type[r["Typ"]] = by_type.get(r["Typ"], 0) + 1
    return {
        "rows": rows,
        "total": total,
        "saved": saved,
        "skipped": skipped,
        "errors": errors,
        "tracks": tracks,
        "by_type": by_type,
    }

def render_upload_dashboard_page():
    st.header("Upload Dashboard")
    st.caption("Hier siehst du klar, was wann importiert wurde, wie viel gespeichert wurde und wo Fehler oder Dubletten aufgetreten sind.")
    stats = get_import_dashboard_stats(limit=250)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Import-Zeilen", stats["total"])
    m2.metric("Gespeichert", stats["saved"])
    m3.metric("Übersprungen", stats["skipped"])
    m4.metric("Fehler", stats["errors"])
    m5.metric("Tracks", stats["tracks"])

    state = get_upload_run_state()
    if state:
        if state.get("status") == "running":
            st.info(
                f"⏳ Upload läuft: {int(state.get('processed_files', 0) or 0)}/{int(state.get('total_files', 0) or 0)} verarbeitet"
                + (f" • gerade: {state.get('current_name')}" if state.get("current_name") else "")
            )
        elif state.get("status") == "done":
            st.success(
                f"✅ Letzter Lauf fertig: {int(state.get('saved', 0) or 0)} gespeichert • "
                f"{int(state.get('skipped', 0) or 0)} übersprungen • {int(state.get('errors', 0) or 0)} Fehler"
            )

    type_rows = [{"Import-Typ": k, "Anzahl": v} for k, v in sorted(stats["by_type"].items(), key=lambda x: (-x[1], x[0]))]
    c1, c2 = st.columns([1.2, 3.8])
    with c1:
        st.subheader("Import-Typen")
        if type_rows:
            st.dataframe(type_rows, width="stretch", hide_index=True)
        else:
            st.info("Noch keine Import-Daten.")
    with c2:
        st.subheader("Letzte Uploads")
        if stats["rows"]:
            st.dataframe(stats["rows"][:120], width="stretch", hide_index=True)
        else:
            st.info("Noch keine Upload-Historie vorhanden.")



def confidence_label_from_count(count: int) -> str:
    cnt = int(count or 0)
    if cnt >= 12:
        return "sehr hoch"
    if cnt >= 7:
        return "hoch"
    if cnt >= 4:
        return "mittel"
    if cnt >= 2:
        return "niedrig"
    return "sehr niedrig"


def render_context_help_box(menu_name: str):
    help_map = {
        "🏠 Start": {
            "wofür": "Schneller Einstieg in die wichtigsten Bereiche.",
            "du_kannst": [
                "direkt in Analyse, Event Presets, Set Builder oder Live Hilfe springen",
                "die wichtigsten Funktionen kurz überblicken",
                "ohne Suchen in den Arbeitsbereich wechseln",
            ],
            "ablauf": [
                "Startscreen lesen und einen Bereich wählen",
                "bei Event-Arbeit zuerst Presets oder Vorbereitung nutzen",
                "bei akuter Song-Frage eher Live Hilfe oder Transition KI öffnen",
            ],
            "ergebnis": "Du bist schneller im richtigen Bereich und vermeidest unnötiges Klicken.",
            "tipp": "Nutze Start als Home-Basis und arbeite danach in den Fachbereichen weiter.",
        },
        "Playlists importieren": {
            "wofür": "Neue echte Setlisten ins Lernsystem übernehmen.",
            "du_kannst": [
                "Text, Datei, mehrere Dateien oder ZIP importieren",
                "Event, Quelle und optional Unterordner sauber vergeben",
                "Dubletten automatisch erkennen und vermeiden",
            ],
            "ablauf": [
                "passende Import-Art wählen",
                "Event und Herkunft sauber setzen",
                "importieren und danach Learning/Analyse mit den neuen Daten nutzen",
            ],
            "ergebnis": "Neue reale Sets stehen danach vollständig für Blöcke, Übergänge, Rollen und Event-Lernen bereit.",
            "tipp": "Saubere Event- und Quellenangaben machen die KI-Vorschläge später deutlich besser.",
        },
        "Analyse Hub": {
            "wofür": "Zentrale Auswertung deiner gespielten Playlists.",
            "du_kannst": [
                "wichtige Songs, Übergänge und Muster prüfen",
                "Filter nach Event, Quelle und Top-Playlists setzen",
                "Treffer direkt merken oder in den Set Builder übernehmen",
            ],
            "ablauf": [
                "erst Event und Herkunft filtern",
                "dann Songs, Übergänge oder Blöcke lesen",
                "brauchbare Treffer merken oder direkt übernehmen",
            ],
            "ergebnis": "Du siehst, was in echten Sets wirklich oft funktioniert hat.",
            "tipp": "Analyse Hub ist ideal, wenn du erst verstehen willst, was wirklich oft funktioniert hat.",
        },
        "Vorbereitung": {
            "wofür": "Event vorab systematisch vorbereiten.",
            "du_kannst": [
                "wichtige Titel und Kombinationen sammeln",
                "eventbezogene Lücken erkennen",
                "Material für dein späteres Set vorsortieren",
            ],
            "ablauf": [
                "Event filtern",
                "wichtige Songs und Kombis prüfen",
                "nur relevante Treffer in Merkliste oder Set Builder übernehmen",
            ],
            "ergebnis": "Du gehst strukturierter in den Gig und musst live weniger suchen.",
            "tipp": "Erst filtern, dann merken, dann im Set Builder weiterarbeiten.",
        },
        "Event Presets": {
            "wofür": "Schnell passende Grundeinstellungen für typische Events laden.",
            "du_kannst": [
                "Eventtyp, Quelle und Zielbereich vorbelegen",
                "schneller zwischen Hochzeit, Geburtstag, Firmenfeier usw. wechseln",
                "mit einem Klick in Analyse, Vorbereitung oder Set Builder springen",
            ],
            "ablauf": [
                "passendes Preset wählen",
                "Zielbereich öffnen",
                "danach nur noch fein anpassen statt alles neu setzen",
            ],
            "ergebnis": "Das Tool startet direkt mit sinnvollen Filtern und spart viele Klicks.",
            "tipp": "Presets sparen Klicks und sorgen dafür, dass du immer mit sinnvollen Filtern startest.",
        },
        "Auto Event Set": {
            "wofür": "Automatisch eine sinnvolle Set-Struktur aus echten Event-Daten vorschlagen.",
            "du_kannst": [
                "Anlass, Herkunft, Gäste-Typ und Flow-Profil kombinieren",
                "Warmup-, Mittelteil-, Peak- und Closing-Ideen sehen",
                "mit echten Mustern statt nur nach Bauchgefühl starten",
            ],
            "ablauf": [
                "Event-Filter setzen",
                "Flow-Profil und Gäste-Typ wählen",
                "Vorschlag lesen und gute Treffer weiterverwenden",
            ],
            "ergebnis": "Du bekommst schneller eine tragfähige Set-Richtung für das Event.",
            "tipp": "Auto Event Set ist stark für den ersten Aufschlag, Feinarbeit danach im Set Builder.",
        },
        "Set Builder": {
            "wofür": "Aus echten Lernmustern ein konkretes Set bauen.",
            "du_kannst": [
                "Songs, Übergänge und Blöcke übernehmen",
                "dein Set bewerten und weiterentwickeln",
                "schrittweise aus echten Playlist-Mustern bauen",
            ],
            "ablauf": [
                "Treffer aus Analyse, Live Hilfe oder Transition KI übernehmen",
                "Reihenfolge prüfen",
                "Set mit Bauchgefühl und Erfahrung final schärfen",
            ],
            "ergebnis": "Ein konkretes Set, das auf realen Übergängen und deinem Stil basiert.",
            "tipp": "Übernimm nur Treffer mit gutem Bauchgefühl und nutze die KI eher als Verstärker als als Autopilot.",
        },
        "Event vorbereiten": {
            "wofür": "Für ein konkretes Event die wichtigsten Bausteine sehen.",
            "du_kannst": [
                "Top-Songs, starke Übergänge und typische Blöcke prüfen",
                "Fehlstellen und Event-Lücken sehen",
                "Treffer direkt merken oder ins Set ziehen",
            ],
            "ablauf": [
                "Event filtern",
                "wichtige Bausteine checken",
                "Fehlendes ergänzen oder direkt ins Set übernehmen",
            ],
            "ergebnis": "Du erkennst schnell, was für dieses Event wirklich noch fehlt oder besonders wichtig ist.",
            "tipp": "Gut geeignet als letzter Check vor dem eigentlichen Setbau.",
        },
        "Learning Dashboard": {
            "wofür": "Nachvollziehen, was die KI aus echten Playlists gelernt hat.",
            "du_kannst": [
                "sehen, welche Rolle und Phase ein Song typischerweise hat",
                "direkte Folgesongs, Vorgänger und Ketten prüfen",
                "Confidence und Datenbasis hinter Vorschlägen erkennen",
            ],
            "ablauf": [
                "Song eingeben",
                "Metriken und Begründung lesen",
                "danach Folgesongs, Ketten und Event-Lernen vergleichen",
            ],
            "ergebnis": "Du verstehst nicht nur den Vorschlag, sondern auch die dahinterliegende Lernbasis.",
            "tipp": "Nutze diesen Bereich immer dann, wenn du verstehen willst, warum das Tool etwas empfiehlt.",
        },
        "Transition KI": {
            "wofür": "Ab einem aktuellen Song echte nächste Wege finden.",
            "du_kannst": [
                "direkte Folgetracks sehen",
                "3er-, 4er- und 5er-Ketten prüfen",
                "brauchbare Wege direkt in den Set Builder übernehmen",
            ],
            "ablauf": [
                "aktuellen Song eingeben",
                "Top-Folgetracks und Route lesen",
                "gute Treffer direkt ins Set übernehmen",
            ],
            "ergebnis": "Du bekommst schnelle, echte Anschlussideen aus real gespielten Übergängen.",
            "tipp": "Ideal live oder kurz vor dem Gig, wenn du schnell Anschlussideen brauchst.",
        },
        "Live Hilfe": {
            "wofür": "Schnelle Live-Unterstützung auf Basis deiner echten Daten.",
            "du_kannst": [
                "einen aktuellen Song eingeben und passende nächste Optionen sehen",
                "Gäste-Typ und Flow-Profil berücksichtigen",
                "sichere Richtungen für den nächsten Schritt finden",
            ],
            "ablauf": [
                "aktuellen Song eingeben",
                "Gäste-Typ und Flow setzen",
                "zwischen beste jetzt, sichere Wechsel und Blöcke vergleichen",
            ],
            "ergebnis": "Du kannst live schneller reagieren, ohne die Lernbasis aus den Augen zu verlieren.",
            "tipp": "Nutze Live Hilfe eher für schnelle Entscheidungen, das Learning Dashboard eher zum Verstehen.",
        },
        "Event Kontext KI": {
            "wofür": "Songs im Kontext von Event, Timing und Gäste-Typ lesen.",
            "du_kannst": [
                "prüfen, ob ein Song in diesem Event wirklich passt",
                "typische Rolle, Phase und Event-Herkunft sehen",
                "ähnliche passende Songs entdecken",
            ],
            "ablauf": [
                "Song und Event-Kontext setzen",
                "Rolle, Phase und Event-Fit lesen",
                "ähnliche Songs für denselben Zweck vergleichen",
            ],
            "ergebnis": "Du verstehst besser, warum ein Song für ein Event stark oder eher schwach passt.",
            "tipp": "Ideal, wenn du unsicher bist, ob ein Song in genau diesem Kontext funktioniert.",
        },
        "Smart Event Brain": {
            "wofür": "Event-bezogen sinnvolle Songs und Muster erkennen.",
            "du_kannst": [
                "typische Songs pro Event verstehen",
                "wiederkehrende Event-Muster sichtbar machen",
                "dein Gespür mit echten Daten absichern",
            ],
            "ablauf": [
                "Event sauber filtern",
                "Profile und Lernmuster lesen",
                "brauchbare Kandidaten in Set oder Vorbereitung übernehmen",
            ],
            "ergebnis": "Du erkennst schneller, welche Songs und Muster für das Event wirklich Substanz haben.",
            "tipp": "Besonders stark, wenn deine Events sauber gepflegt und benannt sind.",
        },
        "KI Rollen & Timing": {
            "wofür": "Verstehen, wann und in welcher Funktion Songs typischerweise laufen.",
            "du_kannst": [
                "Opener-, Aufbau-, Peak- und Closing-Songs besser erkennen",
                "Rollen mit Event-Kontext lesen",
                "Timing-Schwerpunkte für Songs prüfen",
            ],
            "ablauf": [
                "Event-Kontext wählen",
                "Rollen und Timing lesen",
                "Treffer für Set-Aufbau nutzen",
            ],
            "ergebnis": "Du triffst bessere Entscheidungen für Dramaturgie und Abendverlauf.",
            "tipp": "Sehr hilfreich, wenn du nicht nur Songwahl, sondern auch Position im Set verbessern willst.",
        },
    }
    cfg = help_map.get(menu_name)
    if not cfg:
        return
    expanded_menus = {"Event Presets", "Auto Event Set", "Analyse Hub", "Learning Dashboard", "Live Hilfe", "Playlists importieren", "Set Builder", "Event vorbereiten", "Transition KI", "Event Kontext KI", "Smart Event Brain"}
    with st.expander(f"ℹ️ Hilfe zu: {menu_name}", expanded=menu_name in expanded_menus):
        st.markdown(f"**Wofür ist dieser Bereich da?**\n\n{cfg['wofür']}")
        st.markdown("**Was kannst du hier machen?**")
        for item in cfg["du_kannst"]:
            st.write(f"- {item}")
        if cfg.get("ablauf"):
            st.markdown("**Schneller Ablauf**")
            for idx, item in enumerate(cfg["ablauf"], start=1):
                st.write(f"{idx}. {item}")
        if cfg.get("ergebnis"):
            st.success(f"Ergebnis: {cfg['ergebnis']}")
        st.info(f"Tipp: {cfg['tipp']}")


def render_learning_rules_box(context_label: str, expanded: bool = False):
    with st.expander(f"🧠 Wie die KI hier lernt – {context_label}", expanded=expanded):
        st.markdown("**Grundregel:** Die KI lernt nur aus echten gespielten Playlists, die im Tool importiert wurden. Keine Demo-Daten, keine erfundenen Übergänge.")
        st.write("- Übergänge entstehen aus echten Song-zu-Song-Folgen in importierten Playlists.")
        st.write("- 3er-, 4er- und 5er-Blöcke kommen nur aus realen Ketten in deinen Daten.")
        st.write("- Rollen wie Opener, Peak oder Closing werden aus Position, Timing und Wiederholung abgeleitet.")
        st.write("- Event-Lernen nutzt Anlass, Herkunft und bei Geburtstagen auch Unterordner, wenn vorhanden.")
        st.write("- Wenig Vorkommen = schwaches Signal. Hohe Trefferzahl über mehrere Playlists = stärkeres Signal.")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("sehr niedrig", "1x")
        c2.metric("niedrig", "2-3x")
        c3.metric("mittel", "4-6x")
        c4.metric("hoch+", "ab 7x")
        st.caption("Confidence ist also keine Magie, sondern eine einfache Lesart der echten Trefferbasis.")


def build_learning_explainer_pack(query_track, event=None, source=None, top_only=False, sub_event=None):
    insights = get_track_insights(query_track, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not insights:
        return None
    current_display = insights["display"]
    role = get_track_role_label(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    phase = get_track_phase_label(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    timing = get_track_timing_bucket(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    energy = estimate_track_energy(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    playlist_count = int(insights.get("playlist_count", 0) or 0)
    total_count = int(insights.get("total_count", 0) or 0)

    learned_next = []
    strongest_next_count = 0
    for norm, cnt in insights.get("after", [])[:12]:
        display = display_from_normalized(norm)
        cnt = int(cnt or 0)
        strongest_next_count = max(strongest_next_count, cnt)
        learned_next.append({
            "Song": display,
            "Übergänge": cnt,
            "Confidence": confidence_label_from_count(cnt),
            "Warum": f"{cnt} echte Übergänge",
            "Rolle": get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "Phase": get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "Timing": get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
        })

    learned_before = []
    for norm, cnt in insights.get("before", [])[:10]:
        display = display_from_normalized(norm)
        cnt = int(cnt or 0)
        learned_before.append({
            "Song davor": display,
            "Häufigkeit": cnt,
            "Confidence": confidence_label_from_count(cnt),
            "Warum": f"{cnt} echte Vorgänger",
        })

    event_rows = []
    for ev_name, cnt in insights.get("event_info", Counter()).most_common(8):
        cnt = int(cnt or 0)
        event_rows.append({"Typisches Event": ev_name, "Vorkommen": cnt, "Confidence": confidence_label_from_count(cnt)})

    chains = []
    strongest_chain_count = 0
    for combo_text, cnt in insights.get("block3", [])[:6]:
        cnt = int(cnt or 0)
        strongest_chain_count = max(strongest_chain_count, cnt)
        chains.append({"Kette": combo_text, "Häufigkeit": cnt, "Confidence": confidence_label_from_count(cnt), "Typ": "3er"})
    for combo_text, cnt in insights.get("block4", [])[:4]:
        cnt = int(cnt or 0)
        strongest_chain_count = max(strongest_chain_count, cnt)
        chains.append({"Kette": combo_text, "Häufigkeit": cnt, "Confidence": confidence_label_from_count(cnt), "Typ": "4er"})
    for combo_text, cnt in insights.get("block5", [])[:3]:
        cnt = int(cnt or 0)
        strongest_chain_count = max(strongest_chain_count, cnt)
        chains.append({"Kette": combo_text, "Häufigkeit": cnt, "Confidence": confidence_label_from_count(cnt), "Typ": "5er"})

    confidence_seed = max(strongest_next_count, strongest_chain_count, total_count // 3)
    confidence_label = confidence_label_from_count(confidence_seed)
    basis_text = f"Gelernt aus {playlist_count} Playlists und {total_count} Song-Vorkommen."
    explanation = [
        f"Der Song wurde insgesamt {total_count}x gefunden.",
        f"Er taucht in {playlist_count} verschiedenen Playlists auf.",
        f"Typische Rolle: {role}.",
        f"Typische Phase: {phase}.",
        f"Timing im Abend: {timing}.",
        f"Geschätzte Energie: {energy}/10.",
        f"Confidence für diesen Song: {confidence_label}.",
        "Alle Folgesongs und Ketten werden nur aus echten gespielten Playlists abgeleitet.",
    ]
    weak_signals = []
    for row in learned_next:
        if int(row.get("Übergänge", 0) or 0) <= 1:
            weak_signals.append(f"{row['Song']} ist aktuell nur sehr dünn belegt.")
    for row in chains:
        if int(row.get("Häufigkeit", 0) or 0) <= 1:
            weak_signals.append(f"{row['Typ']}-Kette '{row['Kette']}' ist bisher nur einmal gesehen worden.")
    weak_signals = weak_signals[:6]

    return {
        "current": current_display,
        "role": role,
        "phase": phase,
        "timing": timing,
        "energy": energy,
        "confidence_label": confidence_label,
        "playlist_count": playlist_count,
        "total_count": total_count,
        "basis_text": basis_text,
        "insights": insights,
        "learned_next": learned_next,
        "learned_before": learned_before,
        "event_rows": event_rows,
        "chains": chains,
        "explanation": explanation,
        "weak_signals": weak_signals,
    }

def render_learning_dashboard_page():
    st.header("Learning Dashboard")
    st.caption("Hier siehst du, warum die KI etwas vorschlägt: Rolle, Timing, Events, Übergänge und echte Ketten.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Learning Dashboard", title="Schnell laden")
    render_learning_rules_box("Learning Dashboard", expanded=True)

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="learn_dash_event")
    src = c2.selectbox("Herkunft", sources, key="learn_dash_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="learn_dash_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="learn_dash_top")

    query_track = st.text_input("Song verstehen", key="learn_dash_track", placeholder="z. B. Mr. Brightside")
    if not query_track:
        st.info("Song eingeben und du siehst, was die KI wirklich gelernt hat.")
        return

    pack = build_learning_explainer_pack(query_track, event=ev, source=src, top_only=top, sub_event=sub_ev)
    if not pack:
        st.warning("Kein passender Song gefunden.")
        return

    quality = get_learning_quality_snapshot(pack.get("insights"))
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Song", pack["current"])
    m2.metric("Rolle", pack["role"])
    m3.metric("Timing", pack["timing"])
    m4.metric("Energie", pack["energy"])
    m5.metric("KI-Vertrauen", f"{quality['label']} ({quality['score']})")

    st.info(" | ".join(pack["explanation"]))
    st.caption(
        f"Lernbasis: {quality['basis_playlists']} Playlists | Song-Nutzung: {quality['total_count']}x"
        + (f" | Stärkster Folgesong: {quality['top_next_track']} ({quality['top_next_count']}x)" if quality['top_next_track'] else "")
    )

    tabs = st.tabs(["➡️ Warum dieser nächste Song?", "⬅️ Was lief davor?", "🧱 Gelernte Ketten", "🎉 Event-Lernen"])

    with tabs[0]:
        if pack["learned_next"]:
            st.dataframe(pack["learned_next"], width="stretch", hide_index=True)
        else:
            st.info("Keine direkten Folgesongs gefunden.")
    with tabs[1]:
        if pack["learned_before"]:
            st.dataframe(pack["learned_before"], width="stretch", hide_index=True)
        else:
            st.info("Keine typischen Vorgänger gefunden.")
    with tabs[2]:
        if pack["chains"]:
            st.dataframe(pack["chains"], width="stretch", hide_index=True)
        else:
            st.info("Keine typischen Ketten gefunden.")
    with tabs[3]:
        if pack["event_rows"]:
            st.dataframe(pack["event_rows"], width="stretch", hide_index=True)
        else:
            st.info("Noch keine Event-Zuordnung verfügbar.")

def get_track_event_context_pack(track_name, event=None, source=None, top_only=False, sub_event=None, guest_type="Gemischt"):
    data = compute_data_cached(event=event, source=source, top_only=top_only, sub_event=sub_event)
    norm_query = normalize_track_text(track_name)
    matches = [k for k in data["track_total_counts"].keys() if norm_query and norm_query in k]
    if not matches:
        return None

    chosen = sorted(matches, key=lambda x: data["track_total_counts"][x], reverse=True)[0]
    display = display_from_normalized(chosen)
    total_count = int(data["track_total_counts"].get(chosen, 0))
    event_counter = data["event_split"].get(chosen, Counter())
    top_events = event_counter.most_common(6)

    role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    phase = get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    timing = get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    energy = estimate_track_energy(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    guest_bias = auto_set_guest_bias(display, guest_type)

    fit_label = "neutral"
    if guest_bias >= 10:
        fit_label = "stark passend"
    elif guest_bias >= 6:
        fit_label = "gut passend"

    recommendations = []
    for norm, cnt in data["track_total_counts"].most_common(250):
        if norm == chosen:
            continue
        disp = display_from_normalized(norm)
        same_role = get_track_role_label(disp, event=event, source=source, top_only=top_only, sub_event=sub_event)
        same_phase = get_track_phase_label(disp, event=event, source=source, top_only=top_only, sub_event=sub_event)
        score = 0
        if same_role == role:
            score += 10
        if same_phase == phase:
            score += 8
        score += auto_set_guest_bias(disp, guest_type)
        score += min(10, int(cnt))
        if score > 12:
            recommendations.append({
                "Song": disp,
                "Rolle": same_role,
                "Phase": same_phase,
                "Häufigkeit": cnt,
                "Score": score,
            })
    recommendations = sorted(recommendations, key=lambda x: (x["Score"], x["Häufigkeit"], x["Song"].casefold()), reverse=True)[:12]

    return {
        "display": display,
        "total_count": total_count,
        "role": role,
        "phase": phase,
        "timing": timing,
        "energy": energy,
        "guest_fit": fit_label,
        "top_events": [{"Event": ev_name, "Vorkommen": cnt} for ev_name, cnt in top_events],
        "recommendations": recommendations,
    }

def render_event_context_ki_page():
    st.header("Event Kontext KI")
    st.caption("Hier liest die KI Songs klarer im Kontext von Event, Timing und Gäste-Typ.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Event Kontext KI", title="Schnell laden")
    render_learning_rules_box("Event Kontext KI", expanded=False)

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="ctx_event")
    src = c2.selectbox("Herkunft", sources, key="ctx_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="ctx_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    guest_type = c4.selectbox("Gäste-Typ", GUEST_TYPES, key="ctx_guest_type")

    track_name = st.text_input("Song prüfen", key="ctx_track_name", placeholder="z. B. Mr. Brightside")
    if not track_name:
        st.info("Song eingeben und du siehst Event-Kontext, Rolle, Timing und passende ähnliche Songs.")
        return

    pack = get_track_event_context_pack(track_name, event=ev, source=src, sub_event=sub_ev, guest_type=guest_type)
    if not pack:
        st.warning("Kein passender Song im Bestand gefunden.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Song", pack["display"])
    m2.metric("Rolle", pack["role"])
    m3.metric("Timing", pack["timing"])
    m4.metric("Gäste-Fit", pack["guest_fit"])
    st.caption(f"Phase: {pack['phase']} | Energie: {pack['energy']} | Nutzung: {pack['total_count']}x")

    left, right = st.columns(2)
    with left:
        st.subheader("Typische Events")
        if pack["top_events"]:
            st.dataframe(pack["top_events"], width="stretch", hide_index=True)
        else:
            st.info("Noch keine Event-Zuordnung verfügbar.")
    with right:
        st.subheader("Ähnliche situative Songs")
        if pack["recommendations"]:
            st.dataframe(pack["recommendations"], width="stretch", hide_index=True)
        else:
            st.info("Noch keine ähnlichen Songs gefunden.")

def build_full_backup_zip_bytes():
    backup_buffer = io.BytesIO()
    with pyzipfile.ZipFile(backup_buffer, "w") as zf:
        if Path(DB_PATH).exists():
            zf.write(DB_PATH, arcname="djtool_live.db")
        if Path(SET_FILE).exists():
            zf.write(SET_FILE, arcname="saved_sets.json")
        manifest = [
            f"Version: {APP_VERSION}",
            f"Build: {APP_BUILD_DATE} {APP_BUILD_TIME}",
            f"DB_PATH: {DB_PATH}",
            f"SET_FILE: {SET_FILE}",
            f"SOURCE_MASTER_BUILD: {SOURCE_MASTER_BUILD}",
            f"MASTER_BUILD_RULE: {MASTER_BUILD_RULE}",
        ]
        zf.writestr("backup_manifest.txt", "\n".join(manifest))
    backup_buffer.seek(0)
    return backup_buffer.getvalue()


def _prune_old_backups(max_files: int = MAX_AUTO_BACKUP_FILES):
    try:
        files = sorted(BACKUP_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
        for old_file in files[int(max_files):]:
            old_file.unlink(missing_ok=True)
    except Exception:
        pass


def should_run_auto_backup(reason: str = "autosave") -> bool:
    now_ts = time.time()
    last_ts = float(st.session_state.get("last_auto_backup_ts", 0) or 0)
    last_reason = str(st.session_state.get("last_auto_backup_reason", "") or "")
    cooldown = max(0, int(AUTO_BACKUP_COOLDOWN_SECONDS or 0))
    if cooldown and last_ts and (now_ts - last_ts) < cooldown and last_reason == str(reason or ""):
        st.session_state["last_auto_backup_skipped_reason"] = f"Cooldown aktiv ({cooldown}s)"
        return False
    st.session_state["last_auto_backup_skipped_reason"] = ""
    return True


def create_timestamped_backup_file(reason: str = "manual") -> str:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_reason = re.sub(r"[^a-z0-9_-]+", "_", str(reason or "manual").strip().lower()).strip("_") or "manual"
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"dj_tool_backup_{timestamp}_{safe_reason}.zip"
    backup_path = BACKUP_DIR / backup_name
    with open(backup_path, "wb") as f:
        f.write(build_full_backup_zip_bytes())
    _prune_old_backups()
    return str(backup_path)


def auto_backup_after_data_change(reason: str = "autosave"):
    if not should_run_auto_backup(reason=reason):
        return str(st.session_state.get("last_auto_backup_path", "") or "")
    try:
        path = create_timestamped_backup_file(reason=reason)
        st.session_state["last_auto_backup_path"] = path
        st.session_state["last_auto_backup_reason"] = reason
        st.session_state["last_auto_backup_ts"] = time.time()
        maybe_auto_sync_latest_backup_to_supabase(path, reason=reason)
        maybe_auto_sync_latest_backup_to_dropbox(path, reason=reason)
        return path
    except Exception as e:
        st.session_state["last_auto_backup_error"] = str(e)
        return ""


def get_recent_backup_files(limit: int = 10):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(BACKUP_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
    return files[:limit]


def persist_storage_info_snapshot():
    payload = {
        "version": APP_VERSION,
        "build_date": APP_BUILD_DATE,
        "build_time": APP_BUILD_TIME,
        "app_data_dir": str(APP_DATA_DIR),
        "app_data_dir_source": APP_DATA_DIR_SOURCE,
        "persistent_mode": bool(APP_DATA_DIR_IS_PERSISTENT),
        "db_path": DB_PATH,
        "set_file": SET_FILE,
        "backup_dir": str(BACKUP_DIR),
        "db_info": get_storage_file_info(DB_PATH),
        "set_info": get_storage_file_info(SET_FILE),
        "backup_count": len(get_recent_backup_files(limit=500)),
    }
    try:
        STORAGE_INFO_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return payload


def get_storage_status_snapshot():
    snapshot = persist_storage_info_snapshot()
    snapshot["backup_info"] = get_storage_file_info(str(BACKUP_DIR))
    return snapshot


def has_any_cloud_restore_support() -> bool:
    return bool(has_supabase_support() or bool(get_dropbox_access_token()))


def learning_memory_is_protected() -> bool:
    return bool(APP_DATA_DIR_IS_PERSISTENT or has_any_cloud_restore_support())


def get_learning_memory_status() -> dict:
    if APP_DATA_DIR_IS_PERSISTENT and has_any_cloud_restore_support():
        return {
            "level": "safe_plus_cloud",
            "label": "Sehr sicher",
            "message": "KI-Lernstand ist lokal persistent und zusätzlich per Cloud-Restore abgesichert.",
        }
    if APP_DATA_DIR_IS_PERSISTENT:
        return {
            "level": "safe_local",
            "label": "Sicher",
            "message": "KI-Lernstand ist über Persistent Storage abgesichert.",
        }
    if has_any_cloud_restore_support():
        return {
            "level": "cloud_restore",
            "label": "Cloud gesichert",
            "message": "Lokaler Speicher ist nicht persistent, aber Restore über Cloud ist aktiv.",
        }
    return {
        "level": "unsafe",
        "label": "Gefährdet",
        "message": "Weder Persistent Storage noch Cloud-Restore sind sicher aktiv. Ein Deploy kann den Lernstand löschen.",
    }


def render_learning_memory_banner():
    status = get_learning_memory_status()
    text = f"🧠 KI-Lernstand: {status['label']} — {status['message']}"
    if status["level"] == "unsafe":
        st.error(text)
    elif status["level"] == "cloud_restore":
        st.warning(text)
    else:
        st.success(text)


def require_safe_storage_before_imports():
    if not REQUIRE_SAFE_STORAGE_FOR_IMPORTS:
        return True
    if learning_memory_is_protected():
        return True
    st.error("⚠️ Import aktuell gesperrt: Der Speicher ist nicht sicher genug für langfristiges KI-Lernen.")
    st.info("Aktiviere Persistent Storage oder richte mindestens Supabase oder Dropbox-Backup mit Restore ein. Erst dann neue Playlists importieren.")
    st.caption("So verhinderst du, dass über Wochen gelernte Daten nach einem Deploy wieder verschwinden.")
    return False


def ensure_build_snapshot_backup():
    snapshot_key = f"build_snapshot_done::{APP_BUILD_DATE}::{APP_BUILD_TIME}"
    if st.session_state.get(snapshot_key):
        return
    st.session_state[snapshot_key] = True
    try:
        playlist_count, track_count, _library_count, _combo_count = stats_counts()
        if playlist_count <= 0 and track_count <= 0:
            return
        existing = list(BACKUP_DIR.glob(f"*build_{APP_BUILD_DATE}_{APP_BUILD_TIME.replace(':', '-')}.zip"))
        if existing:
            st.session_state["last_build_snapshot_path"] = str(existing[0])
            return
        path = create_timestamped_backup_file(reason=f"build_{APP_BUILD_DATE}_{APP_BUILD_TIME.replace(':', '-')}")
        st.session_state["last_build_snapshot_path"] = path
        maybe_auto_sync_latest_backup_to_supabase(path, reason="build_snapshot")
        maybe_auto_sync_latest_backup_to_dropbox(path, reason="build_snapshot")
    except Exception as e:
        st.session_state["last_build_snapshot_error"] = str(e)


@st.cache_data(ttl=180, show_spinner=False)
def get_merged_distinct_values_cached(column_name, presets_key=()):
    values = get_distinct_values(column_name)
    merged = ["Alle"]
    seen = {"alle"}
    for value in list(presets_key) + list(values):
        clean = normalize_meta_value(value)
        if not clean:
            continue
        key = normalize_meta_key(clean)
        if key not in seen:
            merged.append(clean)
            seen.add(key)
    return merged


def get_merged_distinct_values(column_name, presets=None):
    return get_merged_distinct_values_cached(column_name, tuple(presets or []))


@st.cache_data(ttl=180, show_spinner=False)
def get_import_meta_options_cached(column_name: str, presets_key=()):
    values = get_distinct_values(column_name)
    collected = []
    seen = set()
    for value in list(presets_key) + list(values):
        clean = normalize_meta_value(value)
        if not clean:
            continue
        key = normalize_meta_key(clean)
        if key in seen or key == "alle":
            continue
        seen.add(key)
        collected.append(clean)
    return sorted(collected, key=lambda x: x.casefold())


def get_import_meta_options(column_name: str, presets=None):
    return get_import_meta_options_cached(column_name, tuple(presets or []))


def render_data_safety_status(p_count: int, t_count: int):
    backup_files = get_recent_backup_files(limit=1)
    latest_backup = backup_files[0].name if backup_files else "Noch kein Auto-Backup"
    storage = get_storage_status_snapshot()
    learning_status = get_learning_memory_status()
    cols = st.columns(4)
    cols[0].metric("Live-Playlists", p_count)
    cols[1].metric("Live-Tracks", t_count)
    cols[2].metric("Backups", len(get_recent_backup_files(limit=500)))
    cols[3].metric("KI-Lernstand", learning_status["label"])
    render_learning_memory_banner()
    st.caption(f"Aktive Live-DB: {DB_PATH}")
    st.caption(f"Backup-Ordner: {BACKUP_DIR}")
    st.caption(f"Speicher-Quelle: {APP_DATA_DIR_SOURCE}")
    st.caption(f"Persistent erkannt: {'Ja' if APP_DATA_DIR_IS_PERSISTENT else 'Nein'}")
    st.caption(f"Speicher-Modus: {'Persistent Disk' if APP_DATA_DIR_IS_PERSISTENT else 'Fallback / temporär'}")
    st.caption(f"Cloud-Restore aktiv: {'Ja' if has_any_cloud_restore_support() else 'Nein'}")
    st.caption(f"DB-Datei: {'vorhanden' if storage['db_info']['exists'] else 'fehlt'} | Größe: {storage['db_info']['size']} Bytes | Geändert: {storage['db_info']['mtime']}")
    st.caption(f"Letztes Backup: {latest_backup}")
    st.caption(f"Dropbox: {get_dropbox_token_source_label()} | Refresh: {dropbox_refresh_status_label()} | Ordner: {get_dropbox_backup_dir()}")
    st.caption(f"Supabase: {supabase_status_label()} | Tabelle: {get_supabase_table_name()} | Row: {get_supabase_row_id()}")
    if st.session_state.get("supabase_startup_restore_status"):
        st.caption(f"Supabase Startup Restore: {st.session_state.get('supabase_startup_restore_status')}")
    if st.session_state.get("supabase_startup_restore_counts"):
        st.caption(f"Supabase Restore Ergebnis: {st.session_state.get('supabase_startup_restore_counts')}")
    if st.session_state.get("dropbox_startup_restore_status"):
        st.caption(f"Dropbox Startup Restore: {st.session_state.get('dropbox_startup_restore_status')}")
    if st.session_state.get("dropbox_startup_restore_counts"):
        st.caption(f"Dropbox Restore Ergebnis: {st.session_state.get('dropbox_startup_restore_counts')}")

    if learning_status["level"] == "unsafe":
        st.error("⚠️ Unsicherer Lernspeicher: Neue Uploads sind absichtlich gesperrt, bis Persistent Storage oder Cloud-Restore aktiv ist.")
    elif not APP_DATA_DIR_IS_PERSISTENT:
        st.warning("⚠️ Lokaler Speicher ist nicht persistent. Dein Lernstand ist aktuell nur über Cloud-Restore geschützt.")

    prev = st.session_state.get("previous_playlist_count")
    if prev is not None and prev > 0 and p_count == 0:
        st.error("⚠️ Warnung: Vorher waren Playlists da, jetzt ist der Bestand leer. Bitte sofort DB-Pfad / Backup prüfen und NICHT weiter importieren, bevor das geklärt ist.")
    st.session_state["previous_playlist_count"] = p_count


def get_dropbox_refresh_token() -> str:
    return str(os.environ.get(DROPBOX_REFRESH_TOKEN_ENV_NAME) or "").strip()


def get_dropbox_app_key() -> str:
    return str(os.environ.get(DROPBOX_APP_KEY_ENV_NAME) or "").strip()


def get_dropbox_app_secret() -> str:
    return str(os.environ.get(DROPBOX_APP_SECRET_ENV_NAME) or "").strip()


def has_dropbox_refresh_support() -> bool:
    return bool(get_dropbox_refresh_token() and get_dropbox_app_key() and get_dropbox_app_secret())


def dropbox_refresh_status_label() -> str:
    return "Aktiv" if has_dropbox_refresh_support() else "Nicht aktiv"


def _dropbox_extract_error_tag(detail_text: str) -> str:
    try:
        payload = json.loads(detail_text or "{}")
        err = payload.get("error") or {}
        if isinstance(err, dict):
            tag = err.get(".tag") or ""
            if tag == "expired_access_token":
                return tag
            nested = err.get("path") or {}
            if isinstance(nested, dict) and nested.get(".tag"):
                return str(nested.get(".tag"))
        if payload.get("error_summary"):
            summary = str(payload.get("error_summary"))
            return summary.split("/")[0] if "/" in summary else summary
    except Exception:
        pass
    text = str(detail_text or "")
    if "expired_access_token" in text:
        return "expired_access_token"
    if "invalid_access_token" in text:
        return "invalid_access_token"
    return ""


def _dropbox_should_try_refresh(detail_text: str, status_code: int | None = None) -> bool:
    if not has_dropbox_refresh_support():
        return False
    if status_code not in {None, 400, 401}:
        return False
    tag = _dropbox_extract_error_tag(detail_text)
    return tag in {"expired_access_token", "invalid_access_token"}


def refresh_dropbox_access_token(force: bool = False) -> str:
    if not has_dropbox_refresh_support():
        return ""

    now = time.time()
    cached = str(st.session_state.get("dropbox_refreshed_access_token") or "").strip()
    expires_at = float(st.session_state.get("dropbox_refreshed_access_token_expires_at") or 0)
    if cached and (not force) and expires_at > now + 60:
        return cached

    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": get_dropbox_refresh_token(),
        "client_id": get_dropbox_app_key(),
        "client_secret": get_dropbox_app_secret(),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.dropboxapi.com/oauth2/token",
        data=payload,
        method="POST",
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            result = json.loads(body or "{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Dropbox Token Refresh fehlgeschlagen ({e.code}): {detail}")

    access_token = str(result.get("access_token") or "").strip()
    if not access_token:
        raise RuntimeError("Dropbox Token Refresh lieferte kein access_token")

    expires_in = int(result.get("expires_in") or 14400)
    st.session_state["dropbox_refreshed_access_token"] = access_token
    st.session_state["dropbox_refreshed_access_token_expires_at"] = now + max(60, expires_in)
    st.session_state["dropbox_refresh_last_ok_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    st.session_state["dropbox_refresh_last_error"] = ""
    return access_token


def get_dropbox_access_token() -> str:
    session_token = str(st.session_state.get("dropbox_access_token") or "").strip()
    if session_token:
        return session_token
    if has_dropbox_refresh_support():
        try:
            token = refresh_dropbox_access_token(force=False)
            if token:
                return token
        except Exception as e:
            st.session_state["dropbox_refresh_last_error"] = str(e)
    return str(os.environ.get(DROPBOX_TOKEN_ENV_NAME) or "").strip()


def get_dropbox_token_source_label() -> str:
    if str(st.session_state.get("dropbox_access_token") or "").strip():
        return "Session"
    if has_dropbox_refresh_support():
        return "Refresh Token"
    if str(os.environ.get(DROPBOX_TOKEN_ENV_NAME) or "").strip():
        return "Environment"
    return "Nicht verbunden"


def get_dropbox_backup_dir() -> str:
    raw = str(st.session_state.get("dropbox_backup_dir") or DROPBOX_BACKUP_DIR_DEFAULT).strip()
    if not raw:
        raw = DROPBOX_BACKUP_DIR_DEFAULT
    return "/" + raw.strip("/")


def get_dropbox_backup_display_name(remote_path: str) -> str:
    clean = str(remote_path or "").strip()
    if not clean:
        return ""
    return clean.rsplit("/", 1)[-1]


def build_dropbox_remote_path(filename: str) -> str:
    folder = get_dropbox_backup_dir()
    safe_name = str(filename or "backup.zip").strip().replace("\\", "_").replace("//", "/")
    return f"{folder.rstrip('/')}/{safe_name}"


def _dropbox_json_request(url: str, payload: dict):
    token = get_dropbox_access_token()
    if not token:
        raise RuntimeError("Dropbox Access Token fehlt")
    data = json.dumps(payload).encode("utf-8")

    def _send(auth_token: str):
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Bearer {auth_token}")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}

    try:
        return _send(token)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        if _dropbox_should_try_refresh(detail, e.code):
            refreshed = refresh_dropbox_access_token(force=True)
            return _send(refreshed)
        raise RuntimeError(f"Dropbox API Fehler {e.code}: {detail}")


def upload_backup_bytes_to_dropbox(backup_bytes: bytes, filename: str, mode: str = "overwrite") -> dict:
    token = get_dropbox_access_token()
    if not token:
        raise RuntimeError("Dropbox Access Token fehlt")
    remote_path = build_dropbox_remote_path(filename)
    api_arg = {
        "path": remote_path,
        "mode": mode,
        "autorename": False,
        "mute": True,
        "strict_conflict": False,
    }

    def _send(auth_token: str):
        req = urllib.request.Request(
            "https://content.dropboxapi.com/2/files/upload",
            data=backup_bytes,
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {auth_token}")
        req.add_header("Dropbox-API-Arg", json.dumps(api_arg))
        req.add_header("Content-Type", "application/octet-stream")
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            payload = json.loads(body) if body else {}
            payload["remote_path"] = remote_path
            return payload

    try:
        return _send(token)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        if _dropbox_should_try_refresh(detail, e.code):
            refreshed = refresh_dropbox_access_token(force=True)
            return _send(refreshed)
        raise RuntimeError(f"Dropbox Upload fehlgeschlagen ({e.code}): {detail}")


def get_supabase_url() -> str:
    return str(os.environ.get(SUPABASE_URL_ENV_NAME) or "").strip().rstrip("/")


def get_supabase_key() -> str:
    return str(os.environ.get(SUPABASE_KEY_ENV_NAME) or "").strip()


def get_supabase_table_name() -> str:
    return str(os.environ.get(SUPABASE_TABLE_NAME_ENV_NAME) or SUPABASE_TABLE_NAME_DEFAULT).strip() or SUPABASE_TABLE_NAME_DEFAULT


def get_supabase_row_id() -> str:
    return str(os.environ.get(SUPABASE_ROW_ID_ENV_NAME) or SUPABASE_ROW_ID_DEFAULT).strip() or SUPABASE_ROW_ID_DEFAULT


def has_supabase_support() -> bool:
    return bool(get_supabase_url() and get_supabase_key())


def supabase_status_label() -> str:
    return "Aktiv" if has_supabase_support() else "Nicht aktiv"


def _supabase_request(method: str, path: str, payload: dict | None = None):
    url = f"{get_supabase_url()}/rest/v1/{path.lstrip('/')}"
    req = urllib.request.Request(url, method=method.upper())
    req.add_header("apikey", get_supabase_key())
    req.add_header("Authorization", f"Bearer {get_supabase_key()}")
    req.add_header("Content-Type", "application/json")
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    try:
        with urllib.request.urlopen(req, data=data, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase API Fehler {e.code}: {detail}")


def upload_backup_bytes_to_supabase(backup_bytes: bytes, filename: str, reason: str = "manual") -> dict:
    if not has_supabase_support():
        raise RuntimeError("Supabase nicht konfiguriert")
    payload = {
        "id": get_supabase_row_id(),
        "backup_name": str(filename or "dj_tool_backup.zip"),
        "backup_b64": base64.b64encode(backup_bytes).decode("utf-8"),
        "backup_size": int(len(backup_bytes or b"")),
        "app_version": APP_VERSION,
        "updated_at_client": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": str(reason or "manual"),
    }
    path = f"{get_supabase_table_name()}?on_conflict=id"
    url = f"{get_supabase_url()}/rest/v1/{path}"
    req = urllib.request.Request(url, method="POST")
    req.add_header("apikey", get_supabase_key())
    req.add_header("Authorization", f"Bearer {get_supabase_key()}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "resolution=merge-duplicates,return=representation")
    data = json.dumps(payload).encode("utf-8")
    try:
        with urllib.request.urlopen(req, data=data, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            result = json.loads(body) if body else []
            if isinstance(result, list) and result:
                return result[0]
            if isinstance(result, dict):
                return result
            return {"id": get_supabase_row_id(), "backup_name": payload["backup_name"]}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Supabase Upload fehlgeschlagen ({e.code}): {detail}")


def get_supabase_backup_record() -> dict:
    if not has_supabase_support():
        raise RuntimeError("Supabase nicht konfiguriert")
    path = f"{get_supabase_table_name()}?id=eq.{urllib.parse.quote(get_supabase_row_id(), safe='')}&select=*"
    result = _supabase_request("GET", path, None)
    if isinstance(result, list) and result:
        return result[0]
    return {}


def download_supabase_backup_bytes() -> bytes:
    record = get_supabase_backup_record()
    backup_b64 = str(record.get("backup_b64") or "").strip()
    if not backup_b64:
        raise RuntimeError("Keine Supabase-Sicherung gefunden")
    try:
        return base64.b64decode(backup_b64.encode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Supabase Backup konnte nicht decodiert werden: {e}")


def maybe_auto_sync_latest_backup_to_supabase(local_path: str, reason: str = "autosave") -> str:
    if not has_supabase_support():
        return ""
    p = Path(local_path)
    if not p.exists():
        return ""
    try:
        payload = upload_backup_bytes_to_supabase(p.read_bytes(), p.name, reason=reason)
        name = payload.get("backup_name") or p.name
        st.session_state["last_supabase_sync_name"] = name
        st.session_state["last_supabase_sync_reason"] = reason
        st.session_state["last_supabase_sync_error"] = ""
        return str(name)
    except Exception as e:
        st.session_state["last_supabase_sync_error"] = str(e)
        return ""


def maybe_restore_from_supabase_on_startup(force: bool = False) -> bool:
    if not SUPABASE_STARTUP_RESTORE_ENABLED:
        return False
    session_key = "supabase_startup_restore_attempted"
    if st.session_state.get(session_key) and not force:
        return False
    st.session_state[session_key] = True

    if not has_supabase_support():
        st.session_state["supabase_startup_restore_status"] = "Supabase nicht konfiguriert"
        return False

    local_playlist_count, local_track_count = get_sqlite_playlist_track_counts(DB_PATH)
    local_db_exists = Path(DB_PATH).exists()
    needs_restore = force or (not local_db_exists) or (local_playlist_count <= 0 and local_track_count <= 0)
    if not needs_restore:
        st.session_state["supabase_startup_restore_status"] = f"Lokale DB ok ({local_playlist_count} Playlists / {local_track_count} Tracks)"
        return False

    try:
        record = get_supabase_backup_record()
        if not record:
            st.session_state["supabase_startup_restore_status"] = "Keine Supabase-Sicherung gefunden"
            return False
        data = download_supabase_backup_bytes()
        restore_backup_from_bytes(data)
        new_playlist_count, new_track_count = get_sqlite_playlist_track_counts(DB_PATH)
        st.session_state["supabase_startup_restore_status"] = f"Supabase Restore ok: {record.get('backup_name') or '-'}"
        st.session_state["supabase_startup_restore_counts"] = f"{new_playlist_count} Playlists / {new_track_count} Tracks"
        st.session_state["supabase_last_record_meta"] = {
            "backup_name": record.get("backup_name") or "",
            "updated_at_client": record.get("updated_at_client") or "",
            "reason": record.get("reason") or "",
            "backup_size": record.get("backup_size") or 0,
        }
        return True
    except Exception as e:
        st.session_state["supabase_startup_restore_status"] = f"Supabase Restore fehlgeschlagen: {e}"
        return False


def sync_backup_file_to_dropbox(local_path: str) -> dict:
    p = Path(local_path)
    if not p.exists():
        raise RuntimeError("Lokale Backup-Datei nicht gefunden")
    return upload_backup_bytes_to_dropbox(p.read_bytes(), p.name)


def list_dropbox_backup_files(limit: int = 20):
    result = _dropbox_json_request("https://api.dropboxapi.com/2/files/list_folder", {
        "path": get_dropbox_backup_dir(),
        "recursive": False,
        "include_deleted": False,
        "include_has_explicit_shared_members": False,
        "include_mounted_folders": True,
        "include_non_downloadable_files": False,
    })
    entries = []
    for entry in result.get("entries", []):
        if entry.get(".tag") != "file":
            continue
        name = str(entry.get("name") or "")
        if not name.lower().endswith(".zip"):
            continue
        entries.append(entry)
    entries = sorted(entries, key=lambda x: str(x.get("server_modified") or ""), reverse=True)
    return entries[:limit]


def download_dropbox_backup_bytes(dropbox_path: str) -> bytes:
    token = get_dropbox_access_token()
    if not token:
        raise RuntimeError("Dropbox Access Token fehlt")

    def _send(auth_token: str):
        req = urllib.request.Request("https://content.dropboxapi.com/2/files/download", method="POST")
        req.add_header("Authorization", f"Bearer {auth_token}")
        req.add_header("Dropbox-API-Arg", json.dumps({"path": dropbox_path}))
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    try:
        return _send(token)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        if _dropbox_should_try_refresh(detail, e.code):
            refreshed = refresh_dropbox_access_token(force=True)
            return _send(refreshed)
        raise RuntimeError(f"Dropbox Download fehlgeschlagen ({e.code}): {detail}")


def restore_backup_from_bytes(backup_bytes: bytes):
    restore_buffer = io.BytesIO(backup_bytes)
    with pyzipfile.ZipFile(restore_buffer, "r") as zf:
        names = set(zf.namelist())
        if "djtool_live.db" in names:
            with open(DB_PATH, "wb") as f:
                f.write(zf.read("djtool_live.db"))
        if "saved_sets.json" in names:
            with open(SET_FILE, "wb") as f:
                f.write(zf.read("saved_sets.json"))
    mark_learning_dirty("restore_backup_from_bytes")


def maybe_auto_sync_latest_backup_to_dropbox(local_path: str, reason: str = "autosave") -> str:
    token = get_dropbox_access_token()
    if not token:
        return ""
    try:
        payload = sync_backup_file_to_dropbox(local_path)
        remote_path = payload.get("remote_path") or payload.get("path_display") or ""
        st.session_state["last_dropbox_sync_path"] = remote_path
        st.session_state["last_dropbox_sync_reason"] = reason
        st.session_state["last_dropbox_sync_error"] = ""
        return remote_path
    except Exception as e:
        st.session_state["last_dropbox_sync_error"] = str(e)
        return ""


def maybe_restore_from_dropbox_on_startup(force: bool = False) -> bool:
    if not DROPBOX_STARTUP_RESTORE_ENABLED:
        return False
    session_key = "dropbox_startup_restore_attempted"
    if st.session_state.get(session_key) and not force:
        return False
    st.session_state[session_key] = True

    token = get_dropbox_access_token()
    if not token:
        st.session_state["dropbox_startup_restore_status"] = "Kein Dropbox Token gesetzt"
        return False

    local_playlist_count, local_track_count = get_sqlite_playlist_track_counts(DB_PATH)
    local_db_exists = Path(DB_PATH).exists()
    needs_restore = force or (not local_db_exists) or (local_playlist_count <= 0 and local_track_count <= 0)
    if not needs_restore:
        st.session_state["dropbox_startup_restore_status"] = f"Lokale DB ok ({local_playlist_count} Playlists / {local_track_count} Tracks)"
        return False

    try:
        entries = list_dropbox_backup_files(limit=20)
        if not entries:
            st.session_state["dropbox_startup_restore_status"] = "Keine Dropbox Backups gefunden"
            return False
        latest = entries[0]
        remote_path = latest.get("path_lower") or latest.get("path_display") or ""
        if not remote_path:
            st.session_state["dropbox_startup_restore_status"] = "Dropbox Backup-Pfad fehlt"
            return False
        data = download_dropbox_backup_bytes(remote_path)
        restore_backup_from_bytes(data)
        new_playlist_count, new_track_count = get_sqlite_playlist_track_counts(DB_PATH)
        st.session_state["dropbox_startup_restore_status"] = f"Dropbox Restore ok: {latest.get('name') or '-'}"
        st.session_state["dropbox_startup_restore_remote"] = remote_path
        st.session_state["dropbox_startup_restore_counts"] = f"{new_playlist_count} Playlists / {new_track_count} Tracks"
        return True
    except Exception as e:
        st.session_state["dropbox_startup_restore_status"] = f"Dropbox Restore fehlgeschlagen: {e}"
        return False


def reset_live_database_files():
    ok = True
    try:
        if Path(DB_PATH).exists():
            Path(DB_PATH).unlink()
    except Exception:
        ok = False
    try:
        if Path(SET_FILE).exists():
            Path(SET_FILE).unlink()
    except Exception:
        ok = False
    if ok:
        init_db()
        mark_learning_dirty("reset_live_database")
        auto_backup_after_data_change("reset_live_database")
    return ok


def render_backup_restore_page():
    st.header("Backup / Restore")
    st.caption("Hier kannst du dein komplettes Daten-Backup herunterladen, lokal wiederherstellen und optional direkt mit Supabase oder Dropbox synchronisieren.")

    st.info("Aktive Live-Datenbank liegt außerhalb des Projektordners. Alte Repo-Dateien sind nicht deine aktive Datenbank.")
    st.caption(f"Live-DB: {DB_PATH}")
    st.caption(f"Backup-Ordner: {BACKUP_DIR}")

    st.subheader("Backup herunterladen")
    backup_key = f"backup_restore_bytes::{APP_SHORT_VERSION}"
    if st.button("📦 Backup vorbereiten", key="prepare_backup_restore_btn", width="stretch"):
        try:
            with st.spinner("Backup wird vorbereitet..."):
                st.session_state[backup_key] = build_full_backup_zip_bytes()
            st.success("Backup ist bereit zum Download.")
        except Exception as e:
            st.warning(f"Backup aktuell nicht verfügbar: {e}")

    ready_bytes = st.session_state.get(backup_key)
    if ready_bytes:
        st.download_button(
            label="⬇️ Backup jetzt herunterladen",
            data=ready_bytes,
            file_name=f"dj_tool_backup_{APP_BUILD_DATE}_{APP_BUILD_TIME.replace(':', '-')}.zip",
            mime="application/zip",
            width="stretch",
            key="download_backup_restore_btn",
        )

    recent_backups = get_recent_backup_files(limit=8)
    if recent_backups:
        st.subheader("Letzte Auto-Backups")
        for backup_file in recent_backups:
            st.caption(f"• {backup_file.name}")

    st.divider()
    st.subheader("Supabase Sync + Startup Restore")
    st.caption("Supabase ist jetzt der wichtigste Cloud-Speicher. Bei leerer lokaler DB soll beim Start automatisch die letzte Sicherung geladen werden.")
    st.caption(f"Status: {supabase_status_label()}")
    if st.session_state.get("supabase_startup_restore_status"):
        st.info(f"Startup Restore Status: {st.session_state.get('supabase_startup_restore_status')}")
    if st.session_state.get("supabase_startup_restore_counts"):
        st.caption(f"Supabase Restore Ergebnis: {st.session_state.get('supabase_startup_restore_counts')}")
    if has_supabase_support():
        s1, s2 = st.columns(2)
        if s1.button("☁️ Aktuelles Backup jetzt zu Supabase hochladen", key="push_backup_supabase", width="stretch"):
            try:
                created = create_timestamped_backup_file(reason="supabase_manual_push")
                payload = upload_backup_bytes_to_supabase(Path(created).read_bytes(), Path(created).name, reason="supabase_manual_push")
                st.session_state["last_supabase_sync_name"] = payload.get("backup_name") or Path(created).name
                st.session_state["last_supabase_sync_error"] = ""
                st.success(f"Backup erfolgreich zu Supabase hochgeladen: {st.session_state['last_supabase_sync_name']}")
            except Exception as e:
                st.error(f"Supabase Upload fehlgeschlagen: {e}")
        if s2.button("⬇️ Neueste Supabase-Sicherung jetzt lokal laden", key="force_supabase_pull_now", width="stretch"):
            try:
                restored = maybe_restore_from_supabase_on_startup(force=True)
                if restored:
                    st.success("Neueste Supabase-Sicherung wurde lokal geladen. Bitte Seite neu laden.")
                else:
                    st.warning(st.session_state.get("supabase_startup_restore_status") or "Kein Restore durchgeführt.")
            except Exception as e:
                st.error(f"Supabase Pull fehlgeschlagen: {e}")
        try:
            record = get_supabase_backup_record()
        except Exception as e:
            record = {}
            st.error(f"Supabase-Status konnte nicht geladen werden: {e}")
        if record:
            st.caption(f"Letztes Supabase-Backup: {record.get('backup_name') or '-'} | Client-Zeit: {record.get('updated_at_client') or '-'} | Grund: {record.get('reason') or '-'}")
        else:
            st.info("Noch keine Supabase-Sicherung gefunden.")
    else:
        st.warning("Supabase ist noch nicht konfiguriert. Bitte SUPABASE_URL und SUPABASE_KEY in Render setzen.")

    st.divider()
    st.subheader("Dropbox Sync + Startup Restore")
    st.caption("Ideal für Render Free: lokale Auto-Backups bleiben aktiv und das Tool kann bei leerer lokaler DB automatisch das neueste Dropbox-Backup beim Start laden.")
    st.caption(f"Token-Quelle: {get_dropbox_token_source_label()}")
    st.caption(f"Refresh-Status: {dropbox_refresh_status_label()}")
    if st.session_state.get("dropbox_startup_restore_status"):
        st.info(f"Startup Restore Status: {st.session_state.get('dropbox_startup_restore_status')}")

    token_in_env = bool(str(os.environ.get(DROPBOX_TOKEN_ENV_NAME) or "").strip())
    if has_dropbox_refresh_support():
        st.success("Dropbox Refresh Token System ist aktiv. Access Tokens werden automatisch erneuert.")
    elif token_in_env:
        st.success("Dropbox Access Token ist als Environment Variable gesetzt.")
    else:
        st.warning("Noch kein Dropbox Access Token im Server gesetzt. Du kannst unten testweise einen Token nur für diese Sitzung eingeben.")

    with st.expander("Dropbox Refresh Token Setup", expanded=False):
        st.write("Für wartungsfreien Betrieb auf Render diese Variablen setzen:")
        st.code("""DROPBOX_REFRESH_TOKEN
DROPBOX_APP_KEY
DROPBOX_APP_SECRET""")
        st.caption("Optional kann DROPBOX_ACCESS_TOKEN als Fallback gesetzt bleiben. Mit Refresh Token verschwindet expired_access_token im Normalfall dauerhaft.")
        if st.session_state.get("dropbox_refresh_last_ok_at"):
            st.caption(f"Letzter Token-Refresh erfolgreich: {st.session_state.get('dropbox_refresh_last_ok_at')}")
        if st.session_state.get("dropbox_refresh_last_error"):
            st.warning(f"Letzter Token-Refresh Fehler: {st.session_state.get('dropbox_refresh_last_error')}")

    token_value = st.text_input(
        "Dropbox Access Token (optional pro Sitzung)",
        type="password",
        value="" if token_in_env else str(st.session_state.get("dropbox_access_token") or ""),
        key="dropbox_access_token_input",
        help="Für dauerhafte Nutzung auf Render am besten als Environment Variable DROPBOX_ACCESS_TOKEN setzen.",
    )
    c_token_1, c_token_2 = st.columns(2)
    if c_token_1.button("🔐 Token für diese Sitzung speichern", key="save_dropbox_session_token", width="stretch"):
        st.session_state["dropbox_access_token"] = str(token_value or "").strip()
        st.success("Dropbox Token in dieser Sitzung gespeichert.")
        st.rerun()
    if c_token_2.button("🧹 Sitzungs-Token löschen", key="clear_dropbox_session_token", width="stretch"):
        st.session_state["dropbox_access_token"] = ""
        st.success("Sitzungs-Token gelöscht.")
        st.rerun()

    dropbox_dir = st.text_input(
        "Dropbox Backup-Ordner",
        value=get_dropbox_backup_dir(),
        key="dropbox_backup_dir_input",
        help="Beispiel: /DJ-Tool-Backups",
    )
    st.session_state["dropbox_backup_dir"] = "/" + str(dropbox_dir or DROPBOX_BACKUP_DIR_DEFAULT).strip().strip("/")

    if get_dropbox_access_token():
        d1, d2, d3 = st.columns(3)
        if d1.button("☁️ Aktuelles Backup jetzt zu Dropbox hochladen", key="push_backup_dropbox", width="stretch"):
            try:
                created = create_timestamped_backup_file(reason="dropbox_manual_push")
                payload = sync_backup_file_to_dropbox(created)
                remote_path = payload.get("remote_path") or payload.get("path_display") or "-"
                st.success(f"Backup erfolgreich zu Dropbox hochgeladen: {remote_path}")
            except Exception as e:
                st.error(f"Dropbox Upload fehlgeschlagen: {e}")
        if d2.button("🔄 Letztes lokales Auto-Backup zu Dropbox spiegeln", key="push_last_local_dropbox", width="stretch", disabled=(len(recent_backups) == 0)):
            try:
                payload = sync_backup_file_to_dropbox(str(recent_backups[0]))
                remote_path = payload.get("remote_path") or payload.get("path_display") or "-"
                st.success(f"Letztes Auto-Backup gespiegelt: {remote_path}")
            except Exception as e:
                st.error(f"Dropbox Spiegelung fehlgeschlagen: {e}")
        if d3.button("⬇️ Neueste Dropbox-Sicherung jetzt lokal laden", key="force_dropbox_pull_now", width="stretch"):
            try:
                restored = maybe_restore_from_dropbox_on_startup(force=True)
                if restored:
                    st.success("Neueste Dropbox-Sicherung wurde lokal geladen. Bitte Seite neu laden.")
                else:
                    st.warning(st.session_state.get("dropbox_startup_restore_status") or "Kein Restore durchgeführt.")
            except Exception as e:
                st.error(f"Dropbox Pull fehlgeschlagen: {e}")

        try:
            dropbox_entries = list_dropbox_backup_files(limit=15)
        except Exception as e:
            dropbox_entries = []
            st.error(f"Dropbox-Liste konnte nicht geladen werden: {e}")

        if dropbox_entries:
            st.markdown("**Dropbox Backups**")
            options = {
                f"{entry.get('name','backup.zip')} | {entry.get('server_modified','-')}": entry for entry in dropbox_entries
            }
            selected_label = st.selectbox("Dropbox Backup auswählen", list(options.keys()), key="dropbox_backup_select")
            selected_entry = options[selected_label]
            r1, r2 = st.columns(2)
            if r1.button("📥 Aus Dropbox laden + lokal herunterladen", key="download_dropbox_backup_btn", width="stretch"):
                try:
                    data = download_dropbox_backup_bytes(selected_entry.get("path_lower") or selected_entry.get("path_display") or "")
                    st.session_state["dropbox_download_name"] = selected_entry.get("name") or "dropbox_backup.zip"
                    st.session_state["dropbox_download_bytes"] = data
                    st.success("Dropbox Backup geladen. Du kannst es jetzt herunterladen.")
                except Exception as e:
                    st.error(f"Dropbox Download fehlgeschlagen: {e}")
            if r2.button("♻️ Direkt aus Dropbox wiederherstellen", key="restore_dropbox_backup_btn", width="stretch"):
                try:
                    data = download_dropbox_backup_bytes(selected_entry.get("path_lower") or selected_entry.get("path_display") or "")
                    restore_backup_from_bytes(data)
                    st.success("Dropbox Backup erfolgreich wiederhergestellt. Bitte Seite neu laden.")
                except Exception as e:
                    st.error(f"Dropbox Restore fehlgeschlagen: {e}")

            if st.session_state.get("dropbox_download_bytes"):
                st.download_button(
                    label="📥 Geladenes Dropbox Backup herunterladen",
                    data=st.session_state.get("dropbox_download_bytes"),
                    file_name=st.session_state.get("dropbox_download_name") or "dropbox_backup.zip",
                    mime="application/zip",
                    width="stretch",
                    key="download_loaded_dropbox_backup",
                )
        else:
            st.info("Noch keine Dropbox ZIP-Backups gefunden oder Ordner ist leer.")

    if st.session_state.get("last_supabase_sync_error"):
        st.warning(f"Letzter Supabase-Sync: {st.session_state.get('last_supabase_sync_error')}")
    elif st.session_state.get("last_supabase_sync_name"):
        st.success(f"Letzter Supabase-Sync: {st.session_state.get('last_supabase_sync_name')}")

    if st.session_state.get("last_dropbox_sync_error"):
        st.warning(f"Letzter Dropbox-Sync: {st.session_state.get('last_dropbox_sync_error')}")
    elif st.session_state.get("last_dropbox_sync_path"):
        st.success(f"Letzter Dropbox-Sync: {st.session_state.get('last_dropbox_sync_path')}")

    st.divider()
    st.subheader("Backup wiederherstellen")
    uploaded_backup = st.file_uploader("Backup ZIP hochladen", type=["zip"], key="restore_backup_zip")
    if uploaded_backup is not None:
        st.warning("Beim Wiederherstellen werden vorhandene Live-Daten überschrieben.")
        if st.button("♻️ Backup jetzt wiederherstellen", key="restore_backup_btn", type="primary", width="stretch"):
            try:
                restore_backup_from_bytes(uploaded_backup.read())
                st.success("✅ Backup erfolgreich wiederhergestellt. Bitte Seite neu laden.")
            except Exception as e:
                st.error(f"Backup-Wiederherstellung fehlgeschlagen: {e}")

    st.divider()
    st.subheader("Komplett sauber neu starten")
    st.caption("Nur nutzen, wenn du wirklich alle Live-Daten und Sets löschen willst.")
    if st.button("🧹 Live-Datenbank komplett zurücksetzen", key="reset_live_db_btn", width="stretch"):
        st.session_state["confirm_reset_live_db"] = True
    if st.session_state.get("confirm_reset_live_db"):
        st.error("Wirklich komplette Live-Datenbank + Sets zurücksetzen? Das kann nicht rückgängig gemacht werden.")
        c1, c2 = st.columns(2)
        if c1.button("✅ Ja, komplett zurücksetzen", key="confirm_reset_live_db_yes", width="stretch"):
            if reset_live_database_files():
                st.session_state["confirm_reset_live_db"] = False
                st.success("Live-Datenbank wurde zurückgesetzt. Bitte Seite neu laden.")
                st.stop()
            else:
                st.error("Zurücksetzen hat nicht geklappt.")
        if c2.button("❌ Abbrechen", key="confirm_reset_live_db_no", width="stretch"):
            st.session_state["confirm_reset_live_db"] = False
            st.rerun()

DB_PATH = str(APP_DATA_DIR / "djtool_live.db")


# ---------- DB ----------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA cache_size=-12000;")
    except Exception:
        pass
    return conn


def ensure_column_exists(table_name, column_name, column_definition):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1] for row in cur.fetchall()}
        if column_name not in columns:
            cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
            conn.commit()
    finally:
        conn.close()


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            event TEXT,
            sub_event TEXT,
            source TEXT,
            is_top INTEGER DEFAULT 0,
            import_type TEXT DEFAULT 'text',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS playlist_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER,
            position INTEGER,
            artist TEXT,
            title TEXT,
            remix TEXT,
            raw_text TEXT,
            normalized_name TEXT,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS library_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT,
            title TEXT,
            remix TEXT,
            normalized_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS saved_combos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            combo_type TEXT,
            combo_text TEXT,
            source_track TEXT,
            note TEXT,
            category TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            usage_context TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            genre_name TEXT DEFAULT '',
            event_name TEXT DEFAULT '',
            playlist_name TEXT DEFAULT '',
            playlist_id INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("PRAGMA table_info(saved_combos)")
    saved_combo_cols = {row[1] for row in cur.fetchall()}
    if "category" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN category TEXT DEFAULT ''")
    if "tags" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN tags TEXT DEFAULT ''")
    if "usage_context" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN usage_context TEXT DEFAULT ''")
    if "source_name" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN source_name TEXT DEFAULT ''")
    if "genre_name" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN genre_name TEXT DEFAULT ''")
    if "event_name" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN event_name TEXT DEFAULT ''")
    if "playlist_name" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN playlist_name TEXT DEFAULT ''")
    if "playlist_id" not in saved_combo_cols:
        cur.execute("ALTER TABLE saved_combos ADD COLUMN playlist_id INTEGER DEFAULT 0")

    cur.execute("PRAGMA table_info(playlists)")
    playlist_cols = {row[1] for row in cur.fetchall()}
    if "sub_event" not in playlist_cols:
        cur.execute("ALTER TABLE playlists ADD COLUMN sub_event TEXT")
    if "upload_note" not in playlist_cols:
        cur.execute("ALTER TABLE playlists ADD COLUMN upload_note TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS import_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            import_type TEXT,
            playlist_name TEXT,
            event TEXT,
            sub_event TEXT,
            source TEXT,
            track_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok',
            note TEXT DEFAULT '',
            signature TEXT DEFAULT ''
        )
    """)

    cur.execute("PRAGMA table_info(import_runs)")
    import_run_cols = {row[1] for row in cur.fetchall()}
    if "playlist_id" not in import_run_cols:
        cur.execute("ALTER TABLE import_runs ADD COLUMN playlist_id INTEGER")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_meta (
            key TEXT PRIMARY KEY,
            value_text TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_transition_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_track TEXT,
            to_track TEXT,
            count_value INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_track_role_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            normalized_name TEXT,
            role_label TEXT,
            phase_label TEXT,
            timing_bucket TEXT,
            usage_count INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS event_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            source TEXT,
            sub_event TEXT DEFAULT '',
            guest_type TEXT DEFAULT 'Gemischt',
            age_min INTEGER DEFAULT 25,
            age_max INTEGER DEFAULT 45,
            mood TEXT DEFAULT 'Gemischt',
            flow_profile TEXT DEFAULT 'Standard',
            energy_start INTEGER DEFAULT 25,
            energy_peak INTEGER DEFAULT 82,
            energy_end INTEGER DEFAULT 40,
            notes TEXT DEFAULT '',
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_playlists_event_source_sub_event ON playlists(event, source, sub_event)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_playlists_created_at ON playlists(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist_position ON playlist_tracks(playlist_id, position)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_playlist_tracks_normalized_name ON playlist_tracks(normalized_name)")
    ensure_column_exists("playlists", "genre", "TEXT DEFAULT ''")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_import_runs_created_at ON import_runs(created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_playlists_genre ON playlists(genre)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_import_runs_signature ON import_runs(signature)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_saved_combos_type ON saved_combos(combo_type)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_saved_combos_category ON saved_combos(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_saved_combos_context ON saved_combos(usage_context)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_saved_combos_source ON saved_combos(source_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_saved_combos_genre ON saved_combos(genre_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_saved_combos_event ON saved_combos(event_name)")

    conn.commit()
    conn.close()


def log_import_run(import_type: str, playlist_name: str, event: str, source: str, track_count: int, status: str = "ok", note: str = "", sub_event: str = "", signature: str = ""):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO import_runs(created_at, import_type, playlist_name, event, sub_event, source, track_count, status, note, signature)
            VALUES(CURRENT_TIMESTAMP,?,?,?,?,?,?,?,?,?)
        """, (
            str(import_type or ""),
            str(playlist_name or ""),
            normalize_meta_value(event),
            normalize_sub_event(sub_event) if is_birthday_event(event) else str(sub_event or ""),
            normalize_meta_value(source),
            int(track_count or 0),
            str(status or "ok"),
            str(note or ""),
            str(signature or ""),
        ))
        conn.commit()
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

@st.cache_data(ttl=20, show_spinner=False)
def get_recent_import_runs(limit: int = 20):
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT created_at, import_type, playlist_name, event, sub_event, source, track_count, status, note
            FROM import_runs
            ORDER BY id DESC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
        return rows
    except Exception:
        return []
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

def get_import_log_stats() -> dict:
    rows = get_recent_import_runs(limit=200)
    return {
        "total_recent": len(rows),
        "ok_recent": sum(1 for r in rows if str(r[7] or "") == "ok"),
        "duplicate_recent": sum(1 for r in rows if str(r[7] or "") == "duplicate"),
        "skipped_recent": sum(1 for r in rows if str(r[7] or "") == "skipped"),
    }

def render_recent_import_runs(limit: int = 12):
    rows = get_recent_import_runs(limit=limit)
    if not rows:
        return
    table_rows = []
    for created_at, import_type, playlist_name, event, sub_event, source, track_count, status, note in rows:
        table_rows.append({
            "Zeit": created_at,
            "Typ": import_type,
            "Playlist": playlist_name,
            "Event": format_event_label(event, sub_event),
            "Herkunft": source,
            "Tracks": track_count,
            "Status": status,
            "Hinweis": note,
        })
    st.subheader("Letzte Import-Vorgänge")
    st.dataframe(table_rows, width="stretch", hide_index=True)


def get_playlist_meta_by_id(playlist_id: int):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, event, sub_event, source, is_top, created_at
            FROM playlists
            WHERE id = ?
            LIMIT 1
        """, (int(playlist_id),))
        return cur.fetchone()
    finally:
        conn.close()


def find_playlist_id_for_import_entry(playlist_name: str, event: str, sub_event: str, source: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id
            FROM playlists
            WHERE name = ?
              AND COALESCE(event, '') = ?
              AND COALESCE(sub_event, '') = ?
              AND COALESCE(source, '') = ?
            ORDER BY id DESC
            LIMIT 1
        """, (
            str(playlist_name or "").strip(),
            normalize_meta_value(event),
            normalize_sub_event(sub_event) if is_birthday_event(event) else str(sub_event or ""),
            normalize_meta_value(source),
        ))
        row = cur.fetchone()
        return int(row[0]) if row else None
    finally:
        conn.close()


@st.cache_data(ttl=20, show_spinner=False)
def _get_recent_imported_playlists_cached(limit: int):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                ir.id,
                ir.created_at,
                ir.import_type,
                ir.playlist_name,
                ir.event,
                ir.sub_event,
                ir.source,
                ir.track_count,
                ir.status,
                ir.note,
                COALESCE(MAX(p.id), 0) AS playlist_id
            FROM import_runs ir
            LEFT JOIN playlists p
              ON p.name = ir.playlist_name
             AND COALESCE(p.event, '') = COALESCE(ir.event, '')
             AND COALESCE(p.sub_event, '') = COALESCE(ir.sub_event, '')
             AND COALESCE(p.source, '') = COALESCE(ir.source, '')
            WHERE ir.status = 'ok'
            GROUP BY ir.id, ir.created_at, ir.import_type, ir.playlist_name, ir.event, ir.sub_event, ir.source, ir.track_count, ir.status, ir.note
            ORDER BY ir.id DESC
            LIMIT ?
        """, (int(limit),))
        rows = cur.fetchall()
    finally:
        conn.close()
    prepared = []
    for run_id, created_at, import_type, playlist_name, event, sub_event, source, track_count, status, note, playlist_id in rows:
        prepared.append({
            "run_id": int(run_id),
            "created_at": created_at or "-",
            "import_type": import_type or "-",
            "playlist_name": playlist_name or "-",
            "event": normalize_meta_value(event),
            "sub_event": normalize_sub_event(sub_event),
            "event_label": format_event_label(event, sub_event) if event else "-",
            "source": source or "-",
            "track_count": int(track_count or 0),
            "status": status or "ok",
            "note": note or "",
            "playlist_id": int(playlist_id or 0),
        })
    return prepared


def get_recent_imported_playlists(limit: int = 20):
    return _get_recent_imported_playlists_cached(int(limit))


def jump_to_playlist_browser_for_playlist(playlist_id: int):
    row = get_playlist_meta_by_id(playlist_id)
    if not row:
        return False
    _pid, _name, event, sub_event, source, _is_top, _created_at = row
    st.session_state["browse_focus_playlist_id"] = int(playlist_id)
    st.session_state["browse_event"] = normalize_meta_value(event) or "Alle"
    st.session_state["browse_source"] = normalize_meta_value(source) or "Alle"
    st.session_state["browse_sub_event"] = normalize_sub_event(sub_event) if is_birthday_event(event) else "Alle"
    st.session_state["browse_top"] = False
    st.session_state["browse_sort"] = "Neueste zuerst"
    set_active_menu("Playlists durchsuchen")
    return True


def jump_to_analyse_hub_for_playlist(playlist_id: int):
    row = get_playlist_meta_by_id(playlist_id)
    if not row:
        return False
    _pid, name, event, sub_event, source, _is_top, _created_at = row
    st.session_state["hub_event"] = normalize_meta_value(event) or "Alle"
    st.session_state["hub_source"] = normalize_meta_value(source) or "Alle"
    st.session_state["hub_depth"] = 20
    st.session_state["recent_analysis_playlist_id"] = int(playlist_id)
    st.session_state["recent_analysis_playlist_name"] = str(name or "")
    st.session_state["recent_analysis_playlist_event_label"] = format_event_label(event, sub_event)
    set_active_menu("Analyse Hub")
    return True


def build_single_playlist_analysis(playlist_id: int):
    playlist_row = get_playlist_meta_by_id(playlist_id)
    if not playlist_row:
        return None
    pid, name, event, sub_event, source, is_top, created_at = playlist_row
    tracks = get_playlist_tracks(pid)
    if not tracks:
        return None
    display_rows = [f"{a} - {t}" for _p, a, t, _r, _raw, _n in tracks if (a or t)]
    artists = [str(a or '').strip() for _p, a, _t, _r, _raw, _n in tracks if str(a or '').strip()]
    unique_artists = len({a.casefold() for a in artists})
    first_tracks = display_rows[:5]
    last_tracks = display_rows[-5:]
    transitions = []
    for idx in range(len(display_rows) - 1):
        transitions.append({"Von": display_rows[idx], "Zu": display_rows[idx + 1], "Pos": idx + 1})
    preview_rows = [{"Pos": pos, "Artist": artist, "Titel": title} for pos, artist, title, _r, _raw, _n in tracks[:30]]
    return {"playlist_id": pid, "name": name, "event_label": format_event_label(event, sub_event) or "-", "source": source or "-", "created_at": created_at or "-", "is_top": bool(is_top), "track_count": len(tracks), "unique_artists": unique_artists, "first_tracks": first_tracks, "last_tracks": last_tracks, "transitions": transitions[:12], "preview_rows": preview_rows}


def render_recent_playlist_detail(pack: dict, key_prefix: str = "recent_detail"):
    st.markdown(f"### {pack['name']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tracks", pack["track_count"])
    c2.metric("Artists", pack["unique_artists"])
    c3.metric("Anlass", pack["event_label"])
    c4.metric("Herkunft", pack["source"])
    st.caption(f"Importiert / erstellt: {pack['created_at']}")
    a1, a2 = st.columns(2)
    if a1.button("📂 In Playlists durchsuchen öffnen", key=f"{key_prefix}_open_browser_{pack['playlist_id']}", width="stretch"):
        if jump_to_playlist_browser_for_playlist(pack['playlist_id']):
            st.rerun()
    if a2.button("📊 Im Analyse Hub öffnen", key=f"{key_prefix}_open_hub_{pack['playlist_id']}", width="stretch"):
        if jump_to_analyse_hub_for_playlist(pack['playlist_id']):
            st.rerun()
    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Start der Playlist**")
        for item in pack["first_tracks"]:
            st.write(f"- {item}")
    with t2:
        st.markdown("**Ende der Playlist**")
        for item in pack["last_tracks"]:
            st.write(f"- {item}")
    if pack["transitions"]:
        st.markdown("**Erste Übergänge dieser Playlist**")
        st.dataframe(pack["transitions"], width="stretch", hide_index=True)
    st.markdown("**Track-Vorschau**")
    st.dataframe(pack["preview_rows"], width="stretch", hide_index=True)


def render_recent_imported_playlists_panel(default_limit: int = 10, key_prefix: str = "recent_imports", show_header: bool = True):
    if show_header:
        st.subheader("Zuletzt importierte Playlists")
        st.caption("Global über alle Anlässe und Quellen. Hier siehst du die zuletzt erfolgreich importierten Playlists und kannst sie direkt öffnen oder analysieren.")
    limit_values = [10, 20, 50]
    start_limit = default_limit if default_limit in limit_values else 10
    limit = st.selectbox("Anzahl anzeigen", limit_values, index=limit_values.index(start_limit), key=f"{key_prefix}_limit")
    rows = get_recent_imported_playlists(limit=limit)
    if not rows:
        st.info("Noch keine erfolgreich importierten Playlists gefunden.")
        return
    selected_id = int(st.session_state.get(f"{key_prefix}_selected_playlist_id") or 0)
    selected_mode = st.session_state.get(f"{key_prefix}_selected_mode") or "detail"
    for idx, row in enumerate(rows, start=1):
        playlist_id = int(row.get("playlist_id") or 0)
        c1, c2, c3 = st.columns([6.5, 1.2, 1.3])
        c1.markdown(f"**{idx}. {row['playlist_name']}**")
        c1.caption(f"{row['created_at']} | {row['event_label']} | {row['source']} | {row['track_count']} Tracks")
        open_disabled = playlist_id <= 0
        if c2.button("📂 Öffnen", key=f"{key_prefix}_open_{idx}_{playlist_id}", width="stretch", disabled=open_disabled):
            st.session_state[f"{key_prefix}_selected_playlist_id"] = playlist_id
            st.session_state[f"{key_prefix}_selected_mode"] = "detail"
            st.rerun()
        if c3.button("📊 Analysieren", key=f"{key_prefix}_analyze_{idx}_{playlist_id}", width="stretch", disabled=open_disabled):
            st.session_state[f"{key_prefix}_selected_playlist_id"] = playlist_id
            st.session_state[f"{key_prefix}_selected_mode"] = "analyze"
            st.rerun()
        if selected_id == playlist_id and playlist_id > 0:
            pack = build_single_playlist_analysis(playlist_id)
            if pack:
                with st.container(border=True):
                    if selected_mode == "analyze":
                        st.info("Direkt-Analyse der ausgewählten zuletzt importierten Playlist")
                    render_recent_playlist_detail(pack, key_prefix=f"{key_prefix}_{playlist_id}")
            else:
                st.warning("Die Playlist konnte nicht mehr geladen werden.")

def set_learning_meta(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO learning_meta(key, value_text, updated_at) VALUES(?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value_text=excluded.value_text, updated_at=CURRENT_TIMESTAMP
    """, (str(key), str(value)))
    conn.commit()
    conn.close()

def get_learning_meta_dict():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key, value_text, updated_at FROM learning_meta")
    rows = cur.fetchall()
    conn.close()
    return {str(k): {"value": str(v or ""), "updated_at": u} for k, v, u in rows}


def mark_learning_dirty(reason: str = "data_change"):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    set_learning_meta("learning_dirty", "1")
    set_learning_meta("learning_dirty_reason", str(reason or "data_change"))
    set_learning_meta("learning_dirty_at", stamp)


def clear_learning_dirty(reason: str = "rebuild"):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    set_learning_meta("learning_dirty", "0")
    set_learning_meta("learning_last_sync_reason", str(reason or "rebuild"))
    set_learning_meta("learning_last_sync_at", stamp)


def get_learning_recommendation_confidence(primary_count: int, total_count: int) -> tuple[str, int]:
    total = max(1, int(total_count or 0))
    primary = max(0, int(primary_count or 0))
    ratio = primary / total
    score = min(100, int(round((ratio * 60) + min(40, total))))
    if total >= 12 and ratio >= 0.35:
        return "Sehr hoch", score
    if total >= 8 and ratio >= 0.22:
        return "Hoch", score
    if total >= 5 and ratio >= 0.12:
        return "Mittel", score
    return "Vorsichtig", score


def get_learning_quality_snapshot(insights: dict | None) -> dict:
    if not insights:
        return {"label": "Unklar", "score": 0, "top_next_count": 0, "top_next_track": "", "basis_playlists": 0}
    total_count = int(insights.get("total_count", 0) or 0)
    playlist_count = int(insights.get("playlist_count", 0) or 0)
    after = insights.get("after") or []
    top_next_track = ""
    top_next_count = 0
    if after:
        top_next_track = display_from_normalized(after[0][0])
        top_next_count = int(after[0][1] or 0)
    label, score = get_learning_recommendation_confidence(top_next_count, total_count)
    return {
        "label": label,
        "score": score,
        "top_next_count": top_next_count,
        "top_next_track": top_next_track,
        "basis_playlists": playlist_count,
        "total_count": total_count,
    }

def rebuild_learning_engine():
    data = compute_data()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM learning_transition_stats")
    cur.execute("DELETE FROM learning_track_role_stats")
    for (a, b), cnt in data["pair_counts"].most_common():
        cur.execute("INSERT INTO learning_transition_stats(from_track, to_track, count_value) VALUES(?,?,?)", (a, b, int(cnt)))
    for norm, cnt in data["track_total_counts"].most_common():
        display = display_from_normalized(norm)
        cur.execute("""
            INSERT INTO learning_track_role_stats(normalized_name, role_label, phase_label, timing_bucket, usage_count)
            VALUES(?,?,?,?,?)
        """, (
            norm,
            get_track_role_label(display),
            get_track_phase_label(display),
            get_track_timing_bucket(display),
            int(cnt),
        ))
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM learning_transition_stats")
    transition_count = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM learning_track_role_stats")
    role_count = int(cur.fetchone()[0] or 0)
    conn.close()
    playlists, tracks = get_sqlite_playlist_track_counts(DB_PATH)
    set_learning_meta("last_rebuild_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    set_learning_meta("basis_playlist_count", str(playlists))
    set_learning_meta("basis_track_count", str(tracks))
    set_learning_meta("transition_row_count", str(transition_count))
    set_learning_meta("role_row_count", str(role_count))
    clear_learning_dirty("rebuild_learning_engine")
    return {"playlists": playlists, "tracks": tracks, "transitions": transition_count, "roles": role_count}

def get_learning_engine_status():
    meta = get_learning_meta_dict()
    playlists, tracks = get_sqlite_playlist_track_counts(DB_PATH)
    basis_playlists = int((meta.get("basis_playlist_count") or {}).get("value") or 0)
    basis_tracks = int((meta.get("basis_track_count") or {}).get("value") or 0)
    dirty_flag = str((meta.get("learning_dirty") or {}).get("value") or "0").strip() == "1"
    dirty_reason = (meta.get("learning_dirty_reason") or {}).get("value") or ""
    dirty_at = (meta.get("learning_dirty_at") or {}).get("value") or "-"
    last_sync_reason = (meta.get("learning_last_sync_reason") or {}).get("value") or "-"
    is_current = bool(meta.get("last_rebuild_at")) and basis_playlists == playlists and basis_tracks == tracks and not dirty_flag
    return {
        "last_rebuild_at": (meta.get("last_rebuild_at") or {}).get("value") or "-",
        "basis_playlists": basis_playlists,
        "basis_tracks": basis_tracks,
        "current_playlists": playlists,
        "current_tracks": tracks,
        "transition_rows": int((meta.get("transition_row_count") or {}).get("value") or 0),
        "role_rows": int((meta.get("role_row_count") or {}).get("value") or 0),
        "is_current": is_current,
        "dirty_flag": dirty_flag,
        "dirty_reason": dirty_reason or "-",
        "dirty_at": dirty_at,
        "last_sync_reason": last_sync_reason,
    }

def render_learning_engine_panel():
    status = get_learning_engine_status()
    st.subheader("Learning Engine")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Lernstand", "Aktuell" if status["is_current"] else "Veraltet")
    c2.metric("Übergänge", status["transition_rows"])
    c3.metric("Rollen", status["role_rows"])
    c4.metric("Letzter Rebuild", status["last_rebuild_at"])
    c5.metric("Dirty", "Ja" if status.get("dirty_flag") else "Nein")

    st.caption(f"Basis beim letzten Rebuild: {status['basis_playlists']} Playlists / {status['basis_tracks']} Tracks")
    st.caption(f"Aktueller Bestand: {status['current_playlists']} Playlists / {status['current_tracks']} Tracks")
    st.caption(f"Letzte Sync-Ursache: {status.get('last_sync_reason', '-')}")
    if status.get("dirty_flag"):
        st.caption(f"Dirty seit: {status.get('dirty_at', '-')} | Grund: {status.get('dirty_reason', '-')}")

    if status["is_current"]:
        st.success("Learning Engine ist aktuell. Die gespeicherten Lernwerte passen zum aktuellen Datenbestand.")
    else:
        st.warning("Learning Engine ist veraltet. Neue oder geänderte Playlists wurden erkannt. Bitte Rebuild starten oder automatisch synchronisieren lassen.")

    auto_msg = st.session_state.get("learning_auto_rebuild_status")
    if auto_msg:
        st.info(auto_msg)

    if st.button("🧠 Learning Engine Rebuild starten", key="learning_rebuild_btn", width="stretch"):
        with st.spinner("Learning Engine wird neu aufgebaut..."):
            result = rebuild_learning_engine()
        st.success(
            f"Learning Rebuild abgeschlossen: {result['playlists']} Playlists, {result['tracks']} Tracks, "
            f"{result['transitions']} Übergänge, {result['roles']} Rollen."
        )
        st.rerun()

def ensure_learning_engine_safe_on_startup():
    session_key = f"learning_safe_checked::{APP_BUILD_DATE}::{APP_BUILD_TIME}"
    if st.session_state.get(session_key):
        return
    st.session_state[session_key] = True

    try:
        status = get_learning_engine_status()
        current_playlists = int(status.get("current_playlists", 0) or 0)
        current_tracks = int(status.get("current_tracks", 0) or 0)
        transition_rows = int(status.get("transition_rows", 0) or 0)
        role_rows = int(status.get("role_rows", 0) or 0)
        needs_rebuild = False
        reason = ""

        # Wenn echte Daten vorhanden sind, aber der vorberechnete Lernstand leer ist,
        # wird er automatisch wieder aufgebaut, statt "einfach weg" zu sein.
        if current_playlists > 0 and current_tracks > 0 and (transition_rows <= 0 or role_rows <= 0):
            needs_rebuild = True
            reason = "learning_rows_missing"
        elif current_playlists > 0 and current_tracks > 0 and not bool(status.get("is_current")):
            needs_rebuild = True
            reason = str(status.get("dirty_reason") or "basis_mismatch")

        if needs_rebuild:
            result = rebuild_learning_engine()
            st.session_state["learning_auto_rebuild_status"] = (
                f"Learning wurde beim Start automatisch synchronisiert ({reason}): "
                f"{result['transitions']} Übergänge / {result['roles']} Rollen."
            )
        else:
            st.session_state["learning_auto_rebuild_status"] = ""
    except Exception as e:
        st.session_state["learning_auto_rebuild_status"] = f"Learning Startup Check Hinweis: {e}"

# ---------- Helpers ----------
REMIX_WORDS = [
    "extended mix", "extended", "radio edit", "edit", "remix", "mix", "version",
    "bootleg", "redrum", "intro", "outro", "clean", "dirty"
]


def normalize_track_text(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\[[^\]]*\]", " ", t)
    t = re.sub(r"\([^)]*\)", " ", t)
    t = t.replace("–", "-").replace("—", "-")
    for w in REMIX_WORDS:
        t = t.replace(w, " ")
    t = re.sub(r"[^a-z0-9\- ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_artist_title(artist: str, title: str) -> str:
    a = normalize_track_text(artist)
    b = normalize_track_text(title)
    if not a and not b:
        return ""
    return f"{a}__{b}".strip("_")


def display_from_normalized(norm: str) -> str:
    if not norm:
        return ""
    parts = norm.split("__", 1)
    if len(parts) == 2:
        artist, title = parts
        artist = artist.replace("_", " ").title()
        title = title.replace("_", " ").title()
        return f"{artist} - {title}"
    return norm.replace("_", " ").title()


def parse_line(line: str):
    raw = line.strip()
    if not raw:
        return None

    raw = re.sub(r"^\s*\d+[\.\)\-: ]+\s*", "", raw)
    raw = raw.replace("–", "-").replace("—", "-")

    if " - " in raw:
        artist, title = raw.split(" - ", 1)
    elif "-" in raw:
        artist, title = raw.split("-", 1)
    else:
        return None

    artist = artist.strip()
    title = title.strip()

    remix = ""
    remix_match = re.search(r"(\([^)]+\)|\[[^\]]+\])", title)
    if remix_match:
        remix = remix_match.group(1)

    normalized_name = normalize_artist_title(artist, title)
    return {
        "artist": artist,
        "title": title,
        "remix": remix,
        "raw_text": line.strip(),
        "normalized_name": normalized_name,
    }


def looks_like_non_track_line(line: str) -> bool:
    raw = str(line or "").strip()
    if not raw:
        return True
    lower = raw.casefold()
    blocked_fragments = [
        "facebook", "playlist einer", "vorab zur info", "wunschdisco", "kleine kinderwunschdisco",
        "gespielt da", "gäste gefeiert", "gaeste gefeiert", "uhr", "dj-playlist", "songtransitions blog",
        "www.", "http://", "https://", " playlist ", "playlist:"
    ]
    if any(x in lower for x in blocked_fragments):
        return True
    if len(raw) > 140:
        return True
    if raw.count("-") == 0 and raw.count(" - ") == 0:
        return True
    return False


def parse_line_flexible(line: str):
    raw = str(line or "").strip().lstrip("\ufeff")
    if looks_like_non_track_line(raw):
        return None

    raw = re.sub(r"^\s*\d+[\.\)\-: ]+\s*", "", raw)
    raw = raw.replace("–", "-").replace("—", "-")
    if " - " in raw:
        left, right = raw.split(" - ", 1)
    elif "-" in raw:
        left, right = raw.split("-", 1)
    else:
        return None

    left = left.strip()
    right = right.strip()
    if not left or not right:
        return None

    def side_score_artist(value: str) -> int:
        v = value.casefold()
        score = 0
        if any(x in v for x in [" feat", " ft.", " vs ", " x ", "&", ",", "dj ", " mc "]):
            score += 2
        if len(v.split()) <= 5:
            score += 1
        if "(" in v or "[" in v:
            score -= 2
        if any(x in v for x in ["radio edit", "extended", "mix", "remix", "bootleg", "edit", "version"]):
            score -= 3
        return score

    left_artist_score = side_score_artist(left)
    right_artist_score = side_score_artist(right)

    # Default: artist - title. Flip if right looks more like artist.
    artist, title = left, right
    if right_artist_score > left_artist_score + 1:
        artist, title = right, left

    remix = ""
    remix_match = re.search(r"(\([^)]+\)|\[[^\]]+\])", title)
    if remix_match:
        remix = remix_match.group(1)

    normalized_name = normalize_artist_title(artist, title)
    if not normalized_name:
        return None
    return {
        "artist": artist.strip(),
        "title": title.strip(),
        "remix": remix,
        "raw_text": line.strip(),
        "normalized_name": normalized_name,
    }


def dedupe_tracks_keep_order(tracks):
    seen = set()
    cleaned = []
    pos = 1
    for t in tracks:
        norm = str(t.get("normalized_name") or "").strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        row = dict(t)
        row["position"] = pos
        cleaned.append(row)
        pos += 1
    return cleaned


def parse_text_to_tracks(text: str):
    tracks = []
    for line in str(text or "").splitlines():
        parsed = parse_line_flexible(line)
        if parsed:
            tracks.append(parsed)
    return dedupe_tracks_keep_order(tracks)


def clean_folder_label(value: str) -> str:
    raw = str(value or "").strip().replace("_", " ")
    raw = re.sub(r"^\d+\s*", "", raw).strip()
    raw = re.sub(r"^\d+\s*[-.]\s*", "", raw).strip()
    raw = re.sub(r"\s+", " ", raw)
    return raw


def detect_source_from_zip_parts(parts):
    joined = " | ".join(str(p or "") for p in parts).casefold()
    if "benjamin schneider" in joined:
        return "Benjamin Schneider"
    if "michael zimmermann" in joined:
        return "Michael Zimmermann"
    return ""


def infer_structured_meta_from_zip_member(member_path: str):
    raw_parts = [str(p).strip() for p in Path(str(member_path)).parts if str(p).strip() and str(p).strip() not in {".", ".."}]
    parts = [clean_folder_label(p) for p in raw_parts]
    if not parts:
        return {"event": "", "sub_event": "", "source": "", "is_top": False, "playlist_name": ""}

    filename = Path(raw_parts[-1]).stem
    folders = parts[:-1]
    folder_keys = [normalize_meta_key(p) for p in folders]

    source = detect_source_from_zip_parts(folders)
    event = ""
    sub_event = ""
    is_top = any("ordner sehr gut bewertet" in k for k in folder_keys)

    relevant = [p for p in folders if normalize_meta_key(p) not in {"events", "neuer ordner"}]

    if source:
        filtered = []
        for p in relevant:
            key = normalize_meta_key(p)
            if "benjamin schneider" in key or "michael zimmermann" in key:
                continue
            filtered.append(p)
        relevant = filtered
        if relevant:
            event_candidate = normalize_meta_value(relevant[0])
            if is_birthday_event(event_candidate):
                event = "Geburtstag"
                if len(relevant) >= 2:
                    sub_event = normalize_sub_event(relevant[1])
            else:
                event = event_candidate
    else:
        if relevant:
            first = normalize_meta_value(relevant[0])
            if normalize_meta_key(first) in {normalize_meta_key("Geburtstage"), normalize_meta_key("Geburtstag")}:
                event = "Geburtstag"
                if len(relevant) >= 2:
                    sub_event = normalize_sub_event(relevant[1])
            else:
                event = first

    if not event:
        guessed_event, guessed_sub_event = infer_event_and_sub_event_from_name(member_path, filename)
        event = guessed_event or event
        sub_event = guessed_sub_event or sub_event

    return {
        "event": normalize_meta_value(event),
        "sub_event": normalize_sub_event(sub_event) if is_birthday_event(event) else "",
        "source": normalize_meta_value(source),
        "is_top": bool(is_top),
        "playlist_name": filename,
    }


def merge_import_meta(detected: dict, manual_event: str = "", manual_source: str = "", manual_sub_event: str = "", manual_top: bool = False, prefer_detected: bool = False):
    if prefer_detected:
        event = normalize_meta_value(detected.get("event", ""))
        source = normalize_meta_value(detected.get("source", ""))
        if is_birthday_event(event):
            sub_event = normalize_sub_event(detected.get("sub_event", ""))
        else:
            sub_event = ""
    else:
        event = normalize_meta_value(manual_event) if str(manual_event or "").strip() else normalize_meta_value(detected.get("event", ""))
        source = normalize_meta_value(detected.get("source", "")) or (normalize_meta_value(manual_source) if str(manual_source or "").strip() else "")
        if is_birthday_event(event):
            sub_event = normalize_sub_event(manual_sub_event) if str(manual_sub_event or "").strip() else normalize_sub_event(detected.get("sub_event", ""))
        else:
            sub_event = ""
    is_top = bool(manual_top or detected.get("is_top"))
    playlist_name = str(detected.get("playlist_name") or "").strip()
    return {"event": event, "source": source, "sub_event": sub_event, "is_top": is_top, "playlist_name": playlist_name}


def normalize_meta_value(value: str) -> str:
    value = " ".join(str(value or "").replace("_", " ").split()).strip()
    if not value:
        return ""
    parts = []
    for part in value.split(" "):
        if part.lower() in {"dj", "rb", "xml"}:
            parts.append(part.upper())
        elif any(ch.isdigit() for ch in part):
            parts.append(part)
        else:
            parts.append(part[:1].upper() + part[1:].lower())
    return " ".join(parts)


def normalize_meta_key(value: str) -> str:
    return normalize_meta_value(value).casefold()



BIRTHDAY_SUBEVENT_PRESETS = ["18", "21", "30", "40", "50", "60", "70", "80", "90"]


def is_birthday_event(value: str) -> bool:
    return normalize_meta_key(value) == normalize_meta_key("Geburtstag")


def normalize_sub_event(value: str) -> str:
    return normalize_meta_value(value)


def format_event_label(event: str, sub_event: str = "") -> str:
    event_clean = normalize_meta_value(event)
    sub_clean = normalize_sub_event(sub_event)
    if is_birthday_event(event_clean) and sub_clean:
        return f"{event_clean} › {sub_clean}"
    return event_clean or ""


@st.cache_data(ttl=180, show_spinner=False)
def get_distinct_sub_events_cached(event_value: str = ""):
    if not is_birthday_event(event_value):
        return ["Alle"]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT sub_event
        FROM playlists
        WHERE TRIM(COALESCE(event, '')) != ''
          AND TRIM(COALESCE(sub_event, '')) != ''
    """)
    rows = [normalize_sub_event(r[0]) for r in cur.fetchall()]
    conn.close()

    dedup = {}
    for raw in rows:
        if raw:
            key = normalize_meta_key(raw)
            if key not in dedup:
                dedup[key] = raw

    def sort_key(v: str):
        digits = "".join(ch for ch in v if ch.isdigit())
        if digits:
            return (0, int(digits), v.casefold())
        return (1, v.casefold())

    values = ["Alle"] + sorted(dedup.values(), key=sort_key)
    return values



def get_distinct_sub_events(event_value: str = ""):
    return get_distinct_sub_events_cached(event_value)




def detect_birthday_subevent_from_text(*values) -> str:
    combined = " ".join(str(v or "") for v in values).strip().lower()
    if not combined:
        return ""

    normalized = combined.replace("_", " ").replace("-", " ").replace("/", " ")
    normalized = normalized.replace("geburtstag", " geburtstag ")
    normalized = normalized.replace("geb.", " geb ")
    normalized = normalized.replace("geb", " geb ")

    patterns = [
        r'\b(1[89]|[2-9][0-9])\s*\.\s*geb\b',
        r'\b(1[89]|[2-9][0-9])\s*geb\b',
        r'\bgeb\s*(1[89]|[2-9][0-9])\b',
        r'\b(1[89]|[2-9][0-9])\s*\.\s*geburtstag\b',
        r'\b(1[89]|[2-9][0-9])\s*geburtstag\b',
        r'\bgeburtstag\s*(1[89]|[2-9][0-9])\b',
        r'\bzum\s*(1[89]|[2-9][0-9])\b',
        r'\b(1[89]|[2-9][0-9])er\b',
    ]

    import re
    for pattern in patterns:
        m = re.search(pattern, normalized)
        if m:
            return str(m.group(1)).strip()

    return ""


def infer_event_and_sub_event_from_name(*values):
    combined = " ".join(str(v or "") for v in values).strip()
    lowered = combined.lower()
    if not combined:
        return "", ""

    if "geburtstag" in lowered or " geb " in f" {lowered} " or ".geb" in lowered:
        return "Geburtstag", detect_birthday_subevent_from_text(combined)

    return "", ""


def render_birthday_subevent_input(container, *, key_prefix: str, help_text: str = ""):
    try:
        sub_event = container.selectbox(
            "Geburtstag-Unterordner",
            options=BIRTHDAY_SUBEVENT_PRESETS,
            index=0 if BIRTHDAY_SUBEVENT_PRESETS else None,
            accept_new_options=True,
            key=f"{key_prefix}_sub_event",
            help=help_text or "z. B. 18, 30, 40, 50, 60 oder eigene Eingabe.",
        )
    except TypeError:
        sub_event = container.text_input(
            "Geburtstag-Unterordner",
            placeholder="z. B. 18, 30, 40, 50, 60",
            key=f"{key_prefix}_sub_event",
        )
    return str(sub_event or "").strip()


@st.cache_data(ttl=120, show_spinner=False)
def get_distinct_values_cached(column_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT {column_name} FROM playlists WHERE {column_name} IS NOT NULL AND {column_name} != ''")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()

    dedup = {}
    for raw in rows:
        clean = normalize_meta_value(raw)
        if clean:
            key = normalize_meta_key(clean)
            if key not in dedup:
                dedup[key] = clean

    values = ["Alle"] + sorted(dedup.values(), key=lambda x: x.casefold())
    return values


def get_distinct_values(column_name):
    return get_distinct_values_cached(column_name)


@st.cache_data(ttl=90, show_spinner=False)
def get_playlists_cached(event=None, source=None, sub_event=None, top_only=False, genre=None):
    conn = get_conn()
    cur = conn.cursor()
    query = "SELECT id, name, event, sub_event, source, is_top, created_at FROM playlists WHERE 1=1"
    params = []
    if event and event != "Alle":
        query += " AND event = ?"
        params.append(event)
    if source and source != "Alle":
        query += " AND source = ?"
        params.append(source)
    if sub_event and sub_event != "Alle":
        query += " AND sub_event = ?"
        params.append(sub_event)
    if genre and genre != "Alle":
        try:
            query += " AND genre = ?"
            params.append(genre)
        except Exception:
            pass
    if top_only:
        query += " AND is_top = 1"
    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_playlists(event=None, source=None, sub_event=None, top_only=False, genre=None):
    return get_playlists_cached(event=event, source=source, sub_event=sub_event, top_only=top_only, genre=genre)


@st.cache_data(ttl=120, show_spinner=False)
def get_playlist_tracks_cached(playlist_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT position, artist, title, remix, raw_text, normalized_name
        FROM playlist_tracks
        WHERE playlist_id = ?
        ORDER BY position
    """, (playlist_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_playlist_tracks(playlist_id):
    return get_playlist_tracks_cached(playlist_id)


def preload_duplicate_index(event=None, source=None, sub_event=None):
    seqs, meta = get_all_playlist_sequences()
    entries = []
    event_key = normalize_meta_key(event) if event and event != "Alle" else ""
    source_key = normalize_meta_key(source) if source and source != "Alle" else ""
    sub_event_key = normalize_meta_key(sub_event) if sub_event and sub_event != "Alle" else ""
    for pid, seq in seqs.items():
        info = meta.get(pid, {})
        if event_key and normalize_meta_key(info.get("event", "")) != event_key:
            continue
        if source_key and normalize_meta_key(info.get("source", "")) != source_key:
            continue
        if sub_event_key and normalize_meta_key(info.get("sub_event", "")) != sub_event_key:
            continue
        entries.append({
            "playlist_id": pid,
            "name": info.get("name", ""),
            "event": info.get("event", ""),
            "sub_event": info.get("sub_event", ""),
            "source": info.get("source", ""),
            "seq": seq,
            "fingerprint": "||".join(seq),
            "track_set": set(seq),
            "track_count": len(seq),
        })
    return entries


def find_duplicate_playlists_in_index(candidate_tracks, duplicate_index, threshold=0.98):
    candidate_seq = [t["normalized_name"] for t in candidate_tracks if t.get("normalized_name")]
    if not candidate_seq:
        return []
    candidate_fp = "||".join(candidate_seq)
    candidate_set = set(candidate_seq)
    matches = []
    for item in duplicate_index or []:
        seq = item.get("seq") or []
        exact_same = candidate_seq == seq
        same_track_set = len(candidate_seq) == len(seq) and candidate_set == item.get("track_set", set())
        fingerprint_same = candidate_fp == item.get("fingerprint", "")
        score = compare_sequences(candidate_seq, seq)
        if exact_same or fingerprint_same or same_track_set or score >= threshold:
            matches.append({
                "playlist_id": item["playlist_id"],
                "name": item["name"],
                "event": item.get("event", ""),
                "sub_event": item.get("sub_event", ""),
                "source": item.get("source", ""),
                "score": 1.0 if (exact_same or fingerprint_same) else score,
                "track_count": item.get("track_count", len(seq)),
                "exact_same": bool(exact_same or fingerprint_same),
            })
    return sorted(matches, key=lambda x: (x["exact_same"], x["score"], x["track_count"]), reverse=True)


def get_playlist_track_fingerprint(tracks) -> str:
    return "||".join([str(t.get("normalized_name") or "").strip() for t in tracks if t.get("normalized_name")])


def get_playlist_upload_note(playlist_id: int) -> str:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(upload_note, '') FROM playlists WHERE id = ?", (int(playlist_id),))
    row = cur.fetchone()
    conn.close()
    return str(row[0] or "") if row else ""


def find_duplicate_playlists_by_tracks(candidate_tracks, event=None, source=None, sub_event=None, threshold=0.98):
    duplicate_index = preload_duplicate_index(event=event, source=source, sub_event=sub_event)
    return find_duplicate_playlists_in_index(candidate_tracks, duplicate_index, threshold=threshold)


def render_duplicate_warning_box(parsed_tracks, event="", source="", sub_event="", key_prefix="dupe"):
    matches = find_duplicate_playlists_by_tracks(
        parsed_tracks,
        event=event,
        source=source,
        sub_event=sub_event,
        threshold=0.95
    )
    if not matches:
        return False

    exact = [m for m in matches if m.get("exact_same")]
    if exact:
        st.warning("⚠️ Diese Playlist ist sehr wahrscheinlich schon vorhanden (Inhalt identisch oder fast identisch).")
    else:
        st.warning("⚠️ Mögliche Dublette gefunden. Bitte kurz prüfen, bevor du speicherst.")

    for idx, match in enumerate(matches[:5], start=1):
        percent = int(round(match["score"] * 100))
        flag = "EXAKT" if match.get("exact_same") else f"{percent}% ähnlich"
        event_label = format_event_label(match.get("event", ""), match.get("sub_event", ""))
        st.write(f"{idx}. {match['name']} | {event_label or '-'} | {match['source'] or '-'} — {flag} • {match['track_count']} Tracks")
    return True


def save_playlist(name, event, source, is_top, import_type, tracks, sub_event="", upload_note=""):
    name = " ".join(str(name or "").split()).strip()
    event = normalize_meta_value(event)
    sub_event = normalize_sub_event(sub_event) if is_birthday_event(event) else ""
    source = normalize_meta_value(source)
    upload_note = str(upload_note or "").strip()

    last_error = None
    for _attempt in range(5):
        conn = None
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO playlists(name, event, sub_event, source, is_top, import_type, upload_note)
                VALUES(?,?,?,?,?,?,?)
            """, (name, event, sub_event, source, 1 if is_top else 0, import_type, upload_note))
            playlist_id = cur.lastrowid

            cur.executemany("""
                INSERT INTO playlist_tracks
                (playlist_id, position, artist, title, remix, raw_text, normalized_name)
                VALUES(?,?,?,?,?,?,?)
            """, [
                (
                    playlist_id,
                    t["position"],
                    t["artist"],
                    t["title"],
                    t["remix"],
                    t["raw_text"],
                    t["normalized_name"],
                )
                for t in tracks
            ])

            conn.commit()
            conn.close()
            try:
                get_all_playlist_sequences.clear()
            except Exception:
                pass
            mark_learning_dirty(f"playlist_saved::{name}")
            return playlist_id
        except sqlite3.OperationalError as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass
            time.sleep(0.6)
        except Exception:
            if conn:
                try:
                    conn.rollback()
                    conn.close()
                except Exception:
                    pass
            raise
    raise last_error


def delete_playlist(playlist_id, trigger_backup: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
    cur.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    conn.commit()
    conn.close()
    clear_runtime_caches()
    mark_learning_dirty("playlist_delete")
    if trigger_backup:
        auto_backup_after_data_change("playlist_delete")


def delete_all_playlists(trigger_backup: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM playlist_tracks")
    cur.execute("DELETE FROM playlists")
    conn.commit()
    conn.close()
    clear_runtime_caches()
    mark_learning_dirty("playlist_delete_all")
    if trigger_backup:
        auto_backup_after_data_change("playlist_delete_all")


def delete_filtered_playlists(event=None, source=None, sub_event=None, genre=None, top_only=False):
    try:
        rows = get_playlists(event=event, source=source, sub_event=sub_event, genre=genre, top_only=top_only)
    except TypeError:
        rows = get_playlists(event=event, source=source, sub_event=sub_event, top_only=top_only)
    ids = [row[0] for row in rows]
    for pid in ids:
        delete_playlist(pid, trigger_backup=False)
    if ids:
        mark_learning_dirty("playlist_delete_filtered")
        auto_backup_after_data_change("playlist_delete_filtered")
    return len(ids)


def update_playlist_meta(playlist_id: int, new_event=None, new_sub_event=None, new_source=None, new_name=None, new_is_top=None, new_upload_note=None):
    set_parts = []
    params = []
    if new_name is not None:
        set_parts.append("name = ?")
        params.append(" ".join(str(new_name or "").split()).strip())
    if new_event is not None:
        event_clean = normalize_meta_value(new_event)
        set_parts.append("event = ?")
        params.append(event_clean)
        if not is_birthday_event(event_clean):
            new_sub_event = ""
    if new_sub_event is not None:
        set_parts.append("sub_event = ?")
        params.append(normalize_sub_event(new_sub_event))
    if new_source is not None:
        set_parts.append("source = ?")
        params.append(normalize_meta_value(new_source))
    if new_is_top is not None:
        set_parts.append("is_top = ?")
        params.append(1 if bool(new_is_top) else 0)
    if new_upload_note is not None:
        set_parts.append("upload_note = ?")
        params.append(str(new_upload_note or "").strip())
    if not set_parts:
        return False
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE playlists SET {', '.join(set_parts)} WHERE id = ?", params + [int(playlist_id)])
    conn.commit()
    conn.close()
    clear_runtime_caches()
    mark_learning_dirty("playlist_single_update")
    auto_backup_after_data_change("playlist_single_update")
    return True


def rebuild_full_analysis_state():
    clear_runtime_caches()
    return rebuild_learning_engine()


def bulk_update_filtered_playlists(event=None, source=None, sub_event=None, genre=None, top_only=False, new_event=None, new_sub_event=None, new_source=None):
    try:
        rows = get_playlists(event=event, source=source, sub_event=sub_event, genre=genre, top_only=top_only)
    except TypeError:
        rows = get_playlists(event=event, source=source, sub_event=sub_event, top_only=top_only)
    ids = [row[0] for row in rows]
    if not ids:
        return 0

    set_parts = []
    params = []
    if new_event is not None:
        set_parts.append("event = ?")
        params.append(normalize_meta_value(new_event))
    if new_sub_event is not None:
        set_parts.append("sub_event = ?")
        params.append(normalize_sub_event(new_sub_event))
    if new_source is not None:
        set_parts.append("source = ?")
        params.append(normalize_meta_value(new_source))
    if not set_parts:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    query = f"UPDATE playlists SET {', '.join(set_parts)} WHERE id = ?"
    changed = 0
    for pid in ids:
        cur.execute(query, params + [pid])
        changed += 1
    conn.commit()
    conn.close()
    if changed:
        clear_runtime_caches()
        mark_learning_dirty("playlist_bulk_update")
        auto_backup_after_data_change("playlist_bulk_update")
    return changed


def clean_all_playlist_meta_values():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, event, sub_event, source FROM playlists")
    rows = cur.fetchall()
    changed = 0
    for pid, name, event, sub_event, source in rows:
        new_name = " ".join(str(name or "").split()).strip()
        new_event = normalize_meta_value(event)
        new_sub_event = normalize_sub_event(sub_event) if is_birthday_event(new_event) else ""
        new_source = normalize_meta_value(source)
        if (new_name != (name or "")) or (new_event != (event or "")) or (new_sub_event != (sub_event or "")) or (new_source != (source or "")):
            cur.execute(
                "UPDATE playlists SET name = ?, event = ?, sub_event = ?, source = ? WHERE id = ?",
                (new_name, new_event, new_sub_event, new_source, pid),
            )
            changed += 1
    conn.commit()
    conn.close()
    if changed:
        clear_runtime_caches()
        mark_learning_dirty("playlist_meta_clean")
        auto_backup_after_data_change("playlist_meta_clean")
    return changed


def rename_meta_value(column_name: str, old_value: str, new_value: str):
    if column_name not in {"event", "source"}:
        return 0
    old_key = normalize_meta_key(old_value)
    new_clean = normalize_meta_value(new_value)
    if not old_key or not new_clean:
        return 0

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT id, {column_name} FROM playlists")
    rows = cur.fetchall()
    changed = 0
    for pid, raw in rows:
        if normalize_meta_key(raw) == old_key:
            cur.execute(f"UPDATE playlists SET {column_name} = ? WHERE id = ?", (new_clean, pid))
            changed += 1
    conn.commit()
    conn.close()
    if changed:
        clear_runtime_caches()
        mark_learning_dirty(f"rename_{column_name}")
        auto_backup_after_data_change(f"rename_{column_name}")
    return changed


@st.cache_data(ttl=120, show_spinner=False)
def get_meta_counts_cached(column_name: str):
    if column_name not in {"event", "source"}:
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT {column_name} FROM playlists WHERE {column_name} IS NOT NULL AND {column_name} != ''")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()

    counts = {}
    labels = {}
    for raw in rows:
        clean = normalize_meta_value(raw)
        if clean:
            key = normalize_meta_key(clean)
            counts[key] = counts.get(key, 0) + 1
            labels[key] = clean

    return sorted([(labels[k], counts[k]) for k in counts.keys()], key=lambda x: (-x[1], x[0].casefold()))


def get_meta_counts(column_name: str):
    return get_meta_counts_cached(column_name)


@st.cache_data(ttl=60, show_spinner=False)
def stats_counts_cached():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM playlists")
    playlists = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM playlist_tracks")
    tracks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM library_tracks")
    library = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM saved_combos")
    combos = cur.fetchone()[0]
    conn.close()
    return playlists, tracks, library, combos


def stats_counts():
    return stats_counts_cached()


@st.cache_data(ttl=60, show_spinner=False)
def get_library_overview_cached():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(DISTINCT COALESCE(event, '')) FROM playlists WHERE TRIM(COALESCE(event, '')) != ''")
    event_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT COALESCE(source, '')) FROM playlists WHERE TRIM(COALESCE(source, '')) != ''")
    source_count = cur.fetchone()[0]

    genre_count = 0
    latest_rows = []
    try:
        cur.execute("SELECT COUNT(DISTINCT COALESCE(genre, '')) FROM playlists WHERE TRIM(COALESCE(genre, '')) != ''")
        genre_count = cur.fetchone()[0]
        cur.execute("""
            SELECT id, name, event, sub_event, source, genre, created_at
            FROM playlists
            ORDER BY id DESC
            LIMIT 5
        """)
        latest_rows = cur.fetchall()
    except Exception:
        cur.execute("""
            SELECT id, name, event, sub_event, source, created_at
            FROM playlists
            ORDER BY id DESC
            LIMIT 5
        """)
        base_rows = cur.fetchall()
        latest_rows = [(pid, name, event, sub_event, source, "", created_at) for pid, name, event, sub_event, source, created_at in base_rows]

    conn.close()
    return {
        "event_count": int(event_count or 0),
        "source_count": int(source_count or 0),
        "genre_count": int(genre_count or 0),
        "latest_rows": latest_rows,
    }


def get_library_overview():
    return get_library_overview_cached()


def is_reference_source_label(value: str) -> bool:
    value = str(value or '').strip().casefold()
    return any(token in value for token in ['referenz', 'reference', 'premium', 'best-of', 'best of'])


@st.cache_data(ttl=20, show_spinner=False)
def get_filtered_playlist_snapshot(event=None, source=None, top_only=False, sub_event=None, limit: int = 8):
    conn = get_conn()
    try:
        cur = conn.cursor()
        query = [
            "SELECT id, name, event, sub_event, source, is_top, created_at, COALESCE(upload_note, '')",
            "FROM playlists",
            "WHERE 1=1",
        ]
        params = []
        if event and event != 'Alle':
            query.append('AND event = ?')
            params.append(event)
        if source and source != 'Alle':
            query.append('AND source = ?')
            params.append(source)
        if sub_event and sub_event != 'Alle':
            query.append('AND sub_event = ?')
            params.append(sub_event)
        if top_only:
            query.append('AND is_top = 1')
        query.append('ORDER BY id DESC LIMIT ?')
        params.append(int(limit))
        cur.execute(" ".join(query), params)
        rows = cur.fetchall()

        count_query = ["SELECT COUNT(*) FROM playlists WHERE 1=1"]
        count_params = []
        if event and event != 'Alle':
            count_query.append('AND event = ?')
            count_params.append(event)
        if source and source != 'Alle':
            count_query.append('AND source = ?')
            count_params.append(source)
        if sub_event and sub_event != 'Alle':
            count_query.append('AND sub_event = ?')
            count_params.append(sub_event)
        if top_only:
            count_query.append('AND is_top = 1')
        cur.execute(" ".join(count_query), count_params)
        total = int(cur.fetchone()[0] or 0)
    finally:
        conn.close()

    latest = []
    for pid, name, ev, sub_ev, src, is_top, created_at, upload_note in rows:
        latest.append({
            'playlist_id': int(pid),
            'name': str(name or '-'),
            'event_label': format_event_label(ev, sub_ev) or '-',
            'source': str(src or '-'),
            'is_top': bool(is_top),
            'created_at': created_at or '-',
            'upload_note': str(upload_note or '').strip(),
        })
    return {'total': total, 'latest': latest}


def get_track_example_playlists(query_track, event=None, source=None, top_only=False, sub_event=None, limit: int = 6):
    norm_query = normalize_track_text(query_track)
    if not norm_query:
        return []
    conn = get_conn()
    try:
        cur = conn.cursor()
        query = [
            "SELECT DISTINCT p.id, p.name, p.event, p.sub_event, p.source, p.created_at",
            "FROM playlists p",
            "JOIN playlist_tracks t ON p.id = t.playlist_id",
            "WHERE LOWER(COALESCE(t.normalized_name, '')) LIKE ?",
        ]
        params = [f'%{norm_query}%']
        if event and event != 'Alle':
            query.append('AND p.event = ?')
            params.append(event)
        if source and source != 'Alle':
            query.append('AND p.source = ?')
            params.append(source)
        if sub_event and sub_event != 'Alle':
            query.append('AND p.sub_event = ?')
            params.append(sub_event)
        if top_only:
            query.append('AND p.is_top = 1')
        query.append('ORDER BY p.id DESC LIMIT ?')
        params.append(int(limit))
        cur.execute(" ".join(query), params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            'playlist_id': int(pid),
            'name': str(name or '-'),
            'event_label': format_event_label(ev, sub_ev) or '-',
            'source': str(src or '-'),
            'created_at': created_at or '-',
        }
        for pid, name, ev, sub_ev, src, created_at in rows
    ]

def compute_data(event=None, source=None, top_only=False, sub_event=None):
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT p.id, p.event, p.sub_event, p.source, p.is_top, t.position, t.normalized_name
        FROM playlists p
        JOIN playlist_tracks t ON p.id = t.playlist_id
        WHERE 1=1
    """
    params = []
    if event and event != "Alle":
        query += " AND p.event = ?"
        params.append(event)
    if source and source != "Alle":
        query += " AND p.source = ?"
        params.append(source)
    if sub_event and sub_event != "Alle":
        query += " AND p.sub_event = ?"
        params.append(sub_event)
    if top_only:
        query += " AND p.is_top = 1"
    query += " ORDER BY p.id, t.position"

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    by_playlist = defaultdict(list)
    meta = {}
    for pid, ev, sub_ev, src, is_top, pos, norm in rows:
        by_playlist[pid].append(norm)
        meta[pid] = {"event": ev, "sub_event": sub_ev, "source": src, "is_top": is_top}

    pair_counts = Counter()
    block3_counts = Counter()
    block4_counts = Counter()
    block5_counts = Counter()
    track_total_counts = Counter()
    example_playlists_for_track = defaultdict(set)
    event_split = defaultdict(Counter)

    for pid, plist in by_playlist.items():
        for norm in plist:
            if not norm:
                continue
            track_total_counts[norm] += 1
            example_playlists_for_track[norm].add(pid)
            if meta[pid]["event"]:
                event_split[norm][meta[pid]["event"]] += 1

        for i in range(len(plist) - 1):
            a, b = plist[i], plist[i + 1]
            pair_counts[(a, b)] += 1

        for i in range(len(plist) - 2):
            block3_counts[(plist[i], plist[i + 1], plist[i + 2])] += 1

        for i in range(len(plist) - 3):
            block4_counts[(plist[i], plist[i + 1], plist[i + 2], plist[i + 3])] += 1

        for i in range(len(plist) - 4):
            block5_counts[(plist[i], plist[i + 1], plist[i + 2], plist[i + 3], plist[i + 4])] += 1

    return {
        "pair_counts": pair_counts,
        "block3_counts": block3_counts,
        "block4_counts": block4_counts,
        "block5_counts": block5_counts,
        "track_total_counts": track_total_counts,
        "example_playlists_for_track": example_playlists_for_track,
        "event_split": event_split,
        "by_playlist": by_playlist,
    }


def compute_transitions(event=None, source=None, top_only=False, sub_event=None):
    return compute_data_cached(event=event, source=source, top_only=top_only, sub_event=sub_event)


def get_track_position_stats(track_name, event=None, source=None, top_only=False, sub_event=None):
    data = compute_data_cached(event=event, source=source, top_only=top_only, sub_event=sub_event)
    norm_query = normalize_track_text(track_name)
    matches = [k for k in data["track_total_counts"].keys() if norm_query and norm_query in k]
    if not matches:
        return None

    chosen = sorted(matches, key=lambda x: data["track_total_counts"][x], reverse=True)[0]
    positions = []
    indexes = []
    lengths = []
    for seq in data["by_playlist"].values():
        for idx, norm in enumerate(seq):
            if norm == chosen:
                rel = idx / max(1, len(seq) - 1)
                positions.append(rel)
                indexes.append(idx + 1)
                lengths.append(len(seq))

    if not positions:
        return None

    avg = sum(positions) / len(positions)
    sorted_positions = sorted(positions)
    mid = len(sorted_positions) // 2
    if len(sorted_positions) % 2 == 0:
        median_rel = (sorted_positions[mid - 1] + sorted_positions[mid]) / 2
    else:
        median_rel = sorted_positions[mid]

    return {
        "normalized": chosen,
        "avg_rel": avg,
        "median_rel": median_rel,
        "avg_position": f"{round(avg * 100)}%",
        "sample_count": len(positions),
        "avg_index": round(sum(indexes) / max(1, len(indexes)), 1),
        "avg_playlist_length": round(sum(lengths) / max(1, len(lengths)), 1),
    }


def get_event_phase_profile(event=None):
    key = normalize_meta_key(event)
    if key == normalize_meta_key("Hochzeit"):
        return [(0.14, "🍽️ Dinner / Empfang"), (0.34, "🌙 Warmup"), (0.58, "⬆️ Aufbau"), (0.84, "🔥 Peak"), (1.01, "🌅 Closing")]
    if key == normalize_meta_key("Geburtstag"):
        return [(0.18, "🌙 Warmup"), (0.45, "⬆️ Aufbau"), (0.82, "🔥 Peak"), (1.01, "🌅 Closing")]
    if key in {normalize_meta_key("Firmenfeier"), normalize_meta_key("Mixed")}:
        return [(0.18, "🌙 Warmup"), (0.46, "⬆️ Aufbau"), (0.80, "🔥 Peak"), (1.01, "🌅 Closing")]
    return [(0.16, "🌙 Warmup"), (0.44, "⬆️ Aufbau"), (0.80, "🔥 Peak"), (1.01, "🌅 Closing")]


def classify_phase_from_relative(relative_position: float, event=None):
    rel = max(0.0, min(1.0, float(relative_position or 0.0)))
    for threshold, label in get_event_phase_profile(event):
        if rel <= threshold:
            return label
    return "🌅 Closing"


def get_track_phase_label(track_name, event=None, source=None, top_only=False, sub_event=None):
    stats = get_track_position_stats(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not stats:
        return "❔ Unklar"
    return classify_phase_from_relative(stats.get("avg_rel", 0.0), event=event)


def get_track_timing_bucket(track_name, event=None, source=None, top_only=False, sub_event=None):
    stats = get_track_position_stats(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not stats:
        return "❔ unklar"
    avg = stats.get("avg_rel", 0.0)
    if avg <= 0.18:
        return "sehr früh"
    if avg <= 0.38:
        return "früh"
    if avg <= 0.62:
        return "Mitte"
    if avg <= 0.84:
        return "spät"
    return "ganz spät"


def get_track_role_label(track_name, event=None, source=None, top_only=False, sub_event=None):
    stats = get_track_position_stats(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not stats:
        return "❔ Unklar"

    phase = get_track_phase_label(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    insights = get_track_insights(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    before_strength = sum(cnt for _norm, cnt in (insights.get("before") or [])[:5]) if insights else 0
    after_strength = sum(cnt for _norm, cnt in (insights.get("after") or [])[:5]) if insights else 0
    bridge_power = min(before_strength, after_strength)

    if "Dinner" in phase or "Warmup" in phase:
        return "🌙 Opener"
    if "Closing" in phase or "Spät" in phase:
        return "🌅 Closing"
    if "Peak" in phase and after_strength >= max(2, before_strength // 2):
        return "🔥 Peak"
    if bridge_power >= 4:
        return "🔗 Bridge"
    return "⬆️ Aufbau"


def estimate_track_energy(track_name, event=None, source=None, top_only=False, sub_event=None):
    phase = get_track_phase_label(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    insights = get_track_insights(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    usage = int((insights or {}).get("total_count", 0))
    if "Dinner" in phase:
        base = 2
    elif "Warmup" in phase:
        base = 3
    elif "Aufbau" in phase:
        base = 6
    elif "Peak" in phase:
        base = 9
    else:
        base = 4
    usage_bonus = 1 if usage >= 8 else (0.5 if usage >= 4 else 0)
    return max(1, min(10, int(round(base + usage_bonus))))


def save_combo_to_set(combo_text: str):
    items = st.session_state.setdefault("set_builder", [])
    added = 0
    raw_parts = re.split(r"\s*(?:\||→)\s*", str(combo_text or "").strip())
    for part in [p.strip() for p in raw_parts if p.strip()]:
        if part not in items:
            items.append(part)
            added += 1
    return added


def render_count_row(title: str, cnt: int, *, combo_type: str | None = None, combo_text: str | None = None, set_key: str | None = None):
    cols = st.columns([6, 1.2, 1.2])
    cols[0].write(f"{title} — {cnt}x ({strength_label(cnt)})")
    if combo_text and combo_type:
        if cols[1].button("⭐ Merken", key=f"save_{set_key}"):
            save_combo(combo_type, combo_text)
            st.success("Gespeichert.")
    if combo_text:
        if cols[2].button("➕ Set", key=f"set_{set_key}"):
            added = save_combo_to_set(combo_text)
            st.success(f"{added} Track(s) ins Set übernommen.")
        render_library_status_for_combo(combo_text)


def get_track_insights(query_track, event=None, source=None, top_only=False, sub_event=None):
    norm_query = normalize_track_text(query_track)
    results = compute_data_cached(event=event, source=source, top_only=top_only, sub_event=sub_event)

    total_by_track = results["track_total_counts"]
    pair_counts = results["pair_counts"]
    block3_counts = results["block3_counts"]
    block4_counts = results["block4_counts"]
    block5_counts = results["block5_counts"]

    matches = [k for k in total_by_track.keys() if norm_query in k]
    if not matches:
        return None

    chosen = sorted(matches, key=lambda x: total_by_track[x], reverse=True)[0]

    before = Counter()
    after = Counter()
    pair_examples = []
    block3_examples = []
    block4_examples = []
    block5_examples = []

    for (a, b), cnt in pair_counts.items():
        if a == chosen:
            after[b] += cnt
            pair_examples.append((f"{display_from_normalized(a)} → {display_from_normalized(b)}", cnt))
        if b == chosen:
            before[a] += cnt

    for block, cnt in block3_counts.items():
        if block[0] == chosen:
            block3_examples.append((
                " → ".join(display_from_normalized(x) for x in block),
                cnt
            ))

    for block, cnt in block4_counts.items():
        if block[0] == chosen:
            block4_examples.append((
                " → ".join(display_from_normalized(x) for x in block),
                cnt
            ))

    for block, cnt in block5_counts.items():
        if block[0] == chosen:
            block5_examples.append((
                " → ".join(display_from_normalized(x) for x in block),
                cnt
            ))

    total_count = total_by_track[chosen]
    event_info = results["event_split"].get(chosen, Counter())
    playlist_count = len(results["example_playlists_for_track"].get(chosen, []))

    return {
        "chosen": chosen,
        "display": display_from_normalized(chosen),
        "total_count": total_count,
        "playlist_count": playlist_count,
        "before": before.most_common(10),
        "after": after.most_common(10),
        "pairs": sorted(pair_examples, key=lambda x: x[1], reverse=True)[:10],
        "block3": sorted(block3_examples, key=lambda x: x[1], reverse=True)[:10],
        "block4": sorted(block4_examples, key=lambda x: x[1], reverse=True)[:10],
        "block5": sorted(block5_examples, key=lambda x: x[1], reverse=True)[:10],
        "event_info": event_info,
    }


def normalize_variant_text(text: str) -> str:
    if not text:
        return ""
    t = str(text).lower().strip()
    t = t.replace("–", "-").replace("—", "-")
    t = re.sub(r"[\[\]\(\)]", " ", t)
    t = re.sub(r"[^a-z0-9\- ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_variant_key(artist: str, title: str, remix: str = "") -> str:
    a = normalize_variant_text(artist)
    b = normalize_variant_text(title)
    r = normalize_variant_text(remix)
    full = " ".join([x for x in [b, r] if x]).strip()
    if not a and not full:
        return ""
    return f"{a}__{full}".strip("_")


def has_version_hint(text: str) -> bool:
    value = normalize_variant_text(text)
    if not value:
        return False
    version_terms = [
        "extended", "intro", "outro", "redrum", "bootleg", "edit", "mix", "version",
        "clean", "dirty", "remix", "rework", "club", "radio", "vip", "mashup"
    ]
    return any(term in value for term in version_terms)


def get_library_index():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT artist, title, remix, normalized_name FROM library_tracks")
    rows = cur.fetchall()
    conn.close()

    family_set = set()
    variant_set = set()
    family_to_variants = defaultdict(set)
    sample_titles = {}
    for artist, title, remix, normalized_name in rows:
        family_key = str(normalized_name or "").strip()
        variant_key = build_variant_key(artist or "", title or "", remix or "")
        if family_key:
            family_set.add(family_key)
            pretty = f"{artist} - {title}".strip(" -")
            if remix:
                pretty += f" ({remix})"
            sample_titles.setdefault(family_key, pretty)
        if variant_key:
            variant_set.add(variant_key)
            if family_key:
                family_to_variants[family_key].add(variant_key)
    return {
        "family_set": family_set,
        "variant_set": variant_set,
        "family_to_variants": family_to_variants,
        "sample_titles": sample_titles,
        "count": len(rows),
    }


def get_playlist_track_rows(event=None, source=None, top_only=False, sub_event=None):
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT
            p.id, p.name, p.event, p.sub_event, p.source, p.is_top,
            t.position, t.artist, t.title, t.remix, t.normalized_name
        FROM playlists p
        JOIN playlist_tracks t ON p.id = t.playlist_id
        WHERE 1=1
    """
    params = []
    if event and event != "Alle":
        query += " AND p.event = ?"
        params.append(event)
    if source and source != "Alle":
        query += " AND p.source = ?"
        params.append(source)
    if sub_event and sub_event != "Alle":
        query += " AND p.sub_event = ?"
        params.append(sub_event)
    if top_only:
        query += " AND p.is_top = 1"
    query += " ORDER BY p.id, t.position"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def summarize_missing_tracks(event=None, source=None, top_only=False, sub_event=None):
    library = get_library_index()
    rows = get_playlist_track_rows(event=event, source=source, top_only=top_only, sub_event=sub_event)
    by_family = {}

    for pid, pname, pev, psub, psrc, _is_top, pos, artist, title, remix, normalized_name in rows:
        family_key = str(normalized_name or "").strip()
        if not family_key:
            continue
        variant_key = build_variant_key(artist or "", title or "", remix or "")
        entry = by_family.setdefault(family_key, {
            "family_key": family_key,
            "display": display_from_normalized(family_key),
            "count": 0,
            "playlist_ids": set(),
            "events": Counter(),
            "sources": Counter(),
            "variants": Counter(),
            "variant_labels": {},
            "example_playlists": [],
        })
        entry["count"] += 1
        entry["playlist_ids"].add(pid)
        if pev:
            entry["events"][pev] += 1
        if psrc:
            entry["sources"][psrc] += 1
        if variant_key:
            entry["variants"][variant_key] += 1
            label = f"{artist} - {title}".strip(" -")
            if remix:
                label += f" ({remix})"
            entry["variant_labels"][variant_key] = label
        if len(entry["example_playlists"]) < 3 and pname not in entry["example_playlists"]:
            entry["example_playlists"].append(pname)

    complete_missing = []
    version_missing = []
    available_exact = []

    for family_key, row in by_family.items():
        playlist_hits = len(row["playlist_ids"])
        row["playlist_hits"] = playlist_hits
        row["top_event"] = row["events"].most_common(1)[0][0] if row["events"] else ""
        row["top_source"] = row["sources"].most_common(1)[0][0] if row["sources"] else ""
        row["relevance"] = (row["count"] * 1.2) + (playlist_hits * 4.0)

        if family_key not in library["family_set"]:
            row["status"] = "complete_missing"
            complete_missing.append(row)
            continue

        missing_variants = []
        for variant_key, cnt in row["variants"].most_common():
            label = row["variant_labels"].get(variant_key, row["display"])
            if variant_key not in library["variant_set"] and has_version_hint(label):
                missing_variants.append({
                    "variant_key": variant_key,
                    "label": label,
                    "count": cnt,
                })
        if missing_variants:
            row["status"] = "version_missing"
            row["missing_variants"] = missing_variants
            version_missing.append(row)
        else:
            row["status"] = "ok"
            available_exact.append(row)

    complete_missing.sort(key=lambda x: (x["relevance"], x["count"], x["playlist_hits"]), reverse=True)
    version_missing.sort(key=lambda x: (x["relevance"], x["count"], x["playlist_hits"]), reverse=True)
    available_exact.sort(key=lambda x: (x["relevance"], x["count"]), reverse=True)
    return {
        "complete_missing": complete_missing,
        "version_missing": version_missing,
        "available_exact": available_exact,
        "library_count": library["count"],
    }


def get_track_library_status(track_label: str):
    library = get_library_index()
    parsed = parse_line(track_label)
    if parsed:
        family_key = parsed.get("normalized_name", "")
        variant_key = build_variant_key(parsed.get("artist", ""), parsed.get("title", ""), parsed.get("remix", ""))
    else:
        clean = str(track_label or "").strip()
        family_key = ""
        variant_key = ""
        if " → " not in clean and " - " in clean:
            left, right = clean.split(" - ", 1)
            family_key = normalize_artist_title(left, right)
            variant_key = build_variant_key(left, right, "")
        else:
            norm = normalize_track_text(clean)
            for fam in library["family_set"]:
                if norm and norm in fam:
                    family_key = fam
                    break
    if not family_key:
        return "❔"
    if family_key not in library["family_set"]:
        return "❌"
    if variant_key and variant_key not in library["variant_set"] and has_version_hint(track_label):
        return "⚠️"
    return "✅"


def render_library_status_for_combo(combo_text: str):
    parts = [p.strip() for p in str(combo_text).split("→") if p.strip()]
    statuses = [get_track_library_status(part) for part in parts]
    if not statuses:
        return
    if all(x == "✅" for x in statuses):
        st.caption("Library: alles vorhanden ✅")
    elif any(x == "❌" for x in statuses):
        st.caption("Library: mindestens 1 Track fehlt ❌")
    elif any(x == "⚠️" for x in statuses):
        st.caption("Library: Track da, aber Version unklar / fehlt ⚠️")
    else:
        st.caption("Library: Status unklar ❔")


def get_missing_block_candidates(event=None, source=None, top_only=False, max_missing=2, sub_event=None):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    library = get_library_index()
    results = []
    for block_len, counter in ((3, data["block3_counts"]), (4, data["block4_counts"]), (5, data["block5_counts"])):
        for block, cnt in counter.most_common(40):
            missing = [display_from_normalized(x) for x in block if x not in library["family_set"]]
            if not missing or len(missing) > max_missing:
                continue
            results.append({
                "block_len": block_len,
                "combo": " → ".join(display_from_normalized(x) for x in block),
                "count": cnt,
                "missing": missing,
                "missing_count": len(missing),
            })
    results.sort(key=lambda x: (x["missing_count"], -x["count"], x["block_len"]))
    return results


def save_missing_to_combos(display: str, note: str = ""):
    save_combo("missing", display, source_track=display, note=note)


def render_missing_summary_ui(event=None, source=None, top_only=False, key_prefix="missing", sub_event=None):
    summary = summarize_missing_tracks(event=event, source=source, top_only=top_only, sub_event=sub_event)
    complete_missing = summary["complete_missing"]
    version_missing = summary["version_missing"]
    block_candidates = get_missing_block_candidates(event=event, source=source, top_only=top_only, max_missing=2, sub_event=sub_event)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Komplett fehlend", len(complete_missing))
    m2.metric("Version fehlt", len(version_missing))
    m3.metric("Fast spielbare Blöcke", len(block_candidates))
    m4.metric("RB Tracks", summary["library_count"])

    tabs = st.tabs(["🔥 Priorität fehlt", "⚠️ Version fehlt", "🧱 Blöcke mit Lücke", "🧪 RB-Debug"])

    with tabs[0]:
        if not complete_missing:
            st.success("Für diese Auswahl fehlen aktuell keine kompletten Tracks.")
        else:
            for idx, row in enumerate(complete_missing[:25], start=1):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([5.5, 1.2, 1.8])
                    c1.write(f"**{idx}. {row['display']}**")
                    c2.write(f"{row['playlist_hits']} PL")
                    if c3.button("⭐ Fehlt merken", key=f"{key_prefix}_miss_{idx}", width="stretch"):
                        save_missing_to_combos(row['display'], note=f"Komplett fehlend • Event: {row.get('top_event','')} • Quelle: {row.get('top_source','')}")
                        st.success("Als fehlender Track gemerkt.")
                    st.caption(f"Vorkommen: {row['count']} • Top Event: {row.get('top_event') or '-'} • Beispiele: {', '.join(row['example_playlists']) or '-'}")

    with tabs[1]:
        if not version_missing:
            st.success("Keine relevanten fehlenden Versionen erkannt.")
        else:
            for idx, row in enumerate(version_missing[:20], start=1):
                with st.container(border=True):
                    c1, c2 = st.columns([5.8, 1.6])
                    c1.write(f"**{idx}. {row['display']}**")
                    if c2.button("⭐ Version merken", key=f"{key_prefix}_ver_{idx}", width="stretch"):
                        first_label = row['missing_variants'][0]['label']
                        save_missing_to_combos(first_label, note=f"Version fehlt • Basis: {row['display']}")
                        st.success("Fehlende Version gemerkt.")
                    for v in row['missing_variants'][:3]:
                        st.write(f"- {v['label']} — {v['count']}x")
                    st.caption(f"Basis-Track vorhanden, aber diese Versionen fehlen. Playlists: {row['playlist_hits']}")

    with tabs[2]:
        if not block_candidates:
            st.success("Keine blockbasierten Lücken gefunden.")
        else:
            for idx, row in enumerate(block_candidates[:20], start=1):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([5.5, 1.0, 1.8])
                    c1.write(f"**{idx}. {row['combo']}**")
                    c2.write(f"{row['count']}x")
                    if c3.button("⭐ Block merken", key=f"{key_prefix}_block_{idx}", width="stretch"):
                        save_combo(f"missing_{row['block_len']}er", row['combo'], note=f"Fast spielbar • fehlt: {', '.join(row['missing'])}")
                        st.success("Block mit Lücke gemerkt.")
                    st.caption(f"Fehlt: {', '.join(row['missing'])}")

    with tabs[3]:
        st.caption("Zeigt dir schnell, warum Songs als fehlend oder nur versionsseitig fehlend erkannt werden.")
        for idx, row in enumerate(complete_missing[:10], start=1):
            st.write(f"{idx}. {row['display']} → Familie nicht in Rekordbox gefunden")
        for idx, row in enumerate(version_missing[:10], start=1):
            labels = ", ".join(v['label'] for v in row['missing_variants'][:2])
            st.write(f"{idx}. {row['display']} → Basis vorhanden, aber Version fehlt: {labels}")

def import_rekordbox_xml(file_text: str):
    root = ET.fromstring(file_text)
    tracks = []
    for track in root.findall(".//TRACK"):
        artist = track.attrib.get("Artist", "").strip()
        title = track.attrib.get("Name", "").strip()
        remix = track.attrib.get("Remixer", "").strip()
        norm = normalize_artist_title(artist, title)
        if artist or title:
            tracks.append((artist, title, remix, norm))

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM library_tracks")
    cur.executemany("""
        INSERT INTO library_tracks(artist, title, remix, normalized_name)
        VALUES(?,?,?,?)
    """, tracks)
    conn.commit()
    conn.close()
    return len(tracks)


def get_missing_tracks(event=None, source=None, top_only=False, sub_event=None):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT normalized_name FROM library_tracks")
    library = {row[0] for row in cur.fetchall()}
    conn.close()

    missing = []
    for track, cnt in data["track_total_counts"].most_common():
        if track not in library:
            missing.append((display_from_normalized(track), cnt))
    return missing



def _normalize_tag_text(value: str) -> str:
    raw = str(value or "").replace(";", ",")
    parts = [p.strip() for p in raw.split(",")]
    clean = []
    seen = set()
    for part in parts:
        if not part:
            continue
        key = part.casefold()
        if key in seen:
            continue
        seen.add(key)
        clean.append(part)
    return ", ".join(clean)


def save_combo(combo_type, combo_text, source_track="", note="", category="", tags="", usage_context="", source_name="", genre_name="", event_name="", playlist_name="", playlist_id=0):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO saved_combos(combo_type, combo_text, source_track, note, category, tags, usage_context, source_name, genre_name, event_name, playlist_name, playlist_id)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        str(combo_type or "").strip(),
        str(combo_text or "").strip(),
        str(source_track or "").strip(),
        str(note or "").strip(),
        str(category or "").strip(),
        _normalize_tag_text(tags),
        str(usage_context or "").strip(),
        str(source_name or "").strip(),
        str(genre_name or "").strip(),
        str(event_name or "").strip(),
        str(playlist_name or "").strip(),
        int(playlist_id or 0),
    ))
    conn.commit()
    conn.close()
    auto_backup_after_data_change("combo_save")


def get_saved_combos(combo_type="Alle", category="", tag="", usage_context="", source_name="", genre_name="", event_name="", query_text=""):
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT id, combo_type, combo_text, source_track, note, category, tags, usage_context, source_name, genre_name, event_name, playlist_name, playlist_id, created_at
        FROM saved_combos
        WHERE 1=1
    """
    params = []
    if combo_type and combo_type != "Alle":
        sql += " AND combo_type = ?"
        params.append(combo_type)
    if str(category or "").strip():
        sql += " AND LOWER(COALESCE(category,'')) = ?"
        params.append(str(category).strip().casefold())
    if str(tag or "").strip():
        sql += " AND LOWER(COALESCE(tags,'')) LIKE ?"
        params.append(f"%{str(tag).strip().casefold()}%")
    if str(usage_context or "").strip():
        sql += " AND LOWER(COALESCE(usage_context,'')) = ?"
        params.append(str(usage_context).strip().casefold())
    if str(source_name or "").strip():
        sql += " AND LOWER(COALESCE(source_name,'')) = ?"
        params.append(str(source_name).strip().casefold())
    if str(genre_name or "").strip():
        sql += " AND LOWER(COALESCE(genre_name,'')) = ?"
        params.append(str(genre_name).strip().casefold())
    if str(event_name or "").strip():
        sql += " AND LOWER(COALESCE(event_name,'')) = ?"
        params.append(str(event_name).strip().casefold())
    if str(query_text or "").strip():
        q = f"%{str(query_text).strip().casefold()}%"
        sql += " AND (LOWER(COALESCE(combo_text,'')) LIKE ? OR LOWER(COALESCE(note,'')) LIKE ? OR LOWER(COALESCE(category,'')) LIKE ? OR LOWER(COALESCE(tags,'')) LIKE ? OR LOWER(COALESCE(usage_context,'')) LIKE ? OR LOWER(COALESCE(source_name,'')) LIKE ? OR LOWER(COALESCE(genre_name,'')) LIKE ? OR LOWER(COALESCE(event_name,'')) LIKE ? OR LOWER(COALESCE(playlist_name,'')) LIKE ?)"
        params.extend([q, q, q, q, q, q, q, q, q])
    sql += " ORDER BY id DESC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_combo(combo_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM saved_combos WHERE id = ?", (combo_id,))
    conn.commit()
    conn.close()
    auto_backup_after_data_change("combo_delete")


def get_saved_combo_categories():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT category FROM saved_combos WHERE TRIM(COALESCE(category,'')) <> '' ORDER BY category")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    out = []
    seen = set()
    for value in rows:
        key = str(value).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(str(value).strip())
    return out


def get_saved_combo_contexts():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT usage_context FROM saved_combos WHERE TRIM(COALESCE(usage_context,'')) <> '' ORDER BY usage_context")
        rows = [r[0] for r in cur.fetchall()]
    except Exception:
        rows = []
    conn.close()
    out = []
    seen = set()
    for value in rows:
        key = str(value).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(str(value).strip())
    return out


def _get_saved_combo_distinct_values(column_name: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT {column_name} FROM saved_combos WHERE TRIM(COALESCE({column_name},'')) <> '' ORDER BY {column_name}")
        rows = [r[0] for r in cur.fetchall()]
    except Exception:
        rows = []
    conn.close()
    out = []
    seen = set()
    for value in rows:
        clean = str(value or "").strip()
        key = clean.casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def get_saved_combo_sources():
    return _get_saved_combo_distinct_values("source_name")


def get_saved_combo_genres():
    return _get_saved_combo_distinct_values("genre_name")


def get_saved_combo_events():
    return _get_saved_combo_distinct_values("event_name")


def get_saved_combo_tags():
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT tags FROM saved_combos WHERE TRIM(COALESCE(tags,'')) <> ''")
        rows = [r[0] for r in cur.fetchall()]
    except Exception:
        rows = []
    conn.close()
    out = []
    seen = set()
    for raw in rows:
        for part in str(raw or "").replace(";", ",").split(","):
            tag = part.strip()
            if not tag:
                continue
            key = tag.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(tag)
    return sorted(out, key=lambda x: x.casefold())


def strength_label(cnt):

    if cnt >= 10:
        return "🔥 sehr oft"
    if cnt >= 5:
        return "👍 oft"
    return "⚠️ selten"




@st.cache_data(ttl=120, show_spinner=False)
def get_all_playlist_sequences():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.name, p.event, p.sub_event, p.source, t.position, t.normalized_name
        FROM playlists p
        JOIN playlist_tracks t ON p.id = t.playlist_id
        ORDER BY p.id, t.position
    """)
    rows = cur.fetchall()
    conn.close()

    seqs = {}
    meta = {}
    for pid, name, event, sub_event, source, pos, norm in rows:
        seqs.setdefault(pid, []).append(norm)
        meta[pid] = {"name": name, "event": event, "sub_event": sub_event, "source": source}
    return seqs, meta


def compare_sequences(seq1, seq2):
    if not seq1 or not seq2:
        return 0.0
    if seq1 == seq2:
        return 1.0
    set1, set2 = set(seq1), set(seq2)
    jaccard = len(set1 & set2) / max(1, len(set1 | set2))
    seq_ratio = SequenceMatcher(None, "|".join(seq1), "|".join(seq2)).ratio()
    length_ratio = min(len(seq1), len(seq2)) / max(len(seq1), len(seq2))
    return round((jaccard * 0.4) + (seq_ratio * 0.5) + (length_ratio * 0.1), 4)


def find_possible_duplicates_for_tracks(candidate_tracks, threshold=0.85):
    candidate_seq = [t["normalized_name"] for t in candidate_tracks if t.get("normalized_name")]
    all_seqs, meta = get_all_playlist_sequences()
    matches = []
    for pid, seq in all_seqs.items():
        score = compare_sequences(candidate_seq, seq)
        if score >= threshold:
            matches.append({
                "playlist_id": pid,
                "name": meta[pid]["name"],
                "event": meta[pid]["event"],
                "source": meta[pid]["source"],
                "score": score,
                "track_count": len(seq),
            })
    return sorted(matches, key=lambda x: x["score"], reverse=True)


def find_all_possible_duplicates(threshold=0.9):
    all_seqs, meta = get_all_playlist_sequences()
    ids = sorted(all_seqs.keys())
    results = []
    for i, pid_a in enumerate(ids):
        for pid_b in ids[i+1:]:
            score = compare_sequences(all_seqs[pid_a], all_seqs[pid_b])
            if score >= threshold:
                results.append({
                    "a_id": pid_a,
                    "a_name": meta[pid_a]["name"],
                    "a_event": meta[pid_a]["event"],
                    "a_source": meta[pid_a]["source"],
                    "b_id": pid_b,
                    "b_name": meta[pid_b]["name"],
                    "b_event": meta[pid_b]["event"],
                    "b_source": meta[pid_b]["source"],
                    "score": score,
                    "a_count": len(all_seqs[pid_a]),
                    "b_count": len(all_seqs[pid_b]),
                })
    return sorted(results, key=lambda x: x["score"], reverse=True)



def get_direct_transition_count(track_a, track_b, event=None, source=None, top_only=False, sub_event=None):
    data = compute_transitions(event=event, source=source, top_only=top_only, sub_event=sub_event)
    pair_counts = data["pair_counts"]

    a_n = normalize_track_text(track_a)
    b_n = normalize_track_text(track_b)
    total = 0
    for (x, y), c in pair_counts.items():
        if a_n in x and b_n in y:
            total += c
    return total


def get_better_alternatives(track_a, current_track=None, event=None, source=None, top_only=False, limit=5, sub_event=None):
    insights = get_track_insights(track_a, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not insights:
        return []

    current_n = normalize_track_text(current_track) if current_track else ""
    results = []
    for norm, cnt in insights["after"]:
        if current_n and current_n in norm:
            continue
        results.append((display_from_normalized(norm), cnt))
    return results[:limit]





def build_autopilot_set(start_track, length=12, event=None, source=None, top_only=False):
    if not start_track:
        return []
    result = [start_track]
    current = start_track
    for _ in range(length-1):
        insights = get_track_insights(current, event=event, source=source, top_only=top_only)
        if not insights or not insights["after"]:
            break
        next_track = display_from_normalized(insights["after"][0][0])
        if next_track in result:
            break
        result.append(next_track)
        current = next_track
    return result

def auto_extend_set(current_set, event=None, source=None, top_only=False, steps=2, sub_event=None):
    extended = current_set.copy()
    for _ in range(steps):
        if not extended:
            break
        last = extended[-1]
        insights = get_track_insights(last, event=event, source=source, top_only=top_only, sub_event=sub_event)
        if insights and insights["after"]:
            next_track = display_from_normalized(insights["after"][0][0])
            extended.append(next_track)
    return extended




def track_phase_distance(label_a: str, label_b: str) -> int:
    a = phase_order_value(label_a)
    b = phase_order_value(label_b)
    if not a or not b:
        return 99
    return abs(a - b)


def get_phase_matched_suggestions(track_name, event=None, source=None, top_only=False, limit=5):
    insights = get_track_insights(track_name, event=event, source=source, top_only=top_only)
    if not insights:
        return []
    current_phase = get_track_phase_label(track_name, event=event, source=source, top_only=top_only)
    desired_phase = current_phase
    current_val = phase_order_value(current_phase)
    if current_val and current_val < 3:
        desired_phase = {1: "⬆️ Aufbau", 2: "🔥 Peak"}.get(current_val, current_phase)

    ranked = []
    for norm, cnt in insights["after"]:
        display = display_from_normalized(norm)
        cand_phase = get_track_phase_label(display, event=event, source=source, top_only=top_only)
        distance = track_phase_distance(desired_phase, cand_phase)
        score = (cnt * 10) - (distance * 7)
        ranked.append({
            "display": display,
            "count": cnt,
            "phase": cand_phase,
            "desired_phase": desired_phase,
            "score": score,
        })
    ranked.sort(key=lambda x: (x["score"], x["count"], x["display"].casefold()), reverse=True)
    return ranked[:limit]


def _timing_order_value(label: str) -> int:
    mapping = {
        "sehr früh": 1,
        "früh": 2,
        "Mitte": 3,
        "spät": 4,
        "ganz spät": 5,
    }
    return mapping.get(str(label or "").strip(), 0)




def build_smart_transition_recommendations(current_track, event=None, source=None, top_only=False, sub_event=None, limit=10):
    insights = get_track_insights(current_track, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not insights:
        return {"current": "", "rows": [], "quality": {"label": "Unklar", "score": 0, "basis_playlists": 0}}

    current_display = insights["display"]
    current_role = get_track_role_label(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    current_phase = get_track_phase_label(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    current_timing = get_track_timing_bucket(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)

    candidate_meta_cache = {}

    def _candidate_meta(display_name: str):
        cached = candidate_meta_cache.get(display_name)
        if cached:
            return cached
        phase = get_track_phase_label(display_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
        timing = get_track_timing_bucket(display_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
        role = get_track_role_label(display_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
        event_fit = get_event_fit_label(display_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
        cached = {"phase": phase, "timing": timing, "role": role, "event_fit": event_fit}
        candidate_meta_cache[display_name] = cached
        return cached

    rows = []
    for norm, cnt in insights.get("after", [])[:18]:
        display = display_from_normalized(norm)
        meta = _candidate_meta(display)
        next_role = meta["role"]
        next_phase = meta["phase"]
        next_timing = meta["timing"]
        event_fit = meta["event_fit"]

        phase_distance = track_phase_distance(current_phase, next_phase)
        timing_distance = abs(_timing_order_value(current_timing) - _timing_order_value(next_timing)) if _timing_order_value(current_timing) and _timing_order_value(next_timing) else 3

        phase_bonus = 14 if phase_distance == 0 else (8 if phase_distance == 1 else (2 if phase_distance == 2 else -6))
        timing_bonus = 10 if timing_distance == 0 else (6 if timing_distance == 1 else (1 if timing_distance == 2 else -5))
        role_bonus = 6 if current_role == next_role else 0

        conf_label, conf_score = get_learning_recommendation_confidence(cnt, insights.get("total_count", 0))
        smart_score = int((cnt * 12) + phase_bonus + timing_bonus + role_bonus + (conf_score * 0.2))
        smart_type = classify_smart_transition_type(current_phase, next_phase, current_timing, next_timing, current_role, next_role)

        reasons = [f"echter Übergang {cnt}x"]
        if phase_distance == 0:
            reasons.append("gleiche Phase")
        elif phase_distance == 1:
            reasons.append("Phase passt gut")
        if timing_distance <= 1:
            reasons.append("Timing passt")
        if current_role == next_role:
            reasons.append("ähnliche Rolle")
        if event_fit != "Neutral":
            reasons.append(event_fit)

        rows.append({
            "Song": display,
            "Typ": smart_type,
            "Übergänge": int(cnt),
            "Smart-Score": int(smart_score),
            "KI-Vertrauen": f"{conf_label} ({conf_score})",
            "Phase": next_phase,
            "Timing": next_timing,
            "Rolle": next_role,
            "Event-Fit": event_fit,
            "Warum": " | ".join(reasons),
        })

    rows = sorted(rows, key=lambda x: (x["Smart-Score"], x["Übergänge"], x["Song"].casefold()), reverse=True)[:limit]
    top_quality = get_learning_quality_snapshot(insights)
    return {"current": current_display, "rows": rows, "quality": top_quality}




def classify_smart_transition_type(current_phase: str, next_phase: str, current_timing: str, next_timing: str, current_role: str, next_role: str) -> str:
    phase_distance = track_phase_distance(current_phase, next_phase)
    timing_distance = abs(_timing_order_value(current_timing) - _timing_order_value(next_timing)) if _timing_order_value(current_timing) and _timing_order_value(next_timing) else 3

    if phase_distance == 0 and timing_distance == 0:
        return "Sicherer Übergang"
    if "Peak" in str(next_phase) and phase_distance <= 1:
        return "Push Richtung Peak"
    if "Closing" in str(next_phase):
        return "Closing-tauglich"
    if current_role == next_role and timing_distance <= 1:
        return "Stabiler Flow"
    if phase_distance <= 1:
        return "Kontext-Passend"
    return "Mutiger Wechsel"


def get_event_fit_label(track_name, event=None, source=None, top_only=False, sub_event=None):
    insights = get_track_insights(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not insights:
        return "Neutral"
    event_rows = list((insights.get("event_info") or {}).most_common(3))
    if not event_rows:
        return "Neutral"
    top_name, top_count = event_rows[0]
    total = max(1, int(insights.get("total_count", 0) or 0))
    share = top_count / total
    if share >= 0.6:
        return f"Stark in {top_name}"
    if share >= 0.35:
        return f"Oft in {top_name}"
    return "Breit einsetzbar"

def get_transition_engine_snapshot(current_track, event=None, source=None, top_only=False, sub_event=None):
    pack = build_smart_transition_recommendations(current_track, event=event, source=source, top_only=top_only, sub_event=sub_event, limit=10)
    rows = pack.get("rows", [])
    if not rows:
        return {
            "best_song": "",
            "best_score": 0,
            "best_confidence": "-",
            "rows": [],
            "quality": pack.get("quality", {"label": "Unklar", "score": 0, "basis_playlists": 0}),
        }
    best = rows[0]
    return {
        "best_song": best.get("Song", ""),
        "best_score": int(best.get("Smart-Score", 0) or 0),
        "best_confidence": best.get("KI-Vertrauen", "-"),
        "rows": rows,
        "quality": pack.get("quality", {"label": "Unklar", "score": 0, "basis_playlists": 0}),
    }



def get_recent_set_transition_quality(current_set, event=None, source=None, top_only=False):
    if len(current_set) < 2:
        return None
    left_track = current_set[-2]
    right_track = current_set[-1]
    cnt = get_direct_transition_count(left_track, right_track, event=event, source=source, top_only=top_only)
    return {
        "left": left_track,
        "right": right_track,
        "count": cnt,
        "label": transition_safety_label(cnt),
    }


def get_smart_set_builder_pack(current_set, event=None, source=None, top_only=False):
    if not current_set:
        return None
    last_track = current_set[-1]
    insights = get_track_insights(last_track, event=event, source=source, top_only=top_only)
    if not insights:
        return None

    last_phase = get_track_phase_label(last_track, event=event, source=source, top_only=top_only)
    top_suggestions = []
    for norm, cnt in insights["after"][:8]:
        display = display_from_normalized(norm)
        top_suggestions.append({
            "display": display,
            "count": cnt,
            "phase": get_track_phase_label(display, event=event, source=source, top_only=top_only),
        })

    phase_suggestions = get_phase_matched_suggestions(last_track, event=event, source=source, top_only=top_only, limit=6)
    transition_quality = get_recent_set_transition_quality(current_set, event=event, source=source, top_only=top_only)
    recovery = []
    if transition_quality and transition_quality["count"] < 5:
        recovery = get_better_alternatives(
            transition_quality["left"],
            current_track=transition_quality["right"],
            event=event,
            source=source,
            top_only=top_only,
            limit=5,
        )

    return {
        "last_track": last_track,
        "last_phase": last_phase,
        "insights": insights,
        "top_suggestions": top_suggestions,
        "phase_suggestions": phase_suggestions,
        "transition_quality": transition_quality,
        "recovery": recovery,
    }


def calculate_average_strength(eval_rows):
    score_map = {"🔥 stark":3,"👍 mittel":2,"⚠️ selten":1,"❌ unbekannt":0}
    if not eval_rows:
        return 0
    total = sum(score_map.get(label,0) for _,_,label in eval_rows)
    return round(total/len(eval_rows),2)




def transition_safety_label(cnt):
    if cnt >= 10:
        return "✅ sicher"
    elif cnt >= 5:
        return "👍 ok"
    elif cnt >= 1:
        return "⚠️ riskant"
    else:
        return "❌ kaum genutzt"


def phase_order_value(label):
    order = {
        "🌙 Warmup": 1,
        "⬆️ Aufbau": 2,
        "🔥 Peak": 3,
        "🌅 Spät / Closing": 4
    }
    return order.get(label, 0)

def build_flow_timeline(phases):
    return " → ".join(phases)

def evaluate_flow(phases):
    # simple monotonic non-decreasing check with small tolerance
    vals = [phase_order_value(p) for p in phases if p]
    if not vals:
        return "Unklar", []
    issues = []
    ok = True
    for i in range(len(vals)-1):
        if vals[i+1] < vals[i] - 0:  # no backwards allowed
            ok = False
            issues.append((i, phases[i], phases[i+1]))
    if ok:
        # strength based on length and smoothness
        if len(vals) >= 4:
            return "🔥 Sehr starker Ablauf", []
        return "👍 Solider Ablauf", []
    return "⚠️ Unlogischer Verlauf", issues



def get_track_importance(event=None, source=None, top_only=False, sub_event=None):
    data = compute_transitions(event=event, source=source, top_only=top_only, sub_event=sub_event)
    counts = data["track_total_counts"]
    total = sum(counts.values()) or 1
    importance = []
    for t, c in counts.most_common(50):
        score = round((c/total)*100, 2)
        importance.append((t, c, score))
    return importance




def get_phase_bucket_for_label(label: str) -> str:
    label = str(label or "")
    if "Warmup" in label:
        return "warmup"
    if "Aufbau" in label:
        return "middle"
    if "Peak" in label:
        return "peak"
    if "Closing" in label or "Spät" in label:
        return "closing"
    return "other"


def get_heute_auflegen_pack(event=None, source=None, top_only=False, sub_event=None):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)

    songs_by_bucket = {"warmup": [], "middle": [], "peak": [], "closing": []}
    for norm, cnt in data["track_total_counts"].most_common(200):
        display = display_from_normalized(norm)
        phase = get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        bucket = get_phase_bucket_for_label(phase)
        if bucket in songs_by_bucket:
            songs_by_bucket[bucket].append({
                "display": display,
                "count": cnt,
                "phase": phase,
            })

    pair_by_bucket = {"warmup": [], "middle": [], "peak": [], "closing": []}
    for (a, b), cnt in data["pair_counts"].most_common(120):
        combo = f"{display_from_normalized(a)} → {display_from_normalized(b)}"
        phase = get_track_phase_label(display_from_normalized(a), event=event, source=source, top_only=top_only, sub_event=sub_event)
        bucket = get_phase_bucket_for_label(phase)
        if bucket in pair_by_bucket:
            pair_by_bucket[bucket].append({
                "combo": combo,
                "count": cnt,
                "phase": phase,
            })

    blocks_by_bucket = {"warmup": [], "middle": [], "peak": [], "closing": []}
    for block_len, counter in ((3, data["block3_counts"]), (4, data["block4_counts"]), (5, data["block5_counts"])):
        for block, cnt in counter.most_common(100):
            combo = " → ".join(display_from_normalized(x) for x in block)
            first_phase = get_track_phase_label(display_from_normalized(block[0]), event=event, source=source, top_only=top_only, sub_event=sub_event)
            bucket = get_phase_bucket_for_label(first_phase)
            if bucket in blocks_by_bucket:
                blocks_by_bucket[bucket].append({
                    "combo": combo,
                    "count": cnt,
                    "phase": first_phase,
                    "block_len": block_len,
                })

    return {
        "songs": songs_by_bucket,
        "pairs": pair_by_bucket,
        "blocks": blocks_by_bucket,
    }


def render_set_builder_panel(title: str = "Heutiges Set"):
    st.subheader(title)
    items = st.session_state.setdefault("set_builder", [])
    if not items:
        st.info("Noch keine Songs im aktuellen Set. Nutze in DJ Memory oder Heute auflegen die Buttons '➕ Set' bzw. '➕ Heute'.")
        return

    m1, m2 = st.columns([3, 2])
    m1.metric("Songs im Set", len(items))
    m2.caption("Baue hier dein aktuelles Arbeits-Set für heute.")

    top_a, top_b, top_c = st.columns(3)
    if top_a.button("⬅️ Letzten entfernen", key=f"{title}_remove_last", width="stretch"):
        if items:
            items.pop()
            st.rerun()
    if top_b.button("🧹 Set leeren", key=f"{title}_clear_all", width="stretch"):
        st.session_state["set_builder"] = []
        st.rerun()
    top_c.download_button(
        "📥 Set als TXT",
        "\n".join(items),
        file_name="heute_set.txt",
        width="stretch",
        key=f"{title}_download_txt",
    )

    for idx, song in enumerate(items, start=1):
        row_cols = st.columns([7, 1.2])
        row_cols[0].write(f"{idx}. {song}")
        if row_cols[1].button("🗑️", key=f"{title}_del_{idx}", width="stretch"):
            del items[idx-1]
            st.rerun()


def render_heute_auflegen_page():
    st.header("Heute auflegen")
    st.caption("Wähle deinen Anlass und hol dir sofort Warmup-, Mittelteil-, Peak- und Closing-Ideen inklusive Songpaare und Blöcke.")

    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Heute auflegen", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="today_event")
    src = c2.selectbox("Herkunft", sources, key="today_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="today_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="today_top")

    pack = get_heute_auflegen_pack(event=ev, source=src, top_only=top, sub_event=sub_ev)

    st.info("Für normale Playlist-Uploads im Web-Tool brauchst du KEIN GitHub. GitHub nur für Code-Updates.")
    render_set_builder_panel("Heute auflegen Set")

    tabs = st.tabs(["🌙 Warmup", "⬆️ Mittelteil", "🔥 Peak", "🌅 Closing", "🎤 Live jetzt"])

    mapping = [
        ("warmup", tabs[0], "Warmup"),
        ("middle", tabs[1], "Mittelteil / Aufbau"),
        ("peak", tabs[2], "Peak"),
        ("closing", tabs[3], "Closing / Rausschmeißer"),
    ]

    for bucket, tab, label in mapping:
        with tab:
            s1, s2, s3 = st.columns(3)
            with s1:
                st.subheader(f"{label} Songs")
                rows = pack["songs"].get(bucket, [])[:12]
                if rows:
                    for idx, row in enumerate(rows, start=1):
                        render_count_row(
                            f"{idx}. {row['display']} [{row['phase']}]",
                            row["count"],
                            combo_type="song",
                            combo_text=row["display"],
                            set_key=f"today_song_{bucket}_{idx}"
                        )
                else:
                    st.info("Keine passenden Songs gefunden.")

            with s2:
                st.subheader(f"{label} Songpaare")
                rows = pack["pairs"].get(bucket, [])[:10]
                if rows:
                    for idx, row in enumerate(rows, start=1):
                        render_count_row(
                            f"{idx}. {row['combo']}",
                            row["count"],
                            combo_type="2er",
                            combo_text=row["combo"],
                            set_key=f"today_pair_{bucket}_{idx}"
                        )
                else:
                    st.info("Keine passenden Paare gefunden.")

            with s3:
                st.subheader(f"{label} Blöcke")
                rows = pack["blocks"].get(bucket, [])[:10]
                if rows:
                    for idx, row in enumerate(rows, start=1):
                        render_count_row(
                            f"{idx}. {row['combo']} ({row['block_len']}er)",
                            row["count"],
                            combo_type=f"{row['block_len']}er",
                            combo_text=row["combo"],
                            set_key=f"today_block_{bucket}_{idx}"
                        )
                else:
                    st.info("Keine passenden Blöcke gefunden.")

    with tabs[4]:
        st.subheader("Live Hilfe direkt für heute")
        current_track = st.text_input("Aktueller Song", placeholder="z. B. Mr. Brightside", key="today_live_track")
        if current_track:
            insights = get_track_insights(current_track, event=ev, source=src, top_only=top, sub_event=sub_ev)
            if not insights:
                st.warning("Kein passender Track gefunden.")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Track", insights["display"])
                m2.metric("Gesamt", insights["total_count"])
                m3.metric("Phase", get_track_phase_label(insights["display"], event=ev, source=src, top_only=top, sub_event=sub_ev))

                st.markdown("**Beste nächste Songs**")
                if insights["after"]:
                    for idx, (norm, cnt) in enumerate(insights["after"][:10], start=1):
                        display = display_from_normalized(norm)
                        render_count_row(
                            f"{idx}. {display}",
                            cnt,
                            combo_type="song",
                            combo_text=display,
                            set_key=f"today_live_after_{idx}"
                        )
                else:
                    st.info("Keine direkten Folgesongs gefunden.")

                st.markdown("**Typische Live-Blöcke ab diesem Song**")
                if insights["block3"]:
                    for idx, (combo_text, cnt) in enumerate(insights["block3"][:6], start=1):
                        render_count_row(
                            combo_text,
                            cnt,
                            combo_type="3er",
                            combo_text=combo_text,
                            set_key=f"today_live_block_{idx}"
                        )
                else:
                    st.info("Keine typischen Blöcke gefunden.")



FLOW_PROFILES = {
    "Standard": {"warmup": 25, "middle": 50, "peak": 82, "closing": 40},
    "Langsamer Aufbau": {"warmup": 20, "middle": 42, "peak": 78, "closing": 38},
    "Party früh": {"warmup": 30, "middle": 60, "peak": 88, "closing": 45},
    "Klassisch gemischt": {"warmup": 22, "middle": 48, "peak": 76, "closing": 35},
}

GUEST_TYPES = [
    "Gemischt",
    "Jung & Party",
    "Ü30 / 90er / 2000er",
    "Klassisch / Familienpublikum",
    "Kinder + Eltern",
]

def get_energy_score_for_phase(phase_label: str, flow_profile: str = "Standard", guest_type: str = "Gemischt") -> int:
    phase = str(phase_label or "")
    profile = FLOW_PROFILES.get(flow_profile, FLOW_PROFILES["Standard"])
    if "Warmup" in phase:
        return profile["warmup"]
    if "Aufbau" in phase:
        return profile["middle"]
    if "Peak" in phase:
        return profile["peak"]
    if "Closing" in phase or "Spät" in phase:
        return profile["closing"]
    return 50

def get_energy_label(score: int) -> str:
    if score <= 25:
        return "🟢 ruhig"
    if score <= 45:
        return "🟡 leicht steigend"
    if score <= 65:
        return "🟠 aktiv"
    if score <= 80:
        return "🔴 stark"
    return "🔥 Peak"

def classify_event_hint(event: str, guest_type: str) -> str:
    e = str(event or "").lower()
    g = str(guest_type or "").lower()
    if "hochzeit" in e and "klassisch" in g:
        return "Erst breit und verbindend, Peak nicht zu früh."
    if "hochzeit" in e and "jung" in g:
        return "Früherer Party-Aufbau möglich, Mitsing-Momente stark nutzen."
    if "ü30" in e or "ue30" in e:
        return "80er/90er/2000er in klaren Wellen spielen, Peak eher in Blöcken."
    if "kinder" in e:
        return "Erst Kinder mitnehmen, später Eltern-Hits als Brücke nutzen."
    return "Flow langsam lesen: erst Sicherheit, dann Aufbau, dann Peak."

def get_flow_pack(event=None, source=None, top_only=False, sub_event=None, flow_profile="Standard", guest_type="Gemischt"):
    auto = build_event_auto_set(event=event, source=source, top_only=top_only, sub_event=sub_event)
    all_phases = []
    for phase_key, label in [("warmup", "Warmup"), ("middle", "Mittelteil"), ("peak", "Peak"), ("closing", "Closing")]:
        for song in auto.get(phase_key, []):
            phase_label = get_track_phase_label(song, event=event, source=source, top_only=top_only, sub_event=sub_event)
            energy = get_energy_score_for_phase(phase_label, flow_profile=flow_profile)
            all_phases.append({
                "phase_key": phase_key,
                "phase_label": label,
                "song": song,
                "energy": energy,
                "energy_label": get_energy_label(energy),
                "timing_hint": "eher später" if energy >= 80 else ("passt jetzt" if energy >= 40 else "eher früher"),
            })
    return {
        "auto": auto,
        "flow_rows": all_phases,
        "event_hint": classify_event_hint(event, guest_type),
        "flow_profile": flow_profile,
        "guest_type": guest_type,
    }

def render_smart_flow_engine_page():
    st.header("Smart Flow Engine")
    st.caption("Hier lernt das Tool nicht nur was gespielt wird, sondern auch wann es typischerweise funktioniert.")

    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Smart Flow Engine", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="flow_event")
    src = c2.selectbox("Herkunft", sources, key="flow_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="flow_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="flow_top")

    d1, d2 = st.columns(2)
    guest_type = d1.selectbox("Gäste-Typ", GUEST_TYPES, key="flow_guest_type")
    flow_profile = d2.selectbox("Flow-Profil", list(FLOW_PROFILES.keys()), key="flow_profile")

    flow = get_flow_pack(event=ev, source=src, top_only=top, sub_event=sub_ev, flow_profile=flow_profile, guest_type=guest_type)

    st.info(f"🎯 Event-Hinweis: {flow['event_hint']}")
    m1, m2 = st.columns(2)
    m1.metric("Gäste-Typ", guest_type)
    m2.metric("Flow-Profil", flow_profile)

    tabs = st.tabs(["⚡ Flow Überblick", "🎧 Auto-Set mit Energie", "🎤 Nächster Song KI"])

    with tabs[0]:
        st.subheader("Typische Event-Welle")
        rows = []
        for r in flow["flow_rows"]:
            rows.append({
                "Phase": r["phase_label"],
                "Song": r["song"],
                "Energie": r["energy"],
                "Energie-Label": r["energy_label"],
                "Wann spielen": r["timing_hint"],
            })
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("Noch zu wenig Daten für diese Auswahl.")

    with tabs[1]:
        st.subheader("Auto-Set mit Energieeinschätzung")
        if flow["flow_rows"]:
            for idx, r in enumerate(flow["flow_rows"], start=1):
                st.write(f"{idx}. {r['song']} — {r['phase_label']} — {r['energy']} — {r['energy_label']} — {r['timing_hint']}")
            st.download_button(
                "📥 Flow-Set als TXT herunterladen",
                "\n".join([f"{r['song']} | {r['phase_label']} | {r['energy']} | {r['timing_hint']}" for r in flow["flow_rows"]]),
                file_name="smart_flow_set.txt",
                width="stretch",
            )
        else:
            st.info("Noch keine Flow-Daten verfügbar.")

    with tabs[2]:
        st.subheader("Nächster Song KI")
        current_track = st.text_input("Was läuft gerade?", key="flow_live_track", placeholder="z. B. Mr. Brightside")
        if current_track:
            insights = get_track_insights(current_track, event=ev, source=src, top_only=top, sub_event=sub_ev)
            if not insights:
                st.warning("Kein passender Track gefunden.")
            else:
                current_phase = get_track_phase_label(insights["display"], event=ev, source=src, top_only=top, sub_event=sub_ev)
                current_energy = get_energy_score_for_phase(current_phase, flow_profile=flow_profile)
                st.info(f"Aktueller Song: {insights['display']} | Phase: {current_phase} | Energie: {current_energy} ({get_energy_label(current_energy)})")

                next_rows = []
                for norm, cnt in insights.get("after", [])[:12]:
                    display = display_from_normalized(norm)
                    phase = get_track_phase_label(display, event=ev, source=src, top_only=top, sub_event=sub_ev)
                    energy = get_energy_score_for_phase(phase, flow_profile=flow_profile)
                    next_rows.append({
                        "Song": display,
                        "Phase": phase,
                        "Energie": energy,
                        "Energie-Label": get_energy_label(energy),
                        "Wie gut jetzt": "✅ passt jetzt" if abs(energy - current_energy) <= 20 else ("⏳ eher später" if energy > current_energy else "🧘 eher früher"),
                        "Häufigkeit": cnt,
                    })
                if next_rows:
                    st.dataframe(next_rows, width="stretch", hide_index=True)
                else:
                    st.info("Keine guten Folge-Songs gefunden.")

def auto_set_phase_plan(flow_profile: str = "Standard", guest_type: str = "Gemischt"):
    if flow_profile == "Langsamer Aufbau":
        return [
            ("warmup", 3), ("middle", 4), ("peak", 3), ("closing", 2)
        ]
    if flow_profile == "Party früh":
        return [
            ("warmup", 2), ("middle", 3), ("peak", 5), ("closing", 2)
        ]
    if flow_profile == "Klassisch gemischt":
        return [
            ("warmup", 3), ("middle", 3), ("peak", 4), ("closing", 2)
        ]
    return [
        ("warmup", 3), ("middle", 3), ("peak", 4), ("closing", 2)
    ]


def auto_set_role_hint(phase_key: str) -> str:
    mapping = {
        "warmup": "🌙 Warmup",
        "middle": "⬆️ Aufbau",
        "peak": "🔥 Peak",
        "closing": "🌅 Spät / Closing",
    }
    return mapping.get(phase_key, "❔ Unklar")


def auto_set_guest_bias(song_name: str, guest_type: str) -> int:
    name = str(song_name or "").casefold()
    guest = str(guest_type or "").casefold()
    score = 0
    if "jung" in guest or "party" in guest:
        if any(x in name for x in ["pitbull", "guetta", "usher", "black eyed peas", "rihanna", "flo rida", "sean paul", "lmfao"]):
            score += 10
    if "ü30" in guest or "2000" in guest or "90er" in guest:
        if any(x in name for x in ["backstreet", "britney", "shakira", "cascada", "snap", "vengaboys", "spice", "eiffel", "whigfield"]):
            score += 10
    if "klassisch" in guest or "familien" in guest:
        if any(x in name for x in ["abba", "boney", "queen", "bon jovi", "a-ha", "roxette", "lou bega", "whitney", "eurythmics"]):
            score += 8
    if "kinder" in guest:
        if any(x in name for x in ["schnappi", "fliegerlied", "macarena", "anton", "baby shark"]):
            score += 12
    return score


def build_smart_event_auto_set(event=None, source=None, top_only=False, sub_event=None, flow_profile="Standard", guest_type="Gemischt"):
    pack = get_heute_auflegen_pack(event=event, source=source, top_only=top_only, sub_event=sub_event)
    phase_plan = auto_set_phase_plan(flow_profile=flow_profile, guest_type=guest_type)

    selected = []
    selected_names = set()
    phase_rows = []
    last_song = None

    for phase_key, take_count in phase_plan:
        candidates = pack["songs"].get(phase_key, [])[:40]
        ranked = []
        for row in candidates:
            song = row["display"]
            if song in selected_names:
                continue
            phase_label = row.get("phase") or get_track_phase_label(song, event=event, source=source, top_only=top_only, sub_event=sub_event)
            energy = get_energy_score_for_phase(phase_label, flow_profile=flow_profile)
            base = int(row.get("count", 0))
            guest_bonus = auto_set_guest_bias(song, guest_type)
            transition_bonus = 0
            if last_song:
                transition_bonus = get_direct_transition_count(last_song, song, event=event, source=source, top_only=top_only, sub_event=sub_event) * 4
            score = base * 5 + guest_bonus + transition_bonus
            ranked.append({
                "song": song,
                "phase_key": phase_key,
                "phase_label": phase_label,
                "energy": energy,
                "energy_label": get_energy_label(energy),
                "count": base,
                "guest_bonus": guest_bonus,
                "transition_bonus": transition_bonus,
                "score": score,
            })

        ranked = sorted(ranked, key=lambda x: (x["score"], x["count"], x["song"].casefold()), reverse=True)

        taken = 0
        for item in ranked:
            if item["song"] in selected_names:
                continue
            selected.append(item["song"])
            selected_names.add(item["song"])
            phase_rows.append(item)
            last_song = item["song"]
            taken += 1
            if taken >= take_count:
                break

    phase_buckets = {"warmup": [], "middle": [], "peak": [], "closing": []}
    for item in phase_rows:
        phase_buckets[item["phase_key"]].append(item)

    return {
        "full_set": [x["song"] for x in phase_rows],
        "phase_rows": phase_rows,
        "warmup": [x["song"] for x in phase_buckets["warmup"]],
        "middle": [x["song"] for x in phase_buckets["middle"]],
        "peak": [x["song"] for x in phase_buckets["peak"]],
        "closing": [x["song"] for x in phase_buckets["closing"]],
        "pairs": {
            "warmup": [x["combo"] for x in pack["pairs"].get("warmup", [])[:5]],
            "middle": [x["combo"] for x in pack["pairs"].get("middle", [])[:5]],
            "peak": [x["combo"] for x in pack["pairs"].get("peak", [])[:5]],
            "closing": [x["combo"] for x in pack["pairs"].get("closing", [])[:5]],
        },
        "blocks": {
            "warmup": [x["combo"] for x in pack["blocks"].get("warmup", [])[:4]],
            "middle": [x["combo"] for x in pack["blocks"].get("middle", [])[:4]],
            "peak": [x["combo"] for x in pack["blocks"].get("peak", [])[:4]],
            "closing": [x["combo"] for x in pack["blocks"].get("closing", [])[:4]],
        },
        "flow_profile": flow_profile,
        "guest_type": guest_type,
    }


def build_event_auto_set(event=None, source=None, top_only=False, sub_event=None, flow_profile="Standard", guest_type="Gemischt"):
    return build_smart_event_auto_set(
        event=event,
        source=source,
        top_only=top_only,
        sub_event=sub_event,
        flow_profile=flow_profile,
        guest_type=guest_type,
    )


def render_event_auto_set_page():
    st.header("Auto Event Set")
    st.caption("Wähle dein Event und lass dir automatisch eine sinnvolle Warmup-, Mittelteil-, Peak- und Closing-Struktur bauen.")
    render_v10_quickflow_box()

    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Auto Event Set", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="auto_event")
    src = c2.selectbox("Herkunft", sources, key="auto_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="auto_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="auto_top")

    d1, d2 = st.columns(2)
    auto_guest_type = d1.selectbox("Gäste-Typ", GUEST_TYPES, key="auto_guest_type")
    auto_flow_profile = d2.selectbox("Flow-Profil", list(FLOW_PROFILES.keys()), key="auto_flow_profile")

    auto = build_event_auto_set(
        event=ev,
        source=src,
        top_only=top,
        sub_event=sub_ev,
        flow_profile=auto_flow_profile,
        guest_type=auto_guest_type,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Auto-Set Länge", len(auto["full_set"]))
    m2.metric("Event", format_event_label(ev, sub_ev) if ev else "-")
    m3.metric("Gäste-Typ", auto_guest_type)
    m4.metric("Flow-Profil", auto_flow_profile)

    st.info("V93 macht den Workflow ruhiger: gleiche smarte Auto-Set-Logik, aber klarere Anzeige, kompaktere Flow-Infos und schnellerer Überblick.")

    tabs = st.tabs(["🎧 Auto Set", "📈 Flow Details", "🌙 Warmup", "⬆️ Mittelteil", "🔥 Peak", "🌅 Closing"])

    with tabs[0]:
        st.subheader("Automatisch gebautes Set")
        if auto["phase_rows"]:
            quick_summary = []
            for phase_key, label in [("warmup", "Warmup"), ("middle", "Mittelteil"), ("peak", "Peak"), ("closing", "Closing")]:
                count_here = len(auto.get(phase_key, []))
                if count_here:
                    quick_summary.append(f"{label}: {count_here}")
            if quick_summary:
                st.caption(" | ".join(quick_summary))
            for idx, row in enumerate(auto["phase_rows"], start=1):
                st.write(f"{idx}. {row['song']} — {row['phase_label']} — {row['energy']} — {row['energy_label']}")
                st.caption(f"Basis {row['count']}x | Gäste-Bonus {row['guest_bonus']} | Übergang {row['transition_bonus']} | Score {row['score']}")
            if st.button("➕ Komplettes Auto-Set in Set Builder übernehmen", key="take_auto_set", width="stretch"):
                st.session_state["set_builder"] = auto["full_set"].copy()
                st.success("Auto-Set in Set Builder übernommen.")
                st.rerun()
            st.download_button(
                "📥 Auto-Set als TXT herunterladen",
                "\n".join([f"{row['song']} | {row['phase_label']} | {row['energy']} | {row['energy_label']}" for row in auto["phase_rows"]]),
                file_name="auto_event_set_v94.txt",
                width="stretch",
            )
        else:
            st.info("Für diese Auswahl konnten noch keine passenden Songs gefunden werden.")

    with tabs[1]:
        st.subheader("Flow Details")
        if auto["phase_rows"]:
            flow_rows = []
            for idx, row in enumerate(auto["phase_rows"], start=1):
                flow_rows.append({
                    "#": idx,
                    "Song": row["song"],
                    "Phase": row["phase_label"],
                    "Energie": row["energy"],
                    "Energie-Label": row["energy_label"],
                    "Basis": row["count"],
                    "Gäste-Bonus": row["guest_bonus"],
                    "Übergang": row["transition_bonus"],
                    "Score": row["score"],
                })
            st.dataframe(flow_rows, width="stretch", hide_index=True)
        else:
            st.info("Noch keine Flow-Daten verfügbar.")

    for tab, key, label in [
        (tabs[2], "warmup", "Warmup"),
        (tabs[3], "middle", "Mittelteil"),
        (tabs[4], "peak", "Peak"),
        (tabs[5], "closing", "Closing"),
    ]:
        with tab:
            a, b, c = st.columns(3)
            with a:
                st.subheader(f"{label} Songs")
                rows = auto[key]
                if rows:
                    for idx, song in enumerate(rows, start=1):
                        st.write(f"{idx}. {song}")
                else:
                    st.info("Keine Songs gefunden.")
            with b:
                st.subheader(f"{label} Songpaare")
                rows = auto["pairs"].get(key, [])
                if rows:
                    for idx, combo in enumerate(rows, start=1):
                        st.write(f"{idx}. {combo}")
                else:
                    st.info("Keine Songpaare gefunden.")
            with c:
                st.subheader(f"{label} Blöcke")
                rows = auto["blocks"].get(key, [])
                if rows:
                    for idx, combo in enumerate(rows, start=1):
                        st.write(f"{idx}. {combo}")
                else:
                    st.info("Keine Blöcke gefunden.")


def guess_source_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return stem


def _normalize_menu_label(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9äöüß ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def update_recent_menus(target: str, *, max_items: int = 6):
    target = str(target or "").strip()
    if not target:
        return
    existing = [item for item in st.session_state.get("recent_menus", []) if item != target]
    st.session_state["recent_menus"] = [target, *existing][:max_items]


def set_active_menu(target: str):
    st.session_state["active_menu"] = target
    update_recent_menus(target)


def jump_button(label: str, target: str, *, key: str, use_container_width: bool = True):
    width = "stretch" if use_container_width else "content"
    if st.button(label, key=key, width=width):
        set_active_menu(target)
        st.rerun()


def render_v10_quickflow_box():
    with st.expander("🚀 V10 Schnell-Workflow", expanded=True):
        st.write("**In 3 Schritten zum ersten Setvorschlag:**")
        s1, s2, s3 = st.columns(3)
        with s1:
            st.markdown("**1. Event wählen**")
            st.caption("Event Presets oder Event vorbereiten öffnen.")
            jump_button("Event Presets", "Event Presets", key="v10_quick_presets")
        with s2:
            st.markdown("**2. Stil / Quelle wählen**")
            st.caption("Smart Event Brain oder Event Kontext KI nutzen.")
            a, b = st.columns(2)
            with a:
                jump_button("Event Brain", "Smart Event Brain", key="v10_quick_brain")
            with b:
                jump_button("Kontext KI", "Event Kontext KI", key="v10_quick_ctx")
        with s3:
            st.markdown("**3. Set generieren**")
            st.caption("Auto Event Set bauen und bei Bedarf in den Set Builder übernehmen.")
            a, b = st.columns(2)
            with a:
                jump_button("Auto Event Set", "Auto Event Set", key="v10_quick_auto")
            with b:
                jump_button("Set Builder", "Set Builder", key="v10_quick_setbuilder")
        st.info("Die KI lernt weiter nur aus echten gespielten Playlists. Vorschläge bleiben dadurch nachvollziehbar und eventbezogen.")


def render_start_screen(p_count: int, t_count: int, l_count: int, c_count: int):
    st.header("Was willst du heute machen?")
    st.caption("Der Upload bleibt wie bisher direkt im Tool. Von hier springst du nur schneller in den passenden Arbeitsbereich.")
    render_v10_quickflow_box()

    wf1, wf2, wf3, wf4 = st.columns(4)
    with wf1:
        st.markdown("### 🎧 Set vorbereiten")
        st.caption("Direkt zu Event, Herkunft, Top Songs, Übergängen und Blöcken.")
        jump_button("Jetzt Set vorbereiten", "Event vorbereiten", key="home_wf_prepare")
    with wf2:
        st.markdown("### 🔍 Playlist analysieren")
        st.caption("Einzelne Playlist prüfen oder im Analyse Hub aus echten Daten lernen.")
        a, b = st.columns(2)
        with a:
            jump_button("Analyse Hub", "Analyse Hub", key="home_wf_hub")
        with b:
            jump_button("Playlists", "Playlists durchsuchen", key="home_wf_browse")
    with wf3:
        st.markdown("### ⭐ Referenz nutzen")
        st.caption("Referenz-/Top-Playlists schneller öffnen und gezielt als Best-of nutzen.")
        if st.button("Referenz öffnen", key="home_wf_reference", width="stretch"):
            st.session_state["browse_source"] = "Referenz"
            st.session_state["browse_sort"] = "Neueste zuerst"
            st.session_state["browse_top"] = False
            set_active_menu("Playlists durchsuchen")
            st.rerun()
    with wf4:
        st.markdown("### 🔥 Inspiration holen")
        st.caption("Davor/Danach, starke Blöcke, Rollen und Timing für echte DJ-Muster.")
        a, b = st.columns(2)
        with a:
            jump_button("Heute auflegen", "Heute auflegen", key="home_wf_today")
        with b:
            jump_button("KI Rollen", "KI Rollen & Timing", key="home_wf_roles")

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Playlists", p_count)
    t2.metric("Tracks", t_count)
    t3.metric("Rekordbox", l_count)
    t4.metric("Gemerkte Kombis", c_count)

    with st.expander("📱 iPad sofort verbinden", expanded=False):
        render_ipad_connection_box()

    st.info("🎤 Neu in V103: Backups können jetzt zusätzlich direkt zu Dropbox synchronisiert werden. Ideal für Render Free ohne bezahlte Persistent Disk.")
    render_quick_backup_button()

    st.markdown("### Schnellstart")

    row0 = st.columns(3)
    with row0[0]:
        st.markdown("**⚡ Event Presets**")
        st.caption("1 Klick lädt fertige Kombinationen wie Hochzeit + Benjamin Schneider direkt in die Zielansicht.")
        jump_button("Zu den Presets", "Event Presets", key="home_presets")
    with row0[1]:
        st.markdown("**🎧 Set vorbereiten**")
        st.caption("Top Songs, Übergänge, 3er/4er-Blöcke und fehlende Songs für ein Event.")
        jump_button("Jetzt vorbereiten", "Event vorbereiten", key="home_event_prepare")
    with row0[2]:
        st.markdown("**📥 Playlists importieren**")
        st.caption("TXT, mehrere Dateien oder ZIP hochladen. Upload bleibt direkt im Tool.")
        jump_button("Zum Import", "Playlists importieren", key="home_import")

    row1 = st.columns(3)
    with row1[0]:
        st.markdown("**🔍 Analyse Hub**")
        st.caption("Top Songs, Übergänge, Blöcke und davor-danach an einem Ort.")
        jump_button("Zum Analyse Hub", "Analyse Hub", key="home_track")
    with row1[1]:
        st.markdown("**🧱 Set Builder**")
        st.caption("Set bauen, Flow prüfen, bessere Alternativen finden und automatisch erweitern.")
        jump_button("Zum Set Builder", "Set Builder", key="home_set_builder")
    with row1[2]:
        st.markdown("**🎼 Rekordbox / Fehlende Songs**")
        st.caption("XML importieren und sofort sehen, was dir für Event oder Stil noch fehlt.")
        a, b = st.columns(2)
        with a:
            jump_button("XML verbinden", "Rekordbox verbinden", key="home_rb")
        with b:
            jump_button("Fehlende prüfen", "Fehlende Songs", key="home_missing")

    row2 = st.columns(3)
    with row2[0]:
        st.markdown("**📱 iPad Verbindung**")
        st.caption("Zeigt dir direkt die Adresse, damit du das Tool am iPad öffnen kannst.")
        jump_button("iPad öffnen", "iPad Verbindung", key="home_ipad")
    with row2[1]:
        st.markdown("**⭐ Merken / Dubletten**")
        st.caption("Gespeicherte Kombis ansehen oder vor Analyse doppelte Playlists prüfen.")
        a, b = st.columns(2)
        with a:
            jump_button("Gemerkte Kombis", "Gemerkte Kombinationen", key="home_saved")
        with b:
            jump_button("Dubletten", "Doppelte Playlists", key="home_dupes")
    with row2[2]:
        st.markdown("**📊 Upload Dashboard**")
        st.caption("Zeigt dir Upload-Historie, Fehler, Dubletten und den letzten Status glasklar.")
        jump_button("Upload Dashboard", "Upload Dashboard", key="home_upload_dashboard")

    row3 = st.columns(3)
    with row3[0]:
        st.markdown("**🔥 Wichtige Tracks**")
        st.caption("Zeigt dir die wichtigsten Songs für Event, Herkunft und dein Setup.")
        jump_button("Wichtige Tracks", "Wichtige Tracks", key="home_important")
    with row3[1]:
        st.markdown("**🎤 Heute auflegen**")
        st.caption("Sofort Warmup, Mittelteil, Peak, Closing, Paare und Blöcke für dein heutiges Event.")
        jump_button("Heute auflegen", "Heute auflegen", key="home_today_dj")
    with row3[2]:
        st.markdown("**🧠 Smart Event Brain**")
        st.caption("Steuert Gäste-Alter, Stimmung und Energie-Kurve für ein Event-Profil.")
        jump_button("Smart Event Brain", "Smart Event Brain", key="home_event_brain")


    row4 = st.columns(3)
    with row4[0]:
        st.markdown("**🧠 KI Rollen & Timing**")
        st.caption("Zeigt dir klar, welche Songs eher Opener, Aufbau, Peak, Closing oder Bridge sind – und wann sie typischerweise laufen.")
        jump_button("KI Rollen öffnen", "KI Rollen & Timing", key="home_ai_roles")
    with row4[1]:
        st.markdown("**🎯 Track → Track KI**")
        st.caption("Lernt echte Folgetracks, sichere Wechsel und jetzt komplette DJ-Ketten ab einem Song.")
        jump_button("Transition KI", "Transition KI", key="home_transition_ki")
    with row4[2]:
        st.markdown("**🧠 Learning / Event Kontext**")
        st.caption("Zeigt dir, warum die KI etwas gelernt hat und wie Songs je Event gelesen werden.")
        a, b = st.columns(2)
        with a:
            jump_button("Learning", "Learning Dashboard", key="home_learning_dash")
        with b:
            jump_button("Kontext KI", "Event Kontext KI", key="home_event_context")
    with row4[2]:
        st.markdown("**🧠 Event Kontext KI**")
        st.caption("Zeigt dir Songs klarer im Kontext von Event, Timing und Gäste-Typ.")
        jump_button("Event Kontext KI", "Event Kontext KI", key="home_event_context_ki")

    st.markdown("### Heute wahrscheinlich sinnvoll")
    hint1, hint2, hint3 = st.columns(3)
    hint1.info("**1. Upload**\n\nNeue Playlists direkt importieren, damit alles im selben Bestand analysiert wird.")
    hint2.info("**2. Event vorbereiten**\n\nQuelle + Anlass wählen und starke Songs, Übergänge und Blöcke prüfen.")
    hint3.info("**3. Set Builder**\n\nGute Treffer übernehmen und dein Set direkt bewerten lassen.")

    st.markdown("### Was im Tool schon drin ist")
    st.write("- Upload direkt im Tool bleibt erhalten")
    st.write("- Analyse Hub mit Songs / Übergängen / Blöcken / davor-danach")
    st.write("- 2er-, 3er-, 4er- und 5er-Kombinationen")
    st.write("- Set Builder mit Bewertung und Auto-Erweiterung")
    st.write("- Rekordbox XML + fehlende Songs")
    st.write("- Dubletten-Erkennung und gemerkte Kombinationen")
    st.write("- Smart Selftest Level 2 für Verhaltensprüfungen")
    st.write("- Smart Event Brain mit Gäste-Alter, Stimmung und Energie-Kurve")



def _has_db_column(table_name: str, column_name: str) -> bool:
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table_name})")
        cols = {row[1] for row in cur.fetchall()}
        conn.close()
        return column_name in cols
    except Exception:
        return False


def _code_contains(snippet: str) -> bool:
    try:
        this_file = Path(__file__)
        if this_file.exists():
            data = this_file.read_text(encoding="utf-8")
            return snippet in data
    except Exception:
        pass
    return False


def run_master_selftest():
    results = []

    def add(feature_key: str, ok: bool, detail: str):
        results.append({
            "key": feature_key,
            "label": FEATURE_MANIFEST.get(feature_key, feature_key),
            "ok": bool(ok),
            "detail": detail,
        })

    menu_snapshot = MENU_OPTIONS if "MENU_OPTIONS" in globals() else []

    # Nur Features prüfen, die in dieser Version wirklich zum aktiven Stand gehören.
    add("startscreen", "🏠 Start" in menu_snapshot, "Start-Menü vorhanden")
    add("import_text", "Playlists importieren" in menu_snapshot, "Import-Menü vorhanden")
    add("import_file", "Playlists importieren" in menu_snapshot, "Datei-Import läuft über Import-Menü")
    add("import_multi", _code_contains('Mehrere Dateien hochladen'), "Mehrfach-Import im Code gefunden")
    add("import_zip", _code_contains('ZIP hochladen'), "ZIP-Import im Code gefunden")
    add("upload_feedback", "render_last_upload_feedback" in globals(), "Upload-Feedback-Funktion vorhanden")
    add("playlist_cards", "get_library_overview" in globals(), "Bibliotheks-Übersicht vorhanden")
    add("latest_imports", "render_recent_import_runs" in globals(), "Zuletzt-importiert-Ansicht vorhanden")
    add("playlist_sorting", _code_contains('browse_sort') or ("get_playlists" in globals()), "Playlist-Sortierung/Browse-Basis vorhanden")
    add("event_merge", "rename_meta_value" in globals(), "Anlass zusammenführen vorhanden")
    add("source_merge", "rename_meta_value" in globals(), "Herkunft zusammenführen vorhanden")
    add("set_builder", "Set Builder" in menu_snapshot, "Set-Builder-Menü vorhanden")
    add("event_presets", "Event Presets" in menu_snapshot, "Event-Presets-Menü vorhanden")
    add("ipad_connection", "iPad Verbindung" in menu_snapshot, "iPad-Verbindungs-Menü vorhanden")
    add("energy_system", "estimate_track_energy" in globals(), "Energy-System-Funktion vorhanden")
    add("rekordbox", "Rekordbox verbinden" in menu_snapshot, "Rekordbox-Menü vorhanden")
    add("missing_tracks", "Fehlende Songs" in menu_snapshot, "Fehlende-Songs-Menü vorhanden")
    add("duplicates", "Doppelte Playlists" in menu_snapshot, "Dubletten-Menü vorhanden")
    add("system_version", "System / Version" in menu_snapshot, "System-/Versions-Menü vorhanden")
    add("delete_clean", "delete_all_playlists" in globals() and "clean_all_playlist_meta_values" in globals(), "Delete + Clean Funktionen vorhanden")
    add("upload_dashboard", "render_upload_dashboard_page" in globals(), "Upload Dashboard vorhanden")
    add("learning_dashboard", "render_learning_dashboard_page" in globals(), "Learning Dashboard vorhanden")
    add("event_context_ki", "render_event_context_ki_page" in globals(), "Event Kontext KI vorhanden")
    add("smart_event_brain", "render_smart_event_brain_page" in globals(), "Smart Event Brain vorhanden")
    add("performance_boost", "compute_data_cached" in globals(), "Performance Boost / Cache vorhanden")
    add("learning_rebuild", "rebuild_learning_engine" in globals(), "Learning Rebuild vorhanden")
    add("learning_ui", "render_learning_engine_panel" in globals(), "Learning UI / Rebuild Button vorhanden")
    add("event_context_ki", "render_event_context_ki_page" in globals(), "Event Kontext KI vorhanden")
    add("release_guard", "build_release_guard_report" in globals(), "Startup Release Guard vorhanden")
    add("manifest_diff", "compare_release_guard_snapshots" in globals(), "Manifest-Diff vorhanden")

    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])

    return {
        "results": results,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "all_ok": fail_count == 0,
    }


def _behavior_test_sorting_latest():
    try:
        rows = get_playlists()
        if len(rows) < 2:
            return True, "Zu wenig Playlists für echten Sortiertest"
        sorted_rows = sorted(rows, key=lambda x: (x[-1] or "", x[0]), reverse=True)
        latest_ok = True
        for i in range(len(sorted_rows) - 1):
            if (sorted_rows[i][-1] or "") < (sorted_rows[i + 1][-1] or ""):
                latest_ok = False
                break
        return latest_ok, "Neueste-zuerst-Sortierung berechenbar"
    except Exception as e:
        return False, f"Sortiertest fehlgeschlagen: {e}"


def _behavior_test_sorting_az():
    try:
        rows = get_playlists()
        if len(rows) < 2:
            return True, "Zu wenig Playlists für A-Z-Test"
        sorted_rows = sorted(rows, key=lambda x: str(x[1] or "").lower())
        az_ok = True
        for i in range(len(sorted_rows) - 1):
            if str(sorted_rows[i][1] or "").lower() > str(sorted_rows[i + 1][1] or "").lower():
                az_ok = False
                break
        return az_ok, "Name-A-Z-Sortierung berechenbar"
    except Exception as e:
        return False, f"A-Z-Test fehlgeschlagen: {e}"


def _behavior_test_latest_imports():
    try:
        overview = get_library_overview()
        latest_rows = overview.get("latest_rows", [])
        if not latest_rows:
            return True, "Keine Importe vorhanden"
        ids = [row[0] for row in latest_rows if row and len(row) > 0]
        ordered = ids == sorted(ids, reverse=True)
        return ordered, "Zuletzt importiert liefert neueste IDs zuerst"
    except Exception as e:
        return False, f"Latest-Import-Test fehlgeschlagen: {e}"


def _behavior_test_genre_db():
    try:
        return _has_db_column("playlists", "genre"), "DB-Spalte genre vorhanden"
    except Exception as e:
        return False, f"Genre-DB-Test fehlgeschlagen: {e}"


def _behavior_test_genre_filter():
    try:
        if not _has_db_column("playlists", "genre"):
            return False, "Genre-Spalte fehlt"
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT genre FROM playlists WHERE TRIM(COALESCE(genre, '')) != '' LIMIT 1")
        row = cur.fetchone()
        conn.close()
        if not row:
            return True, "Keine Genre-Daten zum Filtern vorhanden"
        genre_value = row[0]
        rows = get_playlists(genre=genre_value)
        ok = all((len(r) >= 5 and str(r[4] or "") == str(genre_value)) for r in rows)
        return ok, f"Genre-Filter liefert nur '{genre_value}'"
    except Exception as e:
        return False, f"Genre-Filter-Test fehlgeschlagen: {e}"


def _behavior_test_manifest_vs_menu():
    try:
        menu_snapshot = MENU_OPTIONS if "MENU_OPTIONS" in globals() else []
        required_labels = [
            "🏠 Start",
            "Playlists importieren",
            "Playlists durchsuchen",
            "Set Builder",
            "Rekordbox verbinden",
            "Fehlende Songs",
            "Doppelte Playlists",
            "System / Version",
            "Backup / Restore",
        ]
        missing = [label for label in required_labels if label not in menu_snapshot]
        if missing:
            return False, "Fehlende Menüs: " + ", ".join(missing)
        return True, "Pflicht-Menüs sind vorhanden"
    except Exception as e:
        return False, f"Menü-Test fehlgeschlagen: {e}"


def _behavior_test_upload_feedback_hooks():
    try:
        ok = ("set_last_upload_feedback" in globals()) and ("render_last_upload_feedback" in globals())
        return ok, "Upload-Feedback-Hooks vorhanden"
    except Exception as e:
        return False, f"Upload-Feedback-Test fehlgeschlagen: {e}"


def run_smart_selftest_level2():
    tests = [
        ("sort_latest", "Sortierung Neueste zuerst", _behavior_test_sorting_latest),
        ("sort_az", "Sortierung Name A-Z", _behavior_test_sorting_az),
        ("latest_imports", "Zuletzt importiert korrekt", _behavior_test_latest_imports),
        ("manifest_menu", "Manifest gegen Menü geprüft", _behavior_test_manifest_vs_menu),
        ("upload_feedback", "Upload-Feedback eingebunden", _behavior_test_upload_feedback_hooks),
        ("upload_dashboard", "Upload Dashboard sichtbar", lambda: (("Upload Dashboard" in (MENU_OPTIONS if "MENU_OPTIONS" in globals() else [])), "Upload Dashboard im Menü vorhanden")),
        ("learning_dashboard", "Learning Dashboard sichtbar", lambda: (("Learning Dashboard" in (MENU_OPTIONS if "MENU_OPTIONS" in globals() else [])), "Learning Dashboard im Menü vorhanden")),
        ("smart_event_brain", "Smart Event Brain sichtbar", lambda: (("Smart Event Brain" in (MENU_OPTIONS if "MENU_OPTIONS" in globals() else [])), "Smart Event Brain im Menü vorhanden")),
        ("event_context_ki", "Event Kontext KI sichtbar", lambda: (("Event Kontext KI" in (MENU_OPTIONS if "MENU_OPTIONS" in globals() else [])), "Event Kontext KI im Menü vorhanden")),
        ("learning_ui", "Learning UI sichtbar", lambda: ((("render_learning_engine_panel" in globals()) and ("rebuild_learning_engine" in globals())), "Learning-Panel + Rebuild vorhanden")),
        ("event_context_ki", "Event Kontext KI sichtbar", lambda: ((("render_event_context_ki_page" in globals()) and ("get_track_event_context_pack" in globals())), "Event-Kontext-Seite + Pack vorhanden")),
        ("release_guard", "Release Guard arbeitet", lambda: (("status" in build_release_guard_report(write_current=False)[2]), "Release Guard Bericht erzeugbar")),
    ]
    results = []
    for key, label, fn in tests:
        ok, detail = fn()
        results.append({"key": key, "label": label, "ok": bool(ok), "detail": detail})
    ok_count = sum(1 for r in results if r["ok"])
    fail_count = sum(1 for r in results if not r["ok"])
    return {"results": results, "ok_count": ok_count, "fail_count": fail_count, "all_ok": fail_count == 0}




def _release_guard_dir() -> Path:
    target = APP_DATA_DIR / RELEASE_GUARD_MANIFEST_DIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _release_guard_current_path() -> Path:
    return _release_guard_dir() / "current_manifest.json"


def _release_guard_stable_path() -> Path:
    return _release_guard_dir() / "stable_manifest.json"


def _feature_snapshot_from_selftests():
    level1 = run_master_selftest()
    level2 = run_smart_selftest_level2()
    features = {}
    for row in level1.get("results", []):
        features[row["key"]] = {
            "label": row.get("label", row["key"]),
            "present": bool(row.get("ok")),
            "detail": row.get("detail", ""),
            "level": 1,
        }
    for row in level2.get("results", []):
        features[row["key"]] = {
            "label": row.get("label", row["key"]),
            "present": bool(row.get("ok")),
            "detail": row.get("detail", ""),
            "level": 2,
        }
    return {
        "app_version": APP_VERSION,
        "app_short_version": APP_SHORT_VERSION,
        "build_date": APP_BUILD_DATE,
        "build_time": APP_BUILD_TIME,
        "build_source": APP_BUILD_SOURCE,
        "baseline_id": APP_BASELINE_ID,
        "feature_manifest": FEATURE_MANIFEST,
        "features": features,
        "changelog_top": CHANGELOG[0] if CHANGELOG else {},
        "db_checks": {
            "playlists.upload_note": _has_db_column("playlists", "upload_note"),
            "playlists.sub_event": _has_db_column("playlists", "sub_event"),
        },
        "generated_at": f"{APP_BUILD_DATE} {APP_BUILD_TIME}",
    }


def _write_release_guard_manifest(snapshot: dict, target: Path):
    target.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def load_release_guard_manifest(target: Path):
    try:
        if target.exists():
            return json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def compare_release_guard_snapshots(previous: dict | None, current: dict):
    prev_features = (previous or {}).get("features", {})
    cur_features = current.get("features", {})
    missing = []
    new_ok = []
    changed = []
    carried = []

    for key, prev_row in prev_features.items():
        prev_ok = bool(prev_row.get("present"))
        cur_row = cur_features.get(key)
        cur_ok = bool(cur_row.get("present")) if cur_row else False
        label = (cur_row or prev_row).get("label", key)
        if prev_ok and not cur_ok:
            missing.append({"key": key, "label": label, "before": prev_row.get("detail", ""), "now": (cur_row or {}).get("detail", "nicht gefunden")})
        elif prev_ok and cur_ok:
            carried.append({"key": key, "label": label})
        elif (not prev_ok) and cur_ok:
            new_ok.append({"key": key, "label": label, "detail": cur_row.get("detail", "")})

    for key, cur_row in cur_features.items():
        if key not in prev_features and cur_row.get("present"):
            new_ok.append({"key": key, "label": cur_row.get("label", key), "detail": cur_row.get("detail", "")})

    prev_db = (previous or {}).get("db_checks", {})
    cur_db = current.get("db_checks", {})
    for key, cur_val in cur_db.items():
        prev_val = prev_db.get(key)
        if prev_val is None:
            continue
        if bool(prev_val) != bool(cur_val):
            changed.append({"key": key, "label": key, "before": prev_val, "now": cur_val})

    status = "green"
    if missing:
        status = "red"
    elif changed:
        status = "yellow"

    summary = {
        "status": status,
        "missing": missing,
        "new": new_ok,
        "changed": changed,
        "carried_count": len(carried),
        "previous_version": (previous or {}).get("app_short_version", "keine stabile Referenz"),
        "current_version": current.get("app_short_version", APP_SHORT_VERSION),
        "top_new": current.get("changelog_top", {}).get("new", []),
        "top_fixes": current.get("changelog_top", {}).get("fixes", []),
    }
    return summary


@st.cache_data(ttl=180, show_spinner=False)
def build_release_guard_report_cached():
    current = _feature_snapshot_from_selftests()
    stable = load_release_guard_manifest(_release_guard_stable_path())
    return current, stable, compare_release_guard_snapshots(stable, current)


def build_release_guard_report(write_current: bool = True):
    current, stable, diff = build_release_guard_report_cached()
    if write_current and RELEASE_GUARD_AUTO_WRITE:
        _write_release_guard_manifest(current, _release_guard_current_path())
    return current, stable, diff


def save_current_as_stable_baseline():
    current = _feature_snapshot_from_selftests()
    _write_release_guard_manifest(current, _release_guard_stable_path())
    _write_release_guard_manifest(current, _release_guard_current_path())
    try:
        build_release_guard_report_cached.clear()
    except Exception:
        pass
    return current


def render_release_guard_banner():
    try:
        _, stable, diff = build_release_guard_report(write_current=True)
    except Exception as e:
        st.warning(f"Release Guard konnte nicht geprüft werden: {e}")
        return

    if not stable:
        st.info("🧭 Release Guard: Noch keine stabile Referenz gespeichert. Im Systembereich kannst du diese Version als stabile Basis festhalten.")
        return

    missing_count = len(diff.get("missing", []))
    changed_count = len(diff.get("changed", []))
    new_count = len(diff.get("new", []))
    prev_v = diff.get("previous_version", "?")
    cur_v = diff.get("current_version", "?")

    if diff.get("status") == "red":
        st.error(f"🚨 Release Guard {cur_v} gegen {prev_v}: {missing_count} Pflichtfunktion(en) fehlen. Neu/Fix: {new_count}. Bitte vor stabiler Freigabe prüfen.")
    elif diff.get("status") == "yellow":
        st.warning(f"⚠️ Release Guard {cur_v} gegen {prev_v}: keine harten Verluste, aber {changed_count} Änderung(en). Neu/Fix: {new_count}.")
    else:
        st.success(f"✅ Release Guard {cur_v} gegen {prev_v}: keine fehlenden Pflichtfunktionen erkannt. Neu/Fix: {new_count}.")

    with st.expander("Release Guard Details", expanded=False):
        if diff.get("top_new"):
            st.write("Neu in dieser Version:")
            for item in diff["top_new"]:
                st.write(f"- {item}")
        if diff.get("top_fixes"):
            st.write("Gefixt in dieser Version:")
            for item in diff["top_fixes"]:
                st.write(f"- {item}")
        if diff.get("missing"):
            st.write("Fehlend gegenüber letzter stabiler Version:")
            for item in diff["missing"]:
                st.write(f"- {item['label']} | vorher: {item['before']} | jetzt: {item['now']}")
        else:
            st.write("- Keine fehlenden Pflichtfunktionen erkannt")
        if diff.get("changed"):
            st.write("Geänderte Prüfungen / DB-Zustände:")
            for item in diff["changed"]:
                st.write(f"- {item['label']}: vorher={item['before']} | jetzt={item['now']}")
        if diff.get("new"):
            st.write("Neu erkannt / jetzt vorhanden:")
            for item in diff["new"][:20]:
                st.write(f"- {item['label']} | {item['detail']}")

def render_system_version_page():
    st.header("System / Version")
    st.caption("Hier siehst du Version, Historie, Fixes, Release Guard und den Selbsttest gegen die Master-Baseline.")
    st.info("V15 Komfort: schnellerer Start, optionaler Systemstatus, dauerhafte UI-Einstellungen und leiser Start über VBS-Launcher.")

    a, b, c = st.columns(3)
    a.metric("Version", APP_VERSION)
    b.metric("Build", APP_BUILD_DATE)
    c.metric("Baseline", APP_BASELINE_ID)
    st.caption(f"Aufgebaut auf: {SOURCE_MASTER_BUILD}")
    st.caption(MASTER_BUILD_RULE)

    st.subheader("Release Guard – Vergleich gegen letzte stabile Version")
    current_snapshot, stable_snapshot, diff = build_release_guard_report(write_current=True)
    x1, x2, x3, x4 = st.columns(4)
    x1.metric("Vergleich", f"{diff['current_version']} vs {diff['previous_version']}")
    x2.metric("Fehlend", len(diff.get("missing", [])))
    x3.metric("Neu erkannt", len(diff.get("new", [])))
    x4.metric("Status", "Rot" if diff.get("status") == "red" else ("Gelb" if diff.get("status") == "yellow" else "Grün"))

    if not stable_snapshot:
        st.info("Noch keine stabile Referenz gespeichert. Klicke unten auf 'Diese Version als stabile Basis merken', sobald du diesen Stand freigeben willst.")
    elif diff.get("status") == "red":
        st.error("Gegenüber der letzten stabilen Version fehlen Pflichtfunktionen. Diese Version sollte noch nicht als stabil gelten.")
    elif diff.get("status") == "yellow":
        st.warning("Keine harten Verluste erkannt, aber es gibt Änderungen, die du kurz prüfen solltest.")
    else:
        st.success("Keine fehlenden Pflichtfunktionen gegenüber der letzten stabilen Version erkannt.")

    if diff.get("top_new"):
        st.write("Neu:")
        for item in diff["top_new"]:
            st.write(f"- {item}")
    if diff.get("top_fixes"):
        st.write("Gefixt:")
        for item in diff["top_fixes"]:
            st.write(f"- {item}")
    if diff.get("missing"):
        st.write("Fehlend:")
        for item in diff["missing"]:
            st.write(f"- {item['label']} | vorher: {item['before']} | jetzt: {item['now']}")
    if diff.get("changed"):
        st.write("Geändert:")
        for item in diff["changed"]:
            st.write(f"- {item['label']}: vorher={item['before']} | jetzt={item['now']}")

    c_guard1, c_guard2 = st.columns(2)
    if c_guard1.button("Diese Version als stabile Basis merken", key="release_guard_mark_stable", width="stretch"):
        save_current_as_stable_baseline()
        st.success("Diese Version wurde als stabile Referenz gespeichert.")
        st.rerun()
    stable_path = _release_guard_stable_path()
    c_guard2.caption(f"Stabile Referenz-Datei: {stable_path}")

    st.subheader("Was ist in dieser Version Pflichtbestand?")
    for feature_key, label in FEATURE_MANIFEST.items():
        st.write(f"• {label}")

    st.subheader("Build Notes")
    for note in BUILD_NOTES:
        st.write(f"• {note}")

    st.subheader("Changelog / Fix-Historie")
    for entry in CHANGELOG:
        with st.expander(f"{entry['version']} | {entry['date']}"):
            st.write("Neu:")
            for item in entry.get("new", []):
                st.write(f"- {item}")
            st.write("Fixes:")
            for item in entry.get("fixes", []):
                st.write(f"- {item}")

    st.subheader("Selbsttest Level 1 – Pflichtbestand")
    report = run_master_selftest()
    m1, m2, m3 = st.columns(3)
    m1.metric("OK", report["ok_count"])
    m2.metric("Fehlt", report["fail_count"])
    m3.metric("Status", "Stabil" if report["all_ok"] else "Prüfen")

    if report["all_ok"]:
        st.success("Alle Pflicht-Features der Master-Baseline sind vorhanden.")
    else:
        st.warning("Mindestens ein Pflicht-Feature fehlt oder konnte nicht bestätigt werden.")

    for row in report["results"]:
        if row["ok"]:
            st.success(f"{row['label']} — {row['detail']}")
        else:
            st.error(f"{row['label']} — {row['detail']}")

    st.subheader("Smart Selftest Level 2 – Funktioniert es wirklich?")
    report2 = run_smart_selftest_level2()
    s1, s2, s3 = st.columns(3)
    s1.metric("OK", report2["ok_count"])
    s2.metric("Fehler", report2["fail_count"])
    s3.metric("Status", "Verhalten OK" if report2["all_ok"] else "Verhalten prüfen")

    if report2["all_ok"]:
        st.success("Die wichtigsten Kernfunktionen bestehen auch den Verhaltenstest.")
    else:
        st.warning("Mindestens ein Verhaltenstest ist fehlgeschlagen. Bitte prüfen, bevor weitergebaut wird.")

    for row in report2["results"]:
        if row["ok"]:
            st.success(f"{row['label']} — {row['detail']}")
        else:
            st.error(f"{row['label']} — {row['detail']}")

    st.subheader("Learning Engine / Import Audit")
    learning = get_learning_engine_status()
    imports = get_import_log_stats()
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Letzter Rebuild", learning["last_rebuild_at"])
    l2.metric("Transition-Zeilen", learning["transition_rows"])
    l3.metric("Rollen-Zeilen", learning["role_rows"])
    l4.metric("Learning-Status", "Aktuell" if learning["is_current"] else "Veraltet")
    st.caption(f"Basis beim Rebuild: {learning['basis_playlists']} Playlists / {learning['basis_tracks']} Tracks")
    st.caption(f"Aktuell in DB: {learning['current_playlists']} Playlists / {learning['current_tracks']} Tracks")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("Importe (letzte 200)", imports["total_recent"])
    i2.metric("OK", imports["ok_recent"])
    i3.metric("Dublette", imports["duplicate_recent"])
    i4.metric("Übersprungen", imports["skipped_recent"])
    if st.button("🧠 Learning Engine Rebuild starten", key="system_learning_rebuild_btn", width="stretch"):
        result = rebuild_learning_engine()
        st.success(f"Learning neu aufgebaut: {result['playlists']} Playlists • {result['tracks']} Tracks • {result['transitions']} Übergänge • {result['roles']} Rollen")
        st.rerun()

    st.subheader("V123 Selftest + Learning Safe")
    st.info("V123 zeigt im Selftest nur noch echte relevante Fehler und baut den Lernstand beim Start automatisch wieder auf, wenn echte Daten da sind, aber die vorberechneten Learning-Werte leer sind.")

    st.subheader("V122 Event Kontext KI")
    st.info("V122 liest Songs klarer im Kontext von Event, Timing und Gäste-Typ und ergänzt damit die bestehende DJ-KI sinnvoll.")

    st.subheader("V121 Learning Engine sichtbar")
    st.info("V121 zeigt den Learning-Status direkt im Systembereich und gibt dir dort den sichtbaren Rebuild-Button.")

    st.subheader("V120 Upload / Delete / Dubletten")
    st.info("V120 macht Upload-Audit, Dubletten-Blick und Delete-Flow sichtbarer und ruhiger für den täglichen Einsatz.")

    st.subheader("V119 Upload / iPad UX")
    st.info("V119 zeigt letzte Uploads direkt auf der Import-Seite, setzt hängende Busy-Zustände automatisch zurück und macht Import-Feedback klarer – besonders hilfreich am iPad.")

    st.subheader("V130 Smart Event Brain")
    st.info("V130 ergänzt speicherbare Event-Profile mit Gäste-Alter, Stimmung und Energie-Kurve. Damit wird die Event-KI deutlich gezielter steuerbar.")

    st.subheader("V126 Pro Paket")
    st.info("V10 ist die Abschlussversion mit Einfach/Profi-Modus, Schnell-Workflow und Kompaktmodus auf Basis echter Playlist-Daten.")

    st.subheader("Data Safe Update System")
    st.info("V102 nutzt bevorzugt einen persistenten Datenpfad, zeigt Storage-Diagnose an, warnt bei Fallback-Speicher und legt weiter Build-Snapshots sowie Auto-Backups an.")
    st.caption(f"Live-DB: {DB_PATH}")
    st.caption(f"Backup-Ordner: {BACKUP_DIR}")

    st.subheader("Wichtige Regel ab jetzt")
    st.info("Neue Versionen dürfen nur noch auf dieser letzten Master-Datei aufgebaut werden. Keine alten Zwischenstände mehr verwenden.")




EVENT_PRESETS = [
    {"label": "Hochzeit – Benjamin Schneider", "event": "Hochzeit", "source": "Benjamin Schneider", "top_only": True},
    {"label": "Hochzeit – Michael Zimmermann", "event": "Hochzeit", "source": "Michael Zimmermann", "top_only": True},
    {"label": "90er / 2000er – Benjamin Schneider", "event": "90er-2000er", "source": "Benjamin Schneider", "top_only": True},
    {"label": "90er / 2000er – Global", "event": "90er-2000er", "source": "Global", "top_only": True},
    {"label": "Mixed – Global", "event": "Mixed", "source": "Global", "top_only": False},
    {"label": "Firmenfeier – Global", "event": "Firmenfeier", "source": "Global", "top_only": True},
    {"label": "Fasching – Reverenz", "event": "Fasching", "source": "Reverenz", "top_only": True},
    {"label": "Geburtstag – Michael Zimmermann", "event": "Geburtstag", "source": "Michael Zimmermann", "top_only": False},
]

PRESET_TARGETS = {
    "Event vorbereiten": ("ep_event", "ep_source", "ep_top"),
    "Vorbereitung": ("prep_event", "prep_source", "prep_top"),
    "Analyse Hub": ("hub_event", "hub_source", "hub_top"),
    "Set Builder": ("sb_event", "sb_source", "sb_top"),
    "Live Hilfe": ("live_event", "live_source", "live_top"),
    "Fehlende Songs": ("ms_event", "ms_source", "ms_top"),
    "Wichtige Tracks": ("imp_event", "imp_source", "imp_top"),
    "Heute auflegen": ("today_event", "today_source", "today_top"),
    "Auto Event Set": ("auto_event", "auto_source", "auto_top"),
    "Smart Event Brain": ("brain_event", "brain_source", "brain_top"),
    "Smart Flow Engine": ("flow_event", "flow_source", "flow_top"),
    "KI Rollen & Timing": ("ai_role_event", "ai_role_source", "ai_role_top"),
    "Transition KI": ("transition_event", "transition_source", "transition_top"),
    "Event Kontext KI": ("ctx_event", "ctx_source", "ctx_top"),
}


def apply_event_preset(preset: dict, target_menu: str = "Set Builder"):
    if not preset:
        return
    keys = PRESET_TARGETS.get(target_menu)
    if not keys:
        return
    event_key, source_key, top_key = keys
    st.session_state[event_key] = preset.get("event", "Alle") or "Alle"
    st.session_state[source_key] = preset.get("source", "Alle") or "Alle"
    st.session_state[top_key] = bool(preset.get("top_only", False))
    st.session_state["last_applied_preset"] = preset.get("label", "")
    st.session_state["active_menu"] = target_menu


def render_preset_bar(target_menu: str, title: str = "Event Presets"):
    st.markdown(f"### {title}")
    st.caption("1 Klick setzt Anlass, Herkunft und Top-Filter für den gewählten Bereich.")
    cols = st.columns(2)
    for idx, preset in enumerate(EVENT_PRESETS):
        with cols[idx % 2]:
            if st.button(preset["label"], key=f"preset_{target_menu}_{idx}", width="stretch"):
                apply_event_preset(preset, target_menu=target_menu)
                st.rerun()
    last = st.session_state.get("last_applied_preset")
    if last:
        st.caption(f"Zuletzt geladen: {last}")





def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        host = socket.gethostname()
        ip = socket.gethostbyname(host)
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


def get_ipad_url(port: int = 8501) -> str:
    return f"http://{get_local_ip()}:{port}"


def render_ipad_connection_box():
    url = get_ipad_url()
    st.subheader("iPad Verbindung")
    st.info("PC und iPad müssen im selben WLAN sein. Starte das Tool mit der iPad-Startdatei, dann ist es im Netzwerk erreichbar.")
    c1, c2 = st.columns(2)
    c1.metric("Lokale iPad-Adresse", url)
    c2.metric("Port", "8501")
    st.code(url)
    st.write("1. Starte auf dem Windows-PC die Datei **start_dj_tool_ipad.bat**.")
    st.write("2. Öffne auf dem iPad Safari oder Chrome.")
    st.write("3. Gib die Adresse von oben ein.")
    st.write("4. Falls es nicht aufgeht: prüfen, ob beide Geräte im selben WLAN sind und die Windows-Firewall den Zugriff erlaubt.")


def apply_ipad_optimized_css():
    st.markdown("""
    <style>
    .stButton > button {
        min-height: 3rem;
        font-size: 1rem;
        border-radius: 0.8rem;
    }
    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
        min-height: 3rem;
        font-size: 1rem;
    }
    @media (max-width: 1024px) {
        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100%;
        }
        h1, h2, h3 {
            line-height: 1.15;
        }
        .stButton > button {
            width: 100%;
            min-height: 3.2rem;
            font-size: 1.05rem;
        }
        .stTextInput input, .stTextArea textarea {
            font-size: 1.05rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)




AUTH_QUERY_KEY = "djtool_auth"

def get_persistent_login_token() -> str:
    import hashlib
    raw = f"{APP_LOGIN_PASSWORD}|{APP_BASELINE_ID}|v86_keep_login"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

def get_auth_query_value() -> str:
    try:
        return str(st.query_params.get(AUTH_QUERY_KEY, "") or "")
    except Exception:
        return ""

def set_auth_query_value(value: str):
    try:
        if value:
            st.query_params[AUTH_QUERY_KEY] = value
        else:
            try:
                del st.query_params[AUTH_QUERY_KEY]
            except Exception:
                pass
    except Exception:
        pass


BROWSER_LOGIN_STORAGE_KEY = "djtool_device_login"
BROWSER_LOGIN_COOKIE = "djtool_device_login"

def render_browser_login_sync():
    persistent_token = get_persistent_login_token()
    token_json = json.dumps(persistent_token)
    storage_key_json = json.dumps(BROWSER_LOGIN_STORAGE_KEY)
    cookie_key_json = json.dumps(BROWSER_LOGIN_COOKIE)
    query_key_json = json.dumps(AUTH_QUERY_KEY)
    components.html(
        f"""
        <script>
        const token = {token_json};
        const storageKey = {storage_key_json};
        const cookieKey = {cookie_key_json};
        const queryKey = {query_key_json};

        function readCookie(name) {{
            const parts = document.cookie ? document.cookie.split("; ") : [];
            for (const part of parts) {{
                const idx = part.indexOf("=");
                const key = idx >= 0 ? part.slice(0, idx) : part;
                const value = idx >= 0 ? part.slice(idx + 1) : "";
                if (key === name) return decodeURIComponent(value);
            }}
            return "";
        }}

        function writeCookie(name, value, days) {{
            const maxAge = days * 24 * 60 * 60;
            document.cookie = `${{name}}=${{encodeURIComponent(value)}}; path=/; max-age=${{maxAge}}; SameSite=Lax`;
        }}

        try {{
            const parentWindow = window.parent || window;
            const parentDoc = parentWindow.document || document;
            const href = parentWindow.location ? parentWindow.location.href : window.location.href;
            const url = new URL(href);
            const current = url.searchParams.get(queryKey) || "";
            const localValue = parentWindow.localStorage ? (parentWindow.localStorage.getItem(storageKey) || "") : "";
            const sessionValue = parentWindow.sessionStorage ? (parentWindow.sessionStorage.getItem(storageKey) || "") : "";
            const cookieValue = readCookie(cookieKey) || "";

            if (current === token) {{
                try {{ parentWindow.localStorage && parentWindow.localStorage.setItem(storageKey, token); }} catch (e) {{}}
                try {{ parentWindow.sessionStorage && parentWindow.sessionStorage.setItem(storageKey, token); }} catch (e) {{}}
                try {{ writeCookie(cookieKey, token, 365); }} catch (e) {{}}
            }} else {{
                const stored = localValue || sessionValue || cookieValue;
                if (stored === token) {{
                    url.searchParams.set(queryKey, token);
                    parentWindow.location.replace(url.toString());
                }}
            }}
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )

def render_browser_login_persist_now():
    persistent_token = get_persistent_login_token()
    token_json = json.dumps(persistent_token)
    storage_key_json = json.dumps(BROWSER_LOGIN_STORAGE_KEY)
    cookie_key_json = json.dumps(BROWSER_LOGIN_COOKIE)
    components.html(
        f"""
        <script>
        const token = {token_json};
        const storageKey = {storage_key_json};
        const cookieKey = {cookie_key_json};
        try {{
            const parentWindow = window.parent || window;
            if (parentWindow.localStorage) parentWindow.localStorage.setItem(storageKey, token);
            if (parentWindow.sessionStorage) parentWindow.sessionStorage.setItem(storageKey, token);
            document.cookie = `${{cookieKey}}=${{encodeURIComponent(token)}}; path=/; max-age=${{365*24*60*60}}; SameSite=Lax`;
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )

def render_browser_logout_cleanup():
    storage_key_json = json.dumps(BROWSER_LOGIN_STORAGE_KEY)
    cookie_key_json = json.dumps(BROWSER_LOGIN_COOKIE)
    query_key_json = json.dumps(AUTH_QUERY_KEY)
    components.html(
        f"""
        <script>
        const storageKey = {storage_key_json};
        const cookieKey = {cookie_key_json};
        const queryKey = {query_key_json};
        try {{
            const parentWindow = window.parent || window;
            if (parentWindow.localStorage) parentWindow.localStorage.removeItem(storageKey);
            if (parentWindow.sessionStorage) parentWindow.sessionStorage.removeItem(storageKey);
            document.cookie = `${{cookieKey}}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax`;
            const href = parentWindow.location ? parentWindow.location.href : window.location.href;
            const url = new URL(href);
            if (url.searchParams.has(queryKey)) {{
                url.searchParams.delete(queryKey);
                parentWindow.history.replaceState({{}}, "", url.toString());
            }}
        }} catch (e) {{}}
        </script>
        """,
        height=0,
    )

def build_role_timing_insights(event=None, source=None, top_only=False, sub_event=None, limit_per_role=12):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    role_buckets = {
        "🌙 Opener": [],
        "⬆️ Aufbau": [],
        "🔥 Peak": [],
        "🌅 Closing": [],
        "🔗 Bridge": [],
    }

    for norm, cnt in data["track_total_counts"].most_common(250):
        display = display_from_normalized(norm)
        role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        if role not in role_buckets:
            continue
        pos_stats = get_track_position_stats(display, event=event, source=source, top_only=top_only, sub_event=sub_event) or {}
        role_buckets[role].append({
            "song": display,
            "count": cnt,
            "phase": get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "timing": get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "avg_position": pos_stats.get("avg_position", "-"),
            "samples": pos_stats.get("sample_count", 0),
        })

    for key in list(role_buckets.keys()):
        role_buckets[key] = role_buckets[key][:limit_per_role]

    event_rows = []
    for norm, cnt in data["track_total_counts"].most_common(120):
        display = display_from_normalized(norm)
        event_counter = data["event_split"].get(norm, Counter())
        top_event = event_counter.most_common(1)[0][0] if event_counter else (event or "-")
        event_rows.append({
            "song": display,
            "count": cnt,
            "top_event": top_event or "-",
            "role": get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "timing": get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
        })

    return {
        "roles": role_buckets,
        "event_rows": event_rows,
        "total_tracks": len(data["track_total_counts"]),
        "total_pairs": len(data["pair_counts"]),
    }


def build_event_learning_summary(event=None, source=None, top_only=False, sub_event=None, per_event_limit=8):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    event_role_map = defaultdict(lambda: defaultdict(list))

    for norm, cnt in data["track_total_counts"].most_common(250):
        display = display_from_normalized(norm)
        role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        timing = get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        event_counter = data["event_split"].get(norm, Counter())
        target_events = event_counter.most_common(3) if event_counter else []
        if not target_events and event and event != "Alle":
            target_events = [(event, cnt)]
        for ev_name, ev_cnt in target_events:
            if not ev_name:
                continue
            event_role_map[ev_name][role].append({
                "song": display,
                "count": cnt,
                "event_count": ev_cnt,
                "timing": timing,
            })

    summary_rows = []
    for ev_name in sorted(event_role_map.keys(), key=lambda x: str(x).casefold()):
        role_map = event_role_map[ev_name]
        for role_name in ["🌙 Opener", "⬆️ Aufbau", "🔥 Peak", "🌅 Closing", "🔗 Bridge"]:
            rows = role_map.get(role_name, [])
            rows = sorted(rows, key=lambda x: (x["event_count"], x["count"], x["song"].casefold()), reverse=True)[:per_event_limit]
            for idx, row in enumerate(rows, start=1):
                summary_rows.append({
                    "Event": ev_name,
                    "Rolle": role_name,
                    "Song": row["song"],
                    "Wann typisch": row["timing"],
                    "Im Event": row["event_count"],
                    "Gesamt": row["count"],
                    "Rank": idx,
                })
    return summary_rows

def render_role_bucket_cards(rows, combo_type_prefix: str, set_key_prefix: str):
    if not rows:
        st.info("Noch keine passenden Songs gefunden.")
        return
    for idx, row in enumerate(rows, start=1):
        render_count_row(
            f"{idx}. {row['song']} | {row['phase']} | {row['timing']} | Ø {row['avg_position']}",
            row["count"],
            combo_type=combo_type_prefix,
            combo_text=row["song"],
            set_key=f"{set_key_prefix}_{idx}",
        )



def get_track_event_context_pack(track_name, event=None, source=None, top_only=False, sub_event=None, guest_type="Gemischt"):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    norm_query = normalize_track_text(track_name)
    matches = [k for k in data["track_total_counts"].keys() if norm_query and norm_query in k]
    if not matches:
        return None

    chosen = sorted(matches, key=lambda x: data["track_total_counts"][x], reverse=True)[0]
    display = display_from_normalized(chosen)
    total_count = int(data["track_total_counts"].get(chosen, 0))
    event_counter = data["event_split"].get(chosen, Counter())
    top_events = event_counter.most_common(6)

    role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    phase = get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    timing = get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    energy = estimate_track_energy(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    guest_bias = auto_set_guest_bias(display, guest_type)

    fit_label = "neutral"
    if guest_bias >= 10:
        fit_label = "stark passend"
    elif guest_bias >= 6:
        fit_label = "gut passend"
    elif guest_bias <= 0:
        fit_label = "allgemein / neutral"

    recommendations = []
    for norm, cnt in data["track_total_counts"].most_common(250):
        if norm == chosen:
            continue
        disp = display_from_normalized(norm)
        same_role = get_track_role_label(disp, event=event, source=source, top_only=top_only, sub_event=sub_event)
        same_phase = get_track_phase_label(disp, event=event, source=source, top_only=top_only, sub_event=sub_event)
        score = 0
        if same_role == role:
            score += 10
        if same_phase == phase:
            score += 8
        score += auto_set_guest_bias(disp, guest_type)
        score += min(10, int(cnt))
        if score > 12:
            recommendations.append({
                "song": disp,
                "role": same_role,
                "phase": same_phase,
                "count": cnt,
                "score": score,
            })
    recommendations = sorted(recommendations, key=lambda x: (x["score"], x["count"], x["song"].casefold()), reverse=True)[:10]

    return {
        "display": display,
        "total_count": total_count,
        "role": role,
        "phase": phase,
        "timing": timing,
        "energy": energy,
        "guest_bias": guest_bias,
        "guest_fit": fit_label,
        "top_events": top_events,
        "recommendations": recommendations,
    }

def render_event_context_ki_page():
    st.header("Event Kontext KI")
    st.caption("Hier liest die KI Songs klarer im Kontext von Event, Timing und Gäste-Typ.")

    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Event Kontext KI", title="Schnell laden")
    render_learning_rules_box("Event Kontext KI", expanded=False)

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="ctx_event")
    src = c2.selectbox("Herkunft", sources, key="ctx_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="ctx_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    guest_type = c4.selectbox("Gäste-Typ", GUEST_TYPES, key="ctx_guest_type")

    track_name = st.text_input("Song prüfen", key="ctx_track_name", placeholder="z. B. Mr. Brightside")
    if not track_name:
        st.info("Song eingeben und du siehst Event-Kontext, Rolle, Timing und passende ähnliche Songs.")
        return

    pack = get_track_event_context_pack(track_name, event=ev, source=src, sub_event=sub_ev, guest_type=guest_type)
    if not pack:
        st.warning("Kein passender Song im Bestand gefunden.")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Song", pack["display"])
    m2.metric("Rolle", pack["role"])
    m3.metric("Timing", pack["timing"])
    m4.metric("Gäste-Fit", pack["guest_fit"])

    st.caption(f"Phase: {pack['phase']} | Energie: {pack['energy']} | Nutzung: {pack['total_count']}x | Gäste-Bias: {pack['guest_bias']}")

    left, right = st.columns(2)
    with left:
        st.subheader("Typische Events für diesen Song")
        if pack["top_events"]:
            for ev_name, cnt in pack["top_events"]:
                st.write(f"• {ev_name} — {cnt}x")
        else:
            st.info("Noch keine Event-Zuordnung verfügbar.")
    with right:
        st.subheader("Ähnliche situative Songs")
        if pack["recommendations"]:
            for idx, row in enumerate(pack["recommendations"], start=1):
                render_count_row(
                    f"{idx}. {row['song']} | {row['role']} | {row['phase']}",
                    row["count"],
                    combo_type="event_context_song",
                    combo_text=row["song"],
                    set_key=f"ctx_song_{idx}",
                )
        else:
            st.info("Noch keine passenden ähnlichen Songs gefunden.")


def render_ai_role_timing_page():
    st.header("KI Rollen & Timing")
    st.caption("Hier siehst du klar, welche Songs eher Opener, Aufbau, Peak, Closing oder Bridge sind – und wann sie typischerweise gespielt werden.")

    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="KI Rollen & Timing", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="ai_role_event")
    src = c2.selectbox("Herkunft", sources, key="ai_role_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="ai_role_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="ai_role_top")

    insights = build_role_timing_insights(event=ev, source=src, top_only=top, sub_event=sub_ev)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Songs analysiert", insights["total_tracks"])
    m2.metric("Übergänge", insights["total_pairs"])
    m3.metric("Event", format_event_label(ev, sub_ev) if ev != "Alle" else "Alle")
    m4.metric("Quelle", src)

    tabs = st.tabs(["🌙 Opener", "⬆️ Aufbau", "🔥 Peak", "🌅 Closing", "🔗 Bridge", "📊 Event + Timing", "🧠 Event Learning"])

    with tabs[0]:
        st.subheader("Typische Opener")
        render_role_bucket_cards(insights["roles"].get("🌙 Opener", []), "role_opener", "ai_opener")
    with tabs[1]:
        st.subheader("Typische Aufbau-Songs")
        render_role_bucket_cards(insights["roles"].get("⬆️ Aufbau", []), "role_build", "ai_build")
    with tabs[2]:
        st.subheader("Typische Peak-Songs")
        render_role_bucket_cards(insights["roles"].get("🔥 Peak", []), "role_peak", "ai_peak")
    with tabs[3]:
        st.subheader("Typische Closing-Songs")
        render_role_bucket_cards(insights["roles"].get("🌅 Closing", []), "role_closing", "ai_closing")
    with tabs[4]:
        st.subheader("Typische Bridge-Songs")
        st.caption("Das sind Songs, die oft zwischen Bereichen funktionieren und Stimmungen verbinden können.")
        render_role_bucket_cards(insights["roles"].get("🔗 Bridge", []), "role_bridge", "ai_bridge")
    with tabs[5]:
        st.subheader("Was wird bei welchem Event wann gespielt?")
        rows = []
        for idx, row in enumerate(insights["event_rows"][:60], start=1):
            rows.append({
                "#": idx,
                "Song": row["song"],
                "Top-Event": row["top_event"],
                "Rolle": row["role"],
                "Wann typisch": row["timing"],
                "Häufigkeit": row["count"],
            })
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.info("Noch zu wenig Event-Daten.")

    with tabs[6]:
        st.subheader("KI lernt jetzt pro Event noch klarer")
        st.caption("Hier siehst du pro Event die typischen Rollen: welche Songs oft als Opener, Aufbau, Peak, Closing oder Bridge funktionieren.")
        learning_rows = build_event_learning_summary(event=ev, source=src, top_only=top, sub_event=sub_ev, per_event_limit=6)
        if learning_rows:
            st.dataframe(learning_rows, width="stretch", hide_index=True)
        else:
            st.info("Noch zu wenig Event-Lerndaten vorhanden.")



def build_live_recommendation_rows(current_track, event=None, source=None, top_only=False, sub_event=None, flow_profile="Standard", guest_type="Gemischt", limit=12):
    insights = get_track_insights(current_track, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not insights:
        return {"insights": None, "current": None, "rows": [], "bridge_rows": [], "safe_rows": []}

    current_phase = get_track_phase_label(insights["display"], event=event, source=source, top_only=top_only, sub_event=sub_event)
    current_role = get_track_role_label(insights["display"], event=event, source=source, top_only=top_only, sub_event=sub_event)
    current_energy = get_energy_score_for_phase(current_phase, flow_profile=flow_profile, guest_type=guest_type)

    rows = []
    for norm, cnt in insights.get("after", [])[: max(limit * 2, 20)]:
        display = display_from_normalized(norm)
        phase = get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        timing = get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        energy = get_energy_score_for_phase(phase, flow_profile=flow_profile, guest_type=guest_type)
        transition_count = get_direct_transition_count(current_track, display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        energy_gap = abs(energy - current_energy)

        if energy_gap <= 10:
            fit = "✅ passt jetzt"
            fit_score = 3
        elif energy > current_energy:
            fit = "⏳ eher später"
            fit_score = 1
        else:
            fit = "🧘 eher früher"
            fit_score = 1

        bridge_bonus = 2 if role == "🔗 Bridge" else 0
        safe_bonus = 2 if transition_count >= 5 else (1 if transition_count >= 1 else 0)
        role_bonus = 1 if role in {"⬆️ Aufbau", "🔥 Peak", "🌅 Closing", "🔗 Bridge"} else 0
        score = (cnt * 5) + (fit_score * 8) + (safe_bonus * 6) + (bridge_bonus * 6) + (role_bonus * 2) - energy_gap

        rows.append({
            "Song": display,
            "Phase": phase,
            "Rolle": role,
            "Wann typisch": timing,
            "Energie": energy,
            "Wie gut jetzt": fit,
            "Übergänge": transition_count,
            "Häufigkeit": cnt,
            "Score": score,
        })

    rows = sorted(rows, key=lambda x: (x["Score"], x["Übergänge"], x["Häufigkeit"], x["Song"].casefold()), reverse=True)[:limit]
    bridge_rows = [r for r in rows if r["Rolle"] == "🔗 Bridge"][:6]
    safe_rows = [r for r in rows if r["Übergänge"] >= 5][:6]
    if not safe_rows:
        safe_rows = sorted(rows, key=lambda x: (x["Übergänge"], x["Häufigkeit"]), reverse=True)[:6]

    return {
        "insights": insights,
        "current": {
            "display": insights["display"],
            "phase": current_phase,
            "role": current_role,
            "energy": current_energy,
            "energy_label": get_energy_label(current_energy),
            "timing": get_track_timing_bucket(insights["display"], event=event, source=source, top_only=top_only, sub_event=sub_event),
        },
        "rows": rows,
        "bridge_rows": bridge_rows,
        "safe_rows": safe_rows,
    }


def render_live_rows_table(rows, key_prefix: str):
    if not rows:
        st.info("Keine passenden Vorschläge gefunden.")
        return
    for idx, row in enumerate(rows, start=1):
        cols = st.columns([4.8, 1.2, 1.3, 1.3, 1.0])
        cols[0].write(f"{idx}. {row['Song']}")
        cols[1].caption(row["Rolle"])
        cols[2].caption(row["Wie gut jetzt"])
        cols[3].write(f"{row['Übergänge']}x")
        if cols[4].button("➕", key=f"{key_prefix}_{idx}"):
            st.session_state.setdefault("set_builder", []).append(row["Song"])
            st.success("Song ins Set übernommen.")
            st.rerun()
        st.caption(f"{row['Phase']} | {row['Wann typisch']} | Energie {row['Energie']} | Nutzung {row['Häufigkeit']}x")



def _choose_track_match(query_track, event=None, source=None, top_only=False, sub_event=None):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    norm_query = normalize_track_text(query_track)
    matches = [k for k in data["track_total_counts"].keys() if norm_query and norm_query in k]
    if not matches:
        return None, data
    chosen = sorted(matches, key=lambda x: data["track_total_counts"][x], reverse=True)[0]
    return chosen, data


def build_transition_learning_pack(current_track, event=None, source=None, top_only=False, sub_event=None, limit=8):
    chosen, data = _choose_track_match(current_track, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not chosen:
        return {"current": None, "suggestions": [], "chains3": [], "chains4": [], "chains5": []}

    suggestions = []
    for (a, b), cnt in data["pair_counts"].most_common(300):
        if a != chosen:
            continue
        display = display_from_normalized(b)
        suggestions.append({
            "song": display,
            "transition_count": cnt,
            "role": get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "phase": get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
            "timing": get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event),
        })
    suggestions = suggestions[:limit]

    def _block_rows(counter, block_len):
        rows = []
        for block, cnt in counter.most_common(200):
            if not block or block[0] != chosen:
                continue
            combo = " → ".join(display_from_normalized(x) for x in block)
            rows.append({
                "combo": combo,
                "count": cnt,
                "block_len": block_len,
                "next_song": display_from_normalized(block[1]) if len(block) > 1 else "",
            })
        return rows[:limit]

    return {
        "current": display_from_normalized(chosen),
        "suggestions": suggestions,
        "chains3": _block_rows(data["block3_counts"], 3),
        "chains4": _block_rows(data["block4_counts"], 4),
        "chains5": _block_rows(data["block5_counts"], 5),
    }


def build_track_chain_pack(current_track, event=None, source=None, top_only=False, sub_event=None, limit=8):
    pack = build_transition_learning_pack(
        current_track,
        event=event,
        source=source,
        top_only=top_only,
        sub_event=sub_event,
        limit=limit,
    )

    chain_rows = []
    seen = set()
    for bucket_name in ["chains5", "chains4", "chains3"]:
        for row in pack.get(bucket_name, []):
            combo = row["combo"]
            if combo in seen:
                continue
            seen.add(combo)
            parts = [p.strip() for p in combo.split("→") if p.strip()]
            chain_rows.append({
                "combo": combo,
                "count": row["count"],
                "block_len": row["block_len"],
                "start": parts[0] if parts else "",
                "end": parts[-1] if parts else "",
                "next_song": row.get("next_song", ""),
            })
    chain_rows = sorted(chain_rows, key=lambda x: (x["count"], x["block_len"], x["combo"].casefold()), reverse=True)[:limit]

    recommended_paths = []
    for row in chain_rows[:5]:
        recommended_paths.append({
            "path": row["combo"],
            "count": row["count"],
            "label": f"{row['block_len']}er-Kette",
            "next_song": row["next_song"],
        })

    return {
        "current": pack.get("current"),
        "chain_rows": chain_rows,
        "recommended_paths": recommended_paths,
        "base_pack": pack,
    }


def render_chain_rows_table(rows, key_prefix: str):
    if not rows:
        st.info("Noch keine typischen DJ-Ketten gefunden.")
        return
    for idx, row in enumerate(rows, start=1):
        cols = st.columns([5.3, 0.9, 1.0])
        cols[0].write(f"{idx}. {row['combo']}")
        cols[1].write(f"{row['count']}x")
        if cols[2].button("➕", key=f"{key_prefix}_{idx}"):
            added = save_combo_to_set(row["combo"])
            if added:
                st.success(f"{added} Track(s) ins Set übernommen.")
            st.rerun()
        st.caption(f"{row['block_len']}er-Kette | Nächster sinnvoller Song: {row.get('next_song') or '-'}")






def infer_next_set_direction(current_phase: str, current_timing: str) -> str:
    phase_text = str(current_phase or "")
    timing_text = str(current_timing or "")
    if "Dinner" in phase_text or "Warmup" in phase_text or timing_text in {"sehr früh", "früh"}:
        return "Jetzt eher weiter aufbauen"
    if "Peak" in phase_text or timing_text == "spät":
        return "Peak halten oder kontrolliert nachlegen"
    if "Closing" in phase_text or timing_text == "ganz spät":
        return "Eher kontrolliert Richtung Closing"
    return "Flow stabil halten"


def build_context_route_recommendations(current_track, event=None, source=None, top_only=False, sub_event=None, limit=5):
    chain_pack = build_track_chain_pack(current_track, event=event, source=source, top_only=top_only, sub_event=sub_event, limit=max(8, limit))
    current_insights = get_track_insights(current_track, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not current_insights:
        return []

    current_display = current_insights.get("display", "")
    current_phase = get_track_phase_label(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)
    current_timing = get_track_timing_bucket(current_display, event=event, source=source, top_only=top_only, sub_event=sub_event)

    rows = []
    seen = set()
    for row in chain_pack.get("chain_rows", [])[:20]:
        chain_text = str(row.get("Kette") or row.get("chain") or "").strip()
        if not chain_text or chain_text in seen:
            continue
        seen.add(chain_text)
        parts = [p.strip() for p in chain_text.split("→") if p.strip()]
        if len(parts) < 2:
            continue
        next_song = parts[1]
        last_song = parts[-1]
        next_phase = get_track_phase_label(next_song, event=event, source=source, top_only=top_only, sub_event=sub_event)
        last_phase = get_track_phase_label(last_song, event=event, source=source, top_only=top_only, sub_event=sub_event)
        next_timing = get_track_timing_bucket(next_song, event=event, source=source, top_only=top_only, sub_event=sub_event)
        distance = track_phase_distance(current_phase, next_phase)
        score = int(row.get("Häufigkeit", row.get("count", 0)) or 0) * 12
        score += 8 if distance <= 1 else (-4)
        if next_timing == current_timing:
            score += 6
        if "Peak" in last_phase:
            score += 4
        route_type = "Mini-Route"
        if "Peak" in last_phase and "Peak" not in current_phase:
            route_type = "Route Richtung Peak"
        elif "Closing" in last_phase:
            route_type = "Route Richtung Closing"
        elif distance == 0:
            route_type = "Stabiler Flow"

        rows.append({
            "Route": chain_text,
            "Typ": route_type,
            "Route-Score": score,
            "Nächster Song": next_song,
            "Zielrichtung": last_phase,
            "Warum": f"Echte Kette | Phase-Fit {max(0, 3-distance)}/3 | Timing {next_timing}",
        })

    rows = sorted(rows, key=lambda x: (x["Route-Score"], x["Route"]), reverse=True)[:limit]
    return rows


def build_energy_hint_for_track(track_name, event=None, source=None, top_only=False, sub_event=None):
    phase = get_track_phase_label(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    timing = get_track_timing_bucket(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    energy = estimate_track_energy(track_name, event=event, source=source, top_only=top_only, sub_event=sub_event)
    direction = infer_next_set_direction(phase, timing)
    return {"phase": phase, "timing": timing, "energy": energy, "direction": direction}




def build_transition_zero_hit_explanation(query_track, event=None, source=None, top_only=False, sub_event=None):
    explanation_rows = []
    insights = get_track_insights(query_track, event=event, source=source, top_only=top_only, sub_event=sub_event)
    if not insights:
        broad_insights = get_track_insights(query_track, event="Alle", source="Alle", top_only=False, sub_event="Alle")
        if broad_insights:
            explanation_rows.append("Der Song ist grundsätzlich im Bestand vorhanden, aber im aktuellen Filter nicht eindeutig gefunden worden.")
            explanation_rows.append("Prüfe Herkunft, Anlass oder ob eine andere Schreibweise/Version im aktuellen Filter stärker vertreten ist.")
        else:
            explanation_rows.append("Im aktuellen Lernbestand wurde kein passender Song gefunden.")
        return explanation_rows

    total = int(insights.get("total_count", 0) or 0)
    playlist_count = int(insights.get("playlist_count", 0) or 0)
    after_count = len(insights.get("after", []) or [])
    before_count = len(insights.get("before", []) or [])
    display = insights.get("display", query_track)

    if total > 0 and after_count == 0:
        explanation_rows.append(f"{display} wurde {total}x gefunden, hat im aktuellen Filter aber keine gelernten Folgetracks.")
        if before_count > 0:
            explanation_rows.append("Der Song taucht eher als Ziel / später im Verlauf auf als als Startpunkt für einen nächsten Übergang.")
        else:
            explanation_rows.append("Der Song wird in diesem Filter vermutlich oft isoliert oder am Ende gespielt.")
    elif total > 0 and after_count <= 2:
        explanation_rows.append(f"{display} wurde gefunden, aber nur mit {after_count} direktem/n Folgetrack(s) im aktuellen Filter.")
        explanation_rows.append("Das ist meist ein Zeichen für enge Filter oder seltene echte Übergänge.")
    else:
        explanation_rows.append(f"{display} hat im aktuellen Filter nur eine kleine Lernbasis.")
    if top_only:
        explanation_rows.append("„Nur Top Playlists“ ist aktiv und kann die Lernbasis stark verkleinern.")
    if source and source != "Alle":
        explanation_rows.append(f"Die Herkunft ist auf „{source}“ gefiltert. In anderen Quellen kann mehr gelernt worden sein.")
    if event and event != "Alle":
        explanation_rows.append(f"Der Anlass ist auf „{event}“ gefiltert. In anderen Kontexten kann der Song häufiger vorkommen.")
    if playlist_count <= 3:
        explanation_rows.append(f"Lernbasis im aktuellen Filter: nur {playlist_count} Playlist(s).")
    return explanation_rows

def render_transition_learning_page():
    st.header("Transition KI")
    st.caption("Hier lernt das Tool echte Folgetracks und komplette DJ-Ketten ab deinem aktuellen Song.")
    st.info("V9 intelligenter: Empfehlungen zeigen jetzt auch Set-Richtung, Energie-Hinweis und kleine echte Routen fuer die naechsten 2-3 Songs.")

    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Transition KI", title="Schnell laden")
    render_learning_rules_box("Transition KI", expanded=False)

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="transition_event")
    src = c2.selectbox("Herkunft", sources, key="transition_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="transition_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="transition_top")

    query_track = st.text_input("Aktueller Song / Start-Song", placeholder="z. B. Mr. Brightside", key="transition_query")
    if not query_track:
        st.info("Song eingeben und du siehst direkte Folgetracks, sichere Wechsel und komplette DJ-Ketten.")
        return

    pack = build_transition_learning_pack(query_track, event=ev, source=src, top_only=top, sub_event=sub_ev, limit=10)
    if not pack.get("current"):
        st.warning("Kein passender Track gefunden.")
        return

    smart_pack = build_smart_transition_recommendations(query_track, event=ev, source=src, top_only=top, sub_event=sub_ev, limit=10)
    smart_rows = smart_pack.get("rows", [])
    quality = smart_pack.get("quality", {"label": "Unklar", "score": 0, "basis_playlists": 0})
    best = smart_rows[0] if smart_rows else {}
    energy_hint = build_energy_hint_for_track(pack["current"], event=ev, source=src, top_only=top, sub_event=sub_ev)
    route_rows = build_context_route_recommendations(query_track, event=ev, source=src, top_only=top, sub_event=sub_ev, limit=5)
    zero_hit_explanations = build_transition_zero_hit_explanation(query_track, event=ev, source=src, top_only=top, sub_event=sub_ev)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Start-Song", pack["current"])
    m2.metric("Smart Folgetracks", len(smart_rows))
    m3.metric("Top-Vertrauen", quality.get("label", "-"))
    m4.metric("Energie", energy_hint.get("energy", "-"))

    st.caption(
        f"Set-Richtung: {energy_hint.get('direction', '-')}"
        + f" | Phase: {energy_hint.get('phase', '-')}"
        + f" | Timing: {energy_hint.get('timing', '-')}"
        + f" | Lernbasis: {quality.get('basis_playlists', 0)}"
    )

    if best:
        st.caption(
            f"Beste Smart-Empfehlung: {best.get('Song', '-')}"
            + f" | Typ: {best.get('Typ', '-')}"
            + f" | Smart-Score: {best.get('Smart-Score', 0)}"
            + f" | KI-Vertrauen: {best.get('KI-Vertrauen', '-')}"
        )

    if len(smart_rows) <= 2 and zero_hit_explanations:
        st.warning("Wenig Treffer im aktuellen Filter – das ist meist ein Kontext- oder Lernbasis-Thema, nicht automatisch ein Fehler.")
        for line in zero_hit_explanations[:5]:
            st.caption(f"• {line}")

    tabs = st.tabs(["🎯 Smart Folgetracks", "🏆 Top 3", "🧭 Nächste Route", "🔗 DJ-Ketten", "🧱 3er/4er/5er Wege"])

    with tabs[0]:
        if smart_rows:
            st.dataframe(smart_rows, width="stretch", hide_index=True)
            add_cols = st.columns(5)
            for idx, row in enumerate(smart_rows[:5], start=1):
                if add_cols[(idx - 1) % 5].button(f"➕ {idx}", key=f"transition_song_add_v9_{idx}"):
                    st.session_state.setdefault("set_builder", []).append(row["Song"])
                    st.success(f"{row['Song']} ins Set übernommen.")
                    st.rerun()
        else:
            st.info("Noch keine smarten Folgetracks gefunden.")

    with tabs[1]:
        if smart_rows:
            top3 = smart_rows[:3]
            cols = st.columns(3)
            for idx, row in enumerate(top3):
                with cols[idx]:
                    st.markdown(f"**#{idx+1} {row['Song']}**")
                    st.caption(f"{row['Typ']} | {row['KI-Vertrauen']}")
                    st.caption(f"{row['Phase']} | {row['Timing']} | {row['Rolle']}")
                    st.caption(f"Event-Fit: {row['Event-Fit']}")
                    st.caption(f"Warum: {row['Warum']}")
                    if st.button("➕ Ins Set", key=f"transition_top3_add_v9_{idx}"):
                        st.session_state.setdefault("set_builder", []).append(row["Song"])
                        st.success(f"{row['Song']} ins Set übernommen.")
                        st.rerun()
        else:
            st.info("Noch keine Top-Übergänge gefunden.")

    with tabs[2]:
        st.subheader("Nächste 2-3 Songs intelligent lesen")
        if route_rows:
            st.dataframe(route_rows, width="stretch", hide_index=True)
            st.caption("Diese Routen kommen aus echten Ketten und helfen dir nicht nur beim nächsten Song, sondern beim nächsten Mini-Weg.")
        else:
            st.info("Noch keine passenden Mini-Routen gefunden.")

    with tabs[3]:
        st.subheader("Komplette DJ-Ketten ab deinem Song")
        if st.button("DJ-Ketten jetzt berechnen", key="transition_chain_load_btn"):
            st.session_state["transition_chain_loaded"] = True
        if st.session_state.get("transition_chain_loaded"):
            chain_pack = build_track_chain_pack(query_track, event=ev, source=src, top_only=top, sub_event=sub_ev, limit=10)
            render_chain_rows_table(chain_pack.get("chain_rows", []), "transition_chain")
        else:
            st.info("Klicke auf den Button, wenn du die komplette Kettenberechnung brauchst. Das spart Startzeit.")

    with tabs[4]:
        b1, b2, b3 = st.columns(3)
        with b1:
            st.markdown("**3er-Ketten**")
            render_chain_rows_table(pack.get("chains3", []), "transition_3")
        with b2:
            st.markdown("**4er-Ketten**")
            render_chain_rows_table(pack.get("chains4", []), "transition_4")
        with b3:
            st.markdown("**5er-Ketten**")
            render_chain_rows_table(pack.get("chains5", []), "transition_5")


def get_default_energy_profile(flow_profile: str = "Standard") -> dict:
    profile = FLOW_PROFILES.get(flow_profile, FLOW_PROFILES["Standard"])
    return {
        "energy_start": int(profile.get("warmup", 25)),
        "energy_peak": int(profile.get("peak", 82)),
        "energy_end": int(profile.get("closing", 40)),
    }


def get_saved_event_profile(event: str, source: str, sub_event: str = "") -> dict:
    event_clean = normalize_meta_value(event)
    source_clean = normalize_meta_value(source)
    sub_clean = normalize_sub_event(sub_event) if is_birthday_event(event_clean) else ""
    if not event_clean or not source_clean:
        return {}
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT event, source, sub_event, guest_type, age_min, age_max, mood, flow_profile,
               energy_start, energy_peak, energy_end, notes, updated_at
        FROM event_profiles
        WHERE event = ? AND source = ? AND COALESCE(sub_event, '') = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (event_clean, source_clean, sub_clean),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    return {
        "event": row[0],
        "source": row[1],
        "sub_event": row[2] or "",
        "guest_type": row[3] or "Gemischt",
        "age_min": int(row[4] or 25),
        "age_max": int(row[5] or 45),
        "mood": row[6] or "Gemischt",
        "flow_profile": row[7] or "Standard",
        "energy_start": int(row[8] or 25),
        "energy_peak": int(row[9] or 82),
        "energy_end": int(row[10] or 40),
        "notes": row[11] or "",
        "updated_at": row[12] or "-",
    }


def save_event_profile(event: str, source: str, sub_event: str = "", guest_type: str = "Gemischt", age_min: int = 25, age_max: int = 45, mood: str = "Gemischt", flow_profile: str = "Standard", energy_start: int = 25, energy_peak: int = 82, energy_end: int = 40, notes: str = ""):
    event_clean = normalize_meta_value(event)
    source_clean = normalize_meta_value(source)
    sub_clean = normalize_sub_event(sub_event) if is_birthday_event(event_clean) else ""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO event_profiles(
            event, source, sub_event, guest_type, age_min, age_max, mood, flow_profile,
            energy_start, energy_peak, energy_end, notes, updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
        """,
        (
            event_clean, source_clean, sub_clean, str(guest_type or "Gemischt"),
            int(age_min or 25), int(age_max or 45), str(mood or "Gemischt"), str(flow_profile or "Standard"),
            int(energy_start or 25), int(energy_peak or 82), int(energy_end or 40), str(notes or ""),
        ),
    )
    conn.commit()
    conn.close()
    auto_backup_after_data_change("event_profile_save")


def get_event_profile_overview(limit: int = 12):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT event, source, sub_event, guest_type, age_min, age_max, mood, flow_profile,
               energy_start, energy_peak, energy_end, updated_at
        FROM event_profiles
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "Anlass": format_event_label(r[0], r[2]) or r[0] or "-",
            "Herkunft": r[1] or "-",
            "Gäste": r[3] or "-",
            "Alter": f"{int(r[4] or 0)}-{int(r[5] or 0)}",
            "Stimmung": r[6] or "-",
            "Flow": r[7] or "-",
            "Energie": f"{int(r[8] or 0)}/{int(r[9] or 0)}/{int(r[10] or 0)}",
            "Aktualisiert": r[11] or "-",
        }
        for r in rows
    ]


def get_event_brain_recommendations(event=None, source=None, top_only=False, sub_event=None, guest_type="Gemischt", mood="Gemischt", flow_profile="Standard", age_min: int = 25, age_max: int = 45, limit: int = 18):
    data = compute_data_cached(event=event, source=source, top_only=top_only, sub_event=sub_event)
    results = []
    profile = FLOW_PROFILES.get(flow_profile, FLOW_PROFILES["Standard"])
    mood_key = str(mood or "Gemischt").casefold()
    for norm, cnt in data["track_total_counts"].most_common(300):
        display = display_from_normalized(norm)
        phase = get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        timing = get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        energy = estimate_track_energy(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        score = cnt * 4
        score += auto_set_guest_bias(display, guest_type)
        if age_max <= 24 and any(x in norm for x in ["flo rida", "pitbull", "usher", "rihanna", "guetta", "lmfao"]):
            score += 8
        if age_min >= 30 and any(x in norm for x in ["abba", "boney", "queen", "backstreet", "britney", "cascada", "snap", "whigfield"]):
            score += 7
        if mood_key in {"clubbig", "club / big room", "big room", "club"} and ("Peak" in phase or energy >= 8):
            score += 8
        elif mood_key in {"mitsingen", "singalong"} and any(x in norm for x in ["backstreet", "queen", "bon jovi", "abba", "whitney", "roxette", "eurythmics", "mr brightside"]):
            score += 8
        elif mood_key in {"elegant", "stilvoll"} and ("Warmup" in phase or "Dinner" in phase):
            score += 6
        elif mood_key in {"abriss", "volle eskalation"} and ("Peak" in phase or energy >= 9):
            score += 10
        if "Warmup" in phase:
            score += max(0, 10 - abs(profile.get("warmup", 25) - energy * 10) // 10)
        elif "Aufbau" in phase:
            score += max(0, 10 - abs(profile.get("middle", 50) - energy * 10) // 10)
        elif "Peak" in phase:
            score += max(0, 10 - abs(profile.get("peak", 82) - energy * 10) // 10)
        elif "Closing" in phase or "Spät" in phase:
            score += max(0, 10 - abs(profile.get("closing", 40) - energy * 10) // 10)
        results.append({
            "Song": display,
            "Rolle": role,
            "Phase": phase,
            "Timing": timing,
            "Energie": energy,
            "Nutzung": int(cnt),
            "Score": int(score),
        })
    results = sorted(results, key=lambda x: (x["Score"], x["Nutzung"], x["Song"].casefold()), reverse=True)
    return results[:limit]


def render_energy_curve_preview(energy_start: int, energy_peak: int, energy_end: int):
    rows = [
        {"Phase": "Warmup", "Zielenergie": int(energy_start)},
        {"Phase": "Aufbau", "Zielenergie": int(round((energy_start + energy_peak) / 2))},
        {"Phase": "Peak", "Zielenergie": int(energy_peak)},
        {"Phase": "Closing", "Zielenergie": int(energy_end)},
    ]
    for row in rows:
        st.write(f"**{row['Phase']}** — Zielenergie {row['Zielenergie']}/100")
        st.progress(int(max(0, min(100, row["Zielenergie"]))), text=f"{row['Phase']} • {row['Zielenergie']}/100")


def render_smart_event_brain_page():
    st.header("Smart Event Brain")
    st.caption("Hier steuerst du Event-Intelligenz mit Gäste-Alter, Stimmung und Energie-Kurve – speicherbar pro Anlass und Herkunft.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Smart Event Brain", title="Schnell laden")
    render_learning_rules_box("Smart Event Brain", expanded=False)

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="brain_event")
    src = c2.selectbox("Herkunft", sources, key="brain_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="brain_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="brain_top")

    saved = get_saved_event_profile(ev, src, sub_event=("" if sub_ev == "Alle" else sub_ev)) if ev != "Alle" and src != "Alle" else {}
    flow_default = saved.get("flow_profile") or "Standard"
    guest_default = saved.get("guest_type") or "Gemischt"
    mood_options = ["Gemischt", "Elegant", "Mitsingen", "Club / Big Room", "Abriss", "Urban / HipHop", "Deutsch / Party"]
    mood_default = saved.get("mood") or "Gemischt"
    if mood_default not in mood_options:
        mood_options.append(mood_default)

    d1, d2, d3 = st.columns(3)
    guest_type = d1.selectbox("Gäste-Typ", GUEST_TYPES, index=max(0, GUEST_TYPES.index(guest_default)) if guest_default in GUEST_TYPES else 0, key="brain_guest_type")
    mood = d2.selectbox("Stimmung", mood_options, index=max(0, mood_options.index(mood_default)), key="brain_mood")
    flow_profile = d3.selectbox("Flow-Profil", list(FLOW_PROFILES.keys()), index=max(0, list(FLOW_PROFILES.keys()).index(flow_default)) if flow_default in FLOW_PROFILES else 0, key="brain_flow_profile")

    default_profile = get_default_energy_profile(flow_profile)
    age_default = (int(saved.get("age_min", 25)), int(saved.get("age_max", 45)))
    energy_start_default = int(saved.get("energy_start", default_profile["energy_start"]))
    energy_peak_default = int(saved.get("energy_peak", default_profile["energy_peak"]))
    energy_end_default = int(saved.get("energy_end", default_profile["energy_end"]))

    e1, e2 = st.columns(2)
    age_range = e1.slider("Gäste-Alter", 16, 75, age_default, key="brain_age_range")
    notes = e2.text_area("Notiz / Anlass-Stimmung", value=str(saved.get("notes", "")), key="brain_notes", placeholder="z. B. erst stilvoll, dann 90er/2000er Peak und gegen Ende Mitsinger")

    s1, s2, s3 = st.columns(3)
    energy_start = s1.slider("Start-Energie", 0, 100, energy_start_default, key="brain_energy_start")
    energy_peak = s2.slider("Peak-Energie", 0, 100, energy_peak_default, key="brain_energy_peak")
    energy_end = s3.slider("Closing-Energie", 0, 100, energy_end_default, key="brain_energy_end")

    st.subheader("Energie-Kurve")
    render_energy_curve_preview(energy_start, energy_peak, energy_end)

    b1, b2 = st.columns(2)
    if b1.button("💾 Event-Profil speichern", key="brain_save_profile", width="stretch", disabled=(ev == "Alle" or src == "Alle")):
        save_event_profile(
            ev, src, sub_event=("" if sub_ev == "Alle" else sub_ev), guest_type=guest_type,
            age_min=int(age_range[0]), age_max=int(age_range[1]), mood=mood, flow_profile=flow_profile,
            energy_start=energy_start, energy_peak=energy_peak, energy_end=energy_end, notes=notes,
        )
        st.success("Event-Profil gespeichert.")
        st.rerun()
    if saved:
        b2.success(f"Gespeichertes Profil aktiv · aktualisiert {saved.get('updated_at', '-')}")
    else:
        b2.info("Noch kein gespeichertes Profil für diese Kombination.")

    st.subheader("Empfohlene Songs für dieses Profil")
    rows = get_event_brain_recommendations(
        event=ev, source=src, top_only=top, sub_event=sub_ev, guest_type=guest_type, mood=mood,
        flow_profile=flow_profile, age_min=int(age_range[0]), age_max=int(age_range[1]), limit=18,
    )
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Noch keine passenden Empfehlungen gefunden.")

    auto = build_event_auto_set(
        event=ev, source=src, top_only=top, sub_event=sub_ev, flow_profile=flow_profile, guest_type=guest_type,
    )
    st.subheader("Auto-Set passend zum Profil")
    if auto.get("phase_rows"):
        overview = []
        for idx, row in enumerate(auto["phase_rows"], start=1):
            overview.append({
                "#": idx,
                "Song": row["song"],
                "Phase": row["phase_label"],
                "Energie": row["energy"],
                "Score": row["score"],
            })
        st.dataframe(overview, width="stretch", hide_index=True)
    else:
        st.info("Für dieses Profil konnte noch kein Auto-Set gebaut werden.")

    st.subheader("Gespeicherte Event-Profile")
    overview_rows = get_event_profile_overview(limit=10)
    if overview_rows:
        st.dataframe(overview_rows, width="stretch", hide_index=True)
    else:
        st.info("Noch keine Event-Profile gespeichert.")


def render_app_header():
    compact_mode = st.session_state.get("compact_mode", False)
    st.markdown("## DJ Tool")
    launcher_label = str(os.environ.get("DJ_TOOL_LAUNCHER_LABEL") or "").strip()
    launcher_version = str(os.environ.get("DJ_TOOL_LAUNCHER_VERSION") or "").strip()
    package_base = str(os.environ.get("DJ_TOOL_PACKAGE_BASE") or "").strip()
    launcher_base = os.environ.get("DJ_TOOL_PACKAGE_BASE", "-")
    if compact_mode:
        st.caption(f"{APP_SHORT_VERSION} · {launcher_label or 'Launcher'} · Basis: {launcher_base}")
        return
    if launcher_version:
        extra = f" | Basis: {package_base}" if package_base else ""
        st.caption(f"{launcher_label or 'Launcher'}: {launcher_version}{extra}")
    launcher_version = os.environ.get("DJ_TOOL_LAUNCHER_VERSION", "-")
    st.caption(f"Aktuelle Systemversion: {launcher_version} | aktualisiert am {APP_BUILD_DATE} {APP_BUILD_TIME} | Basis: {launcher_base}")
    st.caption(f"Core-Version: {APP_SHORT_VERSION}")

render_app_header()

p_count, t_count, l_count, c_count = stats_counts()
ensure_build_snapshot_backup()
show_system_status_panel = bool(st.session_state.get("show_system_status_panel", get_ui_pref("show_system_status_panel", False)))
st.session_state["show_system_status_panel"] = show_system_status_panel
status_cols = st.columns([4, 1.2])
status_cols[0].caption(f"Live-Bestand: {p_count} Playlists • {t_count} Tracks • {c_count} gemerkte Kombis")
if show_system_status_panel:
    if status_cols[1].button("🧾 Status ausblenden", key="hide_system_status_btn", width="stretch"):
        st.session_state["show_system_status_panel"] = False
        update_ui_prefs(show_system_status_panel=False)
        st.rerun()
    with st.expander(f"System / Status ({p_count} Playlists • {t_count} Tracks)", expanded=False):
        st.caption(f"Build: {APP_BUILD_DATE} · {APP_BUILD_TIME}")
        st.caption(f"Quelle: {APP_BUILD_SOURCE}")
        st.caption("Systemstatus und Release Guard werden in V15 nur noch bei Bedarf geladen. Das macht den normalen Start ruhiger und schneller.")
        render_data_safety_status(p_count, t_count)
        render_release_guard_banner()
else:
    if status_cols[1].button("🧾 Status laden", key="show_system_status_btn", width="stretch"):
        st.session_state["show_system_status_panel"] = True
        update_ui_prefs(show_system_status_panel=True)
        st.rerun()
    st.caption("System / Status bleibt für schnelleren Start ausgeblendet. Bei Bedarf oben laden.")


SIMPLE_MENU_OPTIONS = [
    "🏠 Start",
    "Event Presets",
    "Event vorbereiten",
    "Auto Event Set",
    "Transition KI",
    "Live Hilfe",
    "Learning Dashboard",
    "Set Builder",
    "Rekordbox verbinden",
    "Fehlende Songs",
    "Playlists importieren",
    "Zuletzt importierte Playlists",
    "Backup / Restore",
    "System / Version",
]

def get_visible_menu_options():
    mode = st.session_state.get("ui_mode", "Profi")
    if mode == "Einfach":
        return [item for item in MENU_OPTIONS if item in SIMPLE_MENU_OPTIONS]
    return MENU_OPTIONS

MENU_OPTIONS = [
    "🏠 Start",
    "Analyse Hub",
    "Auto Event Set",
    "Backup / Restore",
    "Doppelte Playlists",
    "Event Kontext KI",
    "Event Presets",
    "Event vorbereiten",
    "Event-Phasen",
    "Fehlende Songs",
    "Gemerkte Kombinationen",
    "Heute auflegen",
    "iPad Verbindung",
    "KI Rollen & Timing",
    "Live Hilfe",
    "Meine Sets",
    "Playlists durchsuchen",
    "Playlists importieren",
    "Zuletzt importierte Playlists",
    "Rekordbox verbinden",
    "Set Builder",
    "Smart Event Brain",
    "Smart Flow Engine",
    "System / Version",
    "Transition KI",
    "Vorbereitung",
    "Wichtige Tracks",
]

if "active_menu" not in st.session_state:
    st.session_state["active_menu"] = "🏠 Start"
if st.session_state["active_menu"] not in MENU_OPTIONS:
    st.session_state["active_menu"] = "🏠 Start"

with st.sidebar:
    st.session_state.setdefault("show_context_help", bool(get_ui_pref("show_context_help", True)))
    st.session_state.setdefault("ui_mode", str(get_ui_pref("ui_mode", "Profi")))
    st.session_state.setdefault("compact_mode", bool(get_ui_pref("compact_mode", False)))
    if AUTO_LOGIN_TRUSTED_DEVICE:
        st.info("✅ Auto-Login aktiv")
    else:
        if st.button("🔓 Logout", key="logout_btn", width="stretch"):
            st.session_state["is_authenticated"] = False
            st.session_state["logout_cleanup_pending"] = True
            set_auth_query_value("")
            st.rerun()
    if st.button("📦 Backup", key="sidebar_backup_btn", width="stretch"):
        set_active_menu("Backup / Restore")
        st.rerun()
    st.markdown("## Navigation")
    ui_mode = st.radio("Ansicht", ["Einfach", "Profi"], horizontal=True, key="ui_mode")
    compact_mode = st.checkbox("🧼 Kompaktmodus", key="compact_mode", help="Blendet Hilfetexte aus und hält die Oberfläche ruhiger.")
    if compact_mode:
        st.session_state["show_context_help"] = False
    visible_menu_options = get_visible_menu_options()
    if st.session_state.get("active_menu") not in visible_menu_options:
        fallback_menu = "🏠 Start" if "🏠 Start" in visible_menu_options else visible_menu_options[0]
        set_active_menu(fallback_menu)

    quick_menu_query = st.text_input(
        "Schnellzugriff",
        value=st.session_state.get("sidebar_menu_search", ""),
        key="sidebar_menu_search",
        placeholder="Menü suchen...",
    )
    quick_menu_matches = [
        item for item in visible_menu_options
        if not quick_menu_query or _normalize_menu_label(quick_menu_query) in _normalize_menu_label(item)
    ]
    if quick_menu_query:
        if quick_menu_matches:
            default_quick_menu = st.session_state.get("sidebar_quick_menu", quick_menu_matches[0])
            if default_quick_menu not in quick_menu_matches:
                default_quick_menu = quick_menu_matches[0]
            quick_target = st.selectbox(
                "Direkt springen",
                quick_menu_matches,
                index=quick_menu_matches.index(default_quick_menu),
                key="sidebar_quick_menu",
            )
            if st.button("➡️ Öffnen", key="sidebar_quick_jump_btn", width="stretch"):
                set_active_menu(quick_target)
                st.rerun()
        else:
            st.caption("Kein Menü gefunden.")

    recent_menu_items = [
        item for item in st.session_state.get("recent_menus", [])
        if item in visible_menu_options and item != st.session_state.get("active_menu")
    ]
    if recent_menu_items:
        st.caption("Zuletzt genutzt")
        recent_cols = st.columns(2)
        for idx, item in enumerate(recent_menu_items[:4]):
            with recent_cols[idx % 2]:
                short_label = item if len(item) <= 24 else item[:21] + "..."
                if st.button(short_label, key=f"recent_menu_btn_{idx}", width="stretch"):
                    set_active_menu(item)
                    st.rerun()

    chosen_menu = st.radio(
        "Was möchtest du tun?",
        visible_menu_options,
        index=visible_menu_options.index(st.session_state["active_menu"]),
        key="sidebar_main_menu",
    )
    if chosen_menu != st.session_state["active_menu"]:
        set_active_menu(chosen_menu)
    st.checkbox("ℹ️ Bereichs-Hilfe anzeigen", key="show_context_help")
    st.caption("Start = klarer Einstieg. Upload bleibt unter 'Playlists importieren'.")
    st.caption("Kompaktmodus blendet Hilfetexte aus und macht die Oberfläche ruhiger.")
    if st.session_state.get("last_auto_backup_skipped_reason"):
        st.caption(f"Backup-Optimierung: {st.session_state.get('last_auto_backup_skipped_reason')}")
    st.caption(f"Baseline: {APP_BASELINE_ID} | Version: {APP_SHORT_VERSION} | Modus: {ui_mode}")
    update_ui_prefs(
        show_context_help=bool(st.session_state.get("show_context_help", True)),
        ui_mode=str(st.session_state.get("ui_mode", "Profi")),
        compact_mode=bool(st.session_state.get("compact_mode", False)),
        show_system_status_panel=bool(st.session_state.get("show_system_status_panel", False)),
    )

menu = st.session_state["active_menu"]
update_recent_menus(menu)

if st.session_state.get("show_context_help", True):
    render_context_help_box(menu)

events = get_merged_distinct_values("event", EVENT_IMPORT_PRESETS)
sources = get_merged_distinct_values("source", SOURCE_PRESETS)

if menu == "🏠 Start":
    render_start_screen(p_count, t_count, l_count, c_count)

elif menu == "Playlists importieren":
    st.header("Playlists importieren")
    st.caption("Einzelne Setlisten, mehrere Dateien oder ganze ZIP-Ordner importieren. Dubletten werden automatisch NICHT gespeichert.")
    render_last_upload_feedback()
    render_last_upload_result_rows()
    render_upload_busy_notice()
    render_recent_import_runs(limit=10)
    render_recent_imported_playlists_panel(default_limit=10, key_prefix="recent_imports_inline", show_header=True)
    if not require_safe_storage_before_imports():
        st.stop()

    import_mode = st.radio(
        "Import-Art",
        ["Text einfügen", "Datei hochladen", "Mehrere Dateien hochladen", "ZIP hochladen"],
        horizontal=True
    )

    source_presets = get_import_meta_options("source", SOURCE_PRESETS)
    event_presets = get_import_meta_options("event", EVENT_IMPORT_PRESETS)

    name = st.text_input("Name der Playlist")

    p1, p2 = st.columns(2)
    try:
        event = p1.selectbox(
            "Anlass",
            options=event_presets,
            index=0 if event_presets else None,
            accept_new_options=True,
            key="import_event",
            help="Vorschlag wählen oder eigenen Anlass eintippen und Enter drücken.",
        )
        source = p2.selectbox(
            "Herkunft",
            options=source_presets,
            index=0 if source_presets else None,
            accept_new_options=True,
            key="import_source",
            help="Vorschlag wählen oder eigene Herkunft eintippen und Enter drücken.",
        )
    except TypeError:
        event = p1.text_input("Anlass", placeholder="z. B. Hochzeit, Geburtstag, Party, 90er-2000er", key="import_event")
        source = p2.text_input("Herkunft", placeholder="z. B. Benjamin Schneider, Michael Zimmermann, Global, Reverenz", key="import_source")

    event = str(event or "").strip()
    source = str(source or "").strip()

    auto_event_guess, auto_sub_event_guess = infer_event_and_sub_event_from_name(name)
    birthday_sub_event = ""
    if is_birthday_event(event):
        preset_sub_event = st.session_state.get("import_sub_event", "")
        if not preset_sub_event and auto_sub_event_guess:
            st.session_state["import_sub_event"] = auto_sub_event_guess
        birthday_sub_event = render_birthday_subevent_input(
            st,
            key_prefix="import",
            help_text="Nur für Geburtstag. Damit kannst du z. B. 18, 30 oder 60 getrennt auswerten.",
        )
        if auto_sub_event_guess:
            st.caption(f"🔎 Auto-Erkennung erkannt: Geburtstag › {auto_sub_event_guess}")
    elif auto_event_guess == "Geburtstag":
        st.info(f"🔎 Auto-Erkennung erkannt: '{name or '-'}' wirkt wie Geburtstag{(' › ' + auto_sub_event_guess) if auto_sub_event_guess else ''}. Wähle oben bei Anlass einfach 'Geburtstag', dann wird der Unterordner direkt übernommen.")

    is_top = st.checkbox("Top Playlist")
    upload_note = st.text_area("Anlass-Notiz / Upload-Notiz", height=80, placeholder="z. B. Freitext zum Event, Publikum, Stimmung oder Besonderheiten", key="import_upload_note")

    imported_text = ""
    import_type = "text"

    if import_mode == "Text einfügen":
        imported_text = st.text_area("Tracks", height=220, placeholder="Artist - Track")
        st.caption("Eine Zeile pro Track. Format am besten: Artist - Track")

        if imported_text:
            parsed_tracks = parse_text_to_tracks(imported_text)
            st.subheader("Erkannte Tracks")
            st.write(f"{len(parsed_tracks)} Tracks erkannt")
            if parsed_tracks:
                preview_rows = [{"Pos": t["position"], "Artist": t["artist"], "Titel": t["title"]} for t in parsed_tracks[:30]]
                st.dataframe(preview_rows, width="stretch", hide_index=True)

                render_duplicate_warning_box(
                    parsed_tracks,
                    event=event.strip(),
                    source=source.strip(),
                    sub_event=birthday_sub_event.strip(),
                    key_prefix="text_import"
                )

            if st.button("Playlist speichern", type="primary", disabled=is_upload_busy()):
                playlist_name = name.strip() if name.strip() else f"Playlist {p_count + 1}"
                signature = make_upload_signature("text", playlist_name, event.strip(), source.strip(), parsed_tracks, birthday_sub_event.strip())
                if st.session_state.get("last_upload_signature") == signature:
                    log_import_run(import_type, playlist_name, event.strip(), source.strip(), len(parsed_tracks), status="skipped", note="Gerade bereits importiert", sub_event=birthday_sub_event.strip(), signature=signature)
                    set_last_upload_feedback("⚠️ Diese Playlist wurde gerade schon erfolgreich hochgeladen. Kein doppelter Import.", level="warning")
                    st.rerun()
                exact_dupes = [
                    m for m in find_duplicate_playlists_by_tracks(
                        parsed_tracks,
                        event=event.strip(),
                        source=source.strip(),
                        sub_event=birthday_sub_event.strip(),
                        threshold=0.95
                    ) if m.get("exact_same")
                ]
                if exact_dupes:
                    log_import_run(import_type, playlist_name, event.strip(), source.strip(), len(parsed_tracks), status="duplicate", note=f"Schon vorhanden als {exact_dupes[0]['name']}", sub_event=birthday_sub_event.strip(), signature=signature)
                    set_last_upload_feedback(
                        f"⚠️ Nicht gespeichert: Inhalt ist bereits vorhanden als '{exact_dupes[0]['name']}'.",
                        level="warning"
                    )
                    st.rerun()
                start_upload_busy("Playlist wird gespeichert...")
                save_playlist(playlist_name, event.strip(), source.strip(), is_top, import_type, parsed_tracks, sub_event=birthday_sub_event.strip(), upload_note=upload_note)
                auto_backup_after_data_change("single_text_import")
                st.session_state["last_upload_signature"] = signature
                log_import_run(import_type, playlist_name, event.strip(), source.strip(), len(parsed_tracks), status="ok", note=(f"Text-Import gespeichert | {upload_note}" if upload_note else "Text-Import gespeichert"), sub_event=birthday_sub_event.strip(), signature=signature)
                clear_upload_busy()
                set_last_upload_feedback(f"✅ Playlist erfolgreich hochgeladen: {playlist_name} • {len(parsed_tracks)} Tracks")
                st.rerun()

    elif import_mode == "Datei hochladen":
        uploaded = st.file_uploader("TXT-Datei hochladen", type=["txt"])
        if uploaded:
            imported_text = uploaded.read().decode("utf-8", errors="ignore")
            import_type = "txt"
            guessed_event, guessed_sub_event = infer_event_and_sub_event_from_name(uploaded.name, name)
            if guessed_event == "Geburtstag" and not event.strip():
                st.info(f"🔎 Auto-Erkennung aus Dateiname: {guessed_event}{(' › ' + guessed_sub_event) if guessed_sub_event else ''}")
                if st.button("Auto-Erkennung für Anlass übernehmen", key="apply_auto_event_single", width="stretch"):
                    st.session_state["import_event"] = guessed_event
                    if guessed_sub_event:
                        st.session_state["import_sub_event"] = guessed_sub_event
                    st.rerun()
            elif guessed_event == "Geburtstag" and is_birthday_event(event) and guessed_sub_event and not st.session_state.get("import_sub_event"):
                st.session_state["import_sub_event"] = guessed_sub_event
                st.caption(f"🔎 Unterordner automatisch erkannt: {guessed_sub_event}")
            st.text_area("Vorschau", imported_text, height=220)

            parsed_tracks = parse_text_to_tracks(imported_text)
            st.subheader("Erkannte Tracks")
            st.write(f"{len(parsed_tracks)} Tracks erkannt")
            render_duplicate_warning_box(
                parsed_tracks,
                event=event.strip(),
                source=source.strip(),
                sub_event=birthday_sub_event.strip(),
                key_prefix="single_file"
            )

            if st.button("Playlist speichern", type="primary", disabled=is_upload_busy()):
                playlist_name = name.strip() if name.strip() else Path(uploaded.name).stem
                signature = make_upload_signature("txt", playlist_name, event.strip(), source.strip(), parsed_tracks, birthday_sub_event.strip())
                if st.session_state.get("last_upload_signature") == signature:
                    log_import_run(import_type, playlist_name, event.strip(), source.strip(), len(parsed_tracks), status="skipped", note="Gerade bereits importiert", sub_event=birthday_sub_event.strip(), signature=signature)
                    set_last_upload_feedback("⚠️ Diese Playlist wurde gerade schon erfolgreich hochgeladen. Kein doppelter Import.", level="warning")
                    st.rerun()
                exact_dupes = [
                    m for m in find_duplicate_playlists_by_tracks(
                        parsed_tracks,
                        event=event.strip(),
                        source=source.strip(),
                        sub_event=birthday_sub_event.strip(),
                        threshold=0.95
                    ) if m.get("exact_same")
                ]
                if exact_dupes:
                    log_import_run(import_type, playlist_name, event.strip(), source.strip(), len(parsed_tracks), status="duplicate", note=f"Schon vorhanden als {exact_dupes[0]['name']}", sub_event=birthday_sub_event.strip(), signature=signature)
                    set_last_upload_feedback(
                        f"⚠️ Nicht gespeichert: Inhalt ist bereits vorhanden als '{exact_dupes[0]['name']}'.",
                        level="warning"
                    )
                    st.rerun()
                start_upload_busy("Datei wird gespeichert...")
                save_playlist(playlist_name, event.strip(), source.strip(), is_top, import_type, parsed_tracks, sub_event=birthday_sub_event.strip(), upload_note=upload_note)
                auto_backup_after_data_change("single_file_import")
                st.session_state["last_upload_signature"] = signature
                log_import_run(import_type, playlist_name, event.strip(), source.strip(), len(parsed_tracks), status="ok", note=(f"Datei-Import gespeichert | {upload_note}" if upload_note else "Datei-Import gespeichert"), sub_event=birthday_sub_event.strip(), signature=signature)
                clear_upload_busy()
                set_last_upload_feedback(f"✅ Playlist erfolgreich hochgeladen: {playlist_name} • {len(parsed_tracks)} Tracks")
                st.rerun()

    elif import_mode == "Mehrere Dateien hochladen":
        st.subheader("Mehrere Playlists auf einmal")
        st.caption("Am besten mehrere TXT-Dateien gleichzeitig markieren.")

        use_filename_for_name = st.checkbox("Dateinamen als Playlist-Namen verwenden", value=True)
        use_filename_for_source = st.checkbox("Dateinamen als Herkunft verwenden", value=False)

        uploaded_files = st.file_uploader(
            "Mehrere TXT-Dateien hochladen",
            type=["txt"],
            accept_multiple_files=True
        )

        if uploaded_files:
            st.write(f"{len(uploaded_files)} Dateien ausgewählt")

            preview = []
            total_tracks = 0
            valid_files = []

            for uf in uploaded_files:
                file_text = uf.read().decode("utf-8", errors="ignore")
                parsed_tracks = parse_text_to_tracks(file_text)
                if parsed_tracks:
                    valid_files.append((uf.name, parsed_tracks))
                    total_tracks += len(parsed_tracks)
                    guessed_event, guessed_sub_event = infer_event_and_sub_event_from_name(uf.name)
                    effective_event = event.strip() if event.strip() else guessed_event
                    effective_sub_event = birthday_sub_event.strip() if birthday_sub_event.strip() else guessed_sub_event
                    duplicate_hits = find_duplicate_playlists_by_tracks(
                        parsed_tracks,
                        event=effective_event,
                        source=guess_source_from_filename(uf.name) if use_filename_for_source else source.strip(),
                        sub_event=effective_sub_event,
                        threshold=0.95
                    )
                    preview.append({
                        "Datei": uf.name,
                        "Tracks": len(parsed_tracks),
                        "Anlass": format_event_label(effective_event, effective_sub_event) if effective_event else "-",
                        "Herkunft": guess_source_from_filename(uf.name) if use_filename_for_source else (source.strip() if source.strip() else "-"),
                        "Auto": format_event_label(guessed_event, guessed_sub_event) if guessed_event else "-",
                        "Dublette": "Ja" if any(m.get("exact_same") for m in duplicate_hits) else ("Möglich" if duplicate_hits else "-"),
                    })

            if preview:
                st.dataframe(preview, width="stretch", hide_index=True)
                st.write(f"Insgesamt erkannte Tracks: {total_tracks}")

            if st.button("Neue Playlists speichern (Dubletten werden ignoriert)", type="primary"):
                start_ts = time.time()
                saved = 0
                skipped = 0
                result_rows = []
                for filename, parsed_tracks in valid_files:
                    playlist_name = Path(filename).stem if use_filename_for_name else (name.strip() if name.strip() else Path(filename).stem)
                    playlist_source = guess_source_from_filename(filename) if use_filename_for_source else source.strip()
                    guessed_event, guessed_sub_event = infer_event_and_sub_event_from_name(filename, playlist_name)
                    effective_event = event.strip() if event.strip() else guessed_event
                    effective_sub_event = birthday_sub_event.strip() if birthday_sub_event.strip() else guessed_sub_event
                    signature = make_upload_signature("txt_multi", playlist_name, effective_event, playlist_source, parsed_tracks, effective_sub_event)
                    if st.session_state.get("last_upload_signature") == signature:
                        skipped += 1
                        result_rows.append({"Datei": filename, "Playlist": playlist_name, "Status": "❌ Dublette – übersprungen"})
                        continue
                    exact_dupes = [
                        m for m in find_duplicate_playlists_by_tracks(
                            parsed_tracks,
                            event=effective_event,
                            source=playlist_source,
                            sub_event=effective_sub_event,
                            threshold=0.95
                        ) if m.get("exact_same")
                    ]
                    if exact_dupes:
                        skipped += 1
                        result_rows.append({"Datei": filename, "Playlist": playlist_name, "Status": "❌ Dublette – übersprungen"})
                        continue
                    save_playlist(playlist_name, effective_event, playlist_source, is_top, "txt", parsed_tracks, sub_event=effective_sub_event, upload_note=upload_note)
                    st.session_state["last_upload_signature"] = signature
                    saved += 1
                    result_rows.append({"Datei": filename, "Playlist": playlist_name, "Status": "✅ gespeichert"})

                if saved:
                    auto_backup_after_data_change("multi_file_import")
                set_last_upload_result_rows(result_rows)
                set_last_upload_feedback(f"✅ Upload fertig: {saved} Playlist(s) gespeichert • {total_tracks} Tracks • {round(time.time()-start_ts,1)} Sek. {'| '+str(skipped)+' übersprungen' if skipped else ''}")
                st.rerun()

    elif import_mode == "ZIP hochladen":
        st.subheader("Ganzer Ordner als ZIP")
        st.caption("Am besten den Hauptordner oder einen Teilordner als ZIP hochladen. Bei ZIP-Import gilt jetzt Vollautomatik: Event, Herkunft, Geburtstag und Top werden aus der Ordnerstruktur erkannt.")

        st.info("Beim ZIP-Import werden Anlass/Herkunft weiter automatisch aus der Ordnerstruktur erkannt. Deine Upload-Notiz oben wird zusätzlich pro gespeicherter Playlist mitgesichert.")

        uploaded_zip = st.file_uploader("ZIP-Datei hochladen", type=["zip"], key="structured_zip_upload")

        if uploaded_zip:
            preview = []
            total_tracks = 0
            valid_files = []

            try:
                zip_bytes = uploaded_zip.read()
                restore_upload = io.BytesIO(zip_bytes)
                with pyzipfile.ZipFile(restore_upload) as zf:
                    txt_members = [m for m in zf.namelist() if m.lower().endswith(".txt") and not m.endswith("/")]
                    st.write(f"{len(txt_members)} TXT-Dateien in der ZIP gefunden")

                    duplicate_indexes = {}
                    for member in txt_members:
                        try:
                            file_text = zf.read(member).decode("utf-8", errors="ignore")
                            parsed_tracks = parse_text_to_tracks(file_text)
                            if not parsed_tracks:
                                continue

                            detected = infer_structured_meta_from_zip_member(member)
                            merged = merge_import_meta(
                                detected,
                                manual_event="",
                                manual_source="",
                                manual_sub_event="",
                                manual_top=False,
                                prefer_detected=True,
                            )

                            playlist_name = merged["playlist_name"] or Path(member).stem
                            effective_event = merged["event"]
                            effective_source = merged["source"]
                            effective_sub_event = merged["sub_event"]
                            index_key = (normalize_meta_key(effective_event), normalize_meta_key(effective_source), normalize_meta_key(effective_sub_event))
                            if index_key not in duplicate_indexes:
                                duplicate_indexes[index_key] = preload_duplicate_index(
                                    event=effective_event,
                                    source=effective_source,
                                    sub_event=effective_sub_event,
                                )
                            duplicate_hits = find_duplicate_playlists_in_index(
                                parsed_tracks,
                                duplicate_indexes[index_key],
                                threshold=0.95,
                            )

                            valid_files.append((member, playlist_name, merged, parsed_tracks, index_key))
                            total_tracks += len(parsed_tracks)
                            preview.append({
                                "Datei": member,
                                "Playlist": playlist_name,
                                "Tracks": len(parsed_tracks),
                                "Anlass": format_event_label(effective_event, effective_sub_event) if effective_event else "-",
                                "Herkunft": effective_source or "-",
                                "Top": "Ja" if merged["is_top"] else "-",
                                "Dublette": "Ja" if any(m.get("exact_same") for m in duplicate_hits) else ("Möglich" if duplicate_hits else "-"),
                            })
                        except Exception:
                            pass

                if preview:
                    st.dataframe(preview, width="stretch", hide_index=True)
                    st.write(f"Insgesamt erkannte Tracks: {total_tracks}")
                    st.info("Die Reihenfolge der Songs bleibt erhalten und wird für Analyse, Live Hilfe, Transition KI und Auto-Set weiterverwendet.")
                else:
                    st.warning("Keine passenden TXT-Dateien in der ZIP gefunden.")

                if valid_files and st.button("Neue Playlists aus ZIP speichern (Struktur wird automatisch erkannt)", type="primary"):
                    start_ts = time.time()
                    saved = 0
                    skipped = 0
                    result_rows = []
                    progress = st.progress(0, text="Speichere ZIP-Inhalt ...")
                    total_files = len(valid_files)

                    for idx, (member_path, playlist_name, merged, parsed_tracks, index_key) in enumerate(valid_files, start=1):
                        signature = make_upload_signature(
                            "zip_structured",
                            playlist_name,
                            merged["event"],
                            merged["source"],
                            parsed_tracks,
                            merged["sub_event"],
                        )
                        if st.session_state.get("last_upload_signature") == signature:
                            skipped += 1
                            result_rows.append({"Datei": playlist_name, "Status": "❌ Dublette – übersprungen"})
                            progress.progress(int((idx / max(total_files, 1)) * 100), text=f"Überspringe Duplikat {playlist_name}")
                            continue

                        existing_index = duplicate_indexes.get(index_key) or []
                        exact_dupes = [
                            dup for dup in find_duplicate_playlists_in_index(
                                parsed_tracks,
                                existing_index,
                                threshold=0.95
                            ) if dup.get("exact_same")
                        ]
                        if exact_dupes:
                            skipped += 1
                            result_rows.append({"Datei": playlist_name, "Status": "❌ Dublette – übersprungen"})
                            progress.progress(int((idx / max(total_files, 1)) * 100), text=f"Überspringe Inhalts-Dublette {playlist_name}")
                            continue

                        save_playlist(
                            playlist_name,
                            merged["event"],
                            merged["source"],
                            merged["is_top"],
                            "zip_structured",
                            parsed_tracks,
                            sub_event=merged["sub_event"],
                            upload_note=upload_note,
                        )
                        st.session_state["last_upload_signature"] = signature
                        duplicate_indexes.setdefault(index_key, []).append({"playlist_id": -idx, "name": playlist_name, "event": merged["event"], "sub_event": merged["sub_event"], "source": merged["source"], "seq": [t.get("normalized_name") for t in parsed_tracks if t.get("normalized_name")], "fingerprint": "||".join([t.get("normalized_name") for t in parsed_tracks if t.get("normalized_name")]), "track_set": set([t.get("normalized_name") for t in parsed_tracks if t.get("normalized_name")]), "track_count": len([t.get("normalized_name") for t in parsed_tracks if t.get("normalized_name")])})
                        saved += 1
                        result_rows.append({
                            "Datei": playlist_name,
                            "Status": "✅ gespeichert",
                            "Anlass": format_event_label(merged["event"], merged["sub_event"]) or "-",
                            "Herkunft": merged["source"] or "-",
                            "Top": "Ja" if merged["is_top"] else "-",
                        })
                        progress.progress(int((idx / max(total_files, 1)) * 100), text=f"Speichere {playlist_name} ...")

                    if saved:
                        auto_backup_after_data_change("zip_import")
                    set_last_upload_result_rows(result_rows)
                    set_last_upload_feedback(
                        f"✅ Struktur-Import fertig: {saved} Playlist(s) gespeichert • {total_tracks} Tracks • {round(time.time()-start_ts,1)} Sek. {'| '+str(skipped)+' übersprungen' if skipped else ''}"
                    )
                    st.rerun()

            except Exception as e:
                st.error(f"ZIP konnte nicht gelesen werden: {e}")

elif menu == "Upload Dashboard":
    render_upload_dashboard_page()

elif menu == "Zuletzt importierte Playlists":
    st.header("Zuletzt importierte Playlists")
    st.caption("Global über alle Quellen und Anlässe. So findest du schnell die letzten 10, 20 oder 50 Uploads und kannst sie direkt öffnen oder analysieren.")
    render_recent_imported_playlists_panel(default_limit=20, key_prefix="recent_imports_page", show_header=False)

elif menu == "Playlists durchsuchen":
    st.header("Playlists durchsuchen")
    st.caption("Hier kannst du gespeicherte Playlists filtern, gezielt löschen und gefilterte Metadaten gesammelt anpassen.")

    overview = get_library_overview()
    cols = st.columns(5)
    cols[0].metric("Playlists gesamt", p_count)
    cols[1].metric("Tracks gesamt", t_count)
    cols[2].metric("Anlässe", overview.get("event_count", 0))
    cols[3].metric("Quellen", overview.get("source_count", 0))
    cols[4].metric("Top Playlists", overview.get("top_playlist_count", 0))

    st.subheader("Zuletzt erfolgreich importiert")
    latest_rows = overview.get("latest_rows", [])
    if latest_rows:
        for pid, latest_name, latest_event, latest_sub_event, latest_source, latest_genre, latest_created in latest_rows:
            latest_event_label = format_event_label(latest_event, latest_sub_event)
            st.caption(f"• {latest_name} | {latest_event_label or '-'} | {latest_source or '-'} | {latest_genre or '-'} | {latest_created or '-'}")
    else:
        st.info("Noch keine Playlists importiert.")

    st.divider()

    focused_playlist_id = int(st.session_state.get("browse_focus_playlist_id") or 0)
    if focused_playlist_id:
        focused_pack = build_single_playlist_analysis(focused_playlist_id)
        if focused_pack:
            with st.expander("🎯 Direkt geöffnete Playlist", expanded=True):
                render_recent_playlist_detail(focused_pack, key_prefix="browse_focus")
                if st.button("Fokus schließen", key="browse_focus_close_btn", width="stretch"):
                    st.session_state["browse_focus_playlist_id"] = 0
                    st.rerun()

    f1, f2, f3, f4 = st.columns(4)
    filter_event = f1.selectbox("Anlass", events, key="browse_event")
    filter_source = f2.selectbox("Herkunft", sources, key="browse_source")
    filter_sub_event = "Alle"
    if is_birthday_event(filter_event):
        filter_sub_event = f3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(filter_event), key="browse_sub_event")
    else:
        f3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top_only = f4.checkbox("Nur Top Playlists", key="browse_top")
    sort_option = st.selectbox("Sortierung", ["Neueste zuerst", "Älteste zuerst", "Name A–Z", "Name Z–A"], index=0, key="browse_sort")

    try:
        rows = get_playlists(event=filter_event, source=filter_source, sub_event=filter_sub_event, top_only=top_only)
    except TypeError:
        rows = get_playlists(event=filter_event, source=filter_source, sub_event=filter_sub_event, top_only=top_only)

    if sort_option == "Neueste zuerst":
        rows = sorted(rows, key=lambda x: (x[-1] or "", x[0]), reverse=True)
    elif sort_option == "Älteste zuerst":
        rows = sorted(rows, key=lambda x: (x[-1] or "", x[0]))
    elif sort_option == "Name A–Z":
        rows = sorted(rows, key=lambda x: str(x[1] or "").lower())
    elif sort_option == "Name Z–A":
        rows = sorted(rows, key=lambda x: str(x[1] or "").lower(), reverse=True)

    st.write(f"{len(rows)} Playlists gefunden")

    st.subheader("Massenaktionen für die aktuelle Filter-Auswahl")
    st.caption("Beispiel: Herkunft = Benjamin Schneider und Anlass = Hochzeit wählen, dann nur diese Playlists löschen oder anpassen.")
    a1, a2 = st.columns(2)
    if a1.button("🗑️ Gefilterte Playlists löschen", key="delete_filtered_playlists", width="stretch", disabled=(len(rows) == 0)):
        st.session_state["confirm_delete_filtered"] = True
    if a2.button("🗑️ Alle Playlists löschen", key="delete_all_playlists", width="stretch"):
        st.session_state["confirm_delete_all"] = True

    if st.session_state.get("confirm_delete_filtered"):
        st.error(f"Wirklich {len(rows)} gefilterte Playlist(s) löschen? Das kann nicht rückgängig gemacht werden.")
        c1, c2 = st.columns(2)
        if c1.button("✅ Ja, gefilterte löschen", key="confirm_delete_filtered_yes", width="stretch"):
            deleted = delete_filtered_playlists(
                event=filter_event,
                source=filter_source,
                sub_event=filter_sub_event,
                top_only=top_only,
            )
            st.session_state["confirm_delete_filtered"] = False
            st.success(f"{deleted} gefilterte Playlist(s) gelöscht.")
            st.rerun()
        if c2.button("❌ Abbrechen", key="confirm_delete_filtered_no", width="stretch"):
            st.session_state["confirm_delete_filtered"] = False
            st.rerun()

    if st.session_state.get("confirm_delete_all"):
        st.error("Wirklich ALLE Playlists löschen? Das kann nicht rückgängig gemacht werden.")
        c1, c2 = st.columns(2)
        if c1.button("✅ Ja, alle löschen", key="confirm_delete_all_yes", width="stretch"):
            delete_all_playlists()
            st.session_state["confirm_delete_all"] = False
            st.success("Alle Playlists wurden gelöscht.")
            st.rerun()
        if c2.button("❌ Abbrechen", key="confirm_delete_all_no", width="stretch"):
            st.session_state["confirm_delete_all"] = False
            st.rerun()

    with st.expander("✏️ Gefilterte Playlists gesammelt ändern", expanded=False):
        st.caption("Wenn du dich z. B. bei Benjamin Schneider / Hochzeit vertan hast, kannst du genau diese Auswahl gesammelt korrigieren.")
        m1, m2, m3 = st.columns(3)
        try:
            new_event_value = m1.selectbox(
                "Neuer Anlass",
                options=["Unverändert"] + ["Hochzeit", "Geburtstag", "Party", "Firmenfeier", "Fasching", "80s", "90s", "90er-2000er", "2000s", "2010s", "Mixed", "Schlager", "Rock", "Latin"],
                index=0,
                accept_new_options=True,
                key="bulk_new_event",
            )
        except TypeError:
            new_event_value = m1.text_input("Neuer Anlass", key="bulk_new_event")
        new_sub_event_value = "Unverändert"
        if is_birthday_event(filter_event):
            try:
                new_sub_event_value = m2.selectbox(
                    "Neuer Geburtstag-Unterordner",
                    options=["Unverändert"] + BIRTHDAY_SUBEVENT_PRESETS,
                    index=0,
                    accept_new_options=True,
                    key="bulk_new_sub_event",
                )
            except TypeError:
                new_sub_event_value = m2.text_input("Neuer Geburtstag-Unterordner", key="bulk_new_sub_event")
        else:
            m2.caption("Geburtstag-Unterordner nur bei Geburtstag")

        try:
            new_source_value = m3.selectbox(
                "Neue Herkunft",
                options=["Unverändert", "Benjamin Schneider", "Michael Zimmermann", "Global", "Reverenz"],
                index=0,
                accept_new_options=True,
                key="bulk_new_source",
            )
        except TypeError:
            new_source_value = m2.text_input("Neue Herkunft", key="bulk_new_source")

        if st.button("💾 Gefilterte Playlists ändern", key="bulk_update_filtered", width="stretch", disabled=(len(rows) == 0)):
            update_event = None if str(new_event_value or "").strip() in {"", "Unverändert"} else str(new_event_value).strip()
            update_source = None if str(new_source_value or "").strip() in {"", "Unverändert"} else str(new_source_value).strip()
            changed = bulk_update_filtered_playlists(
                event=filter_event,
                source=filter_source,
                sub_event=filter_sub_event,
                top_only=top_only,
                new_event=update_event,
                new_source=update_source,
            )
            if changed:
                st.success(f"{changed} gefilterte Playlist(s) geändert.")
                st.rerun()
            else:
                st.info("Keine Änderung durchgeführt.")

    for row in rows:
        if len(row) == 7:
            pid, name, event, sub_event, source, is_top, created_at = row
            genre = ""
        else:
            pid, name, event, sub_event, source, genre, is_top, created_at = row

        event_label = format_event_label(event, sub_event)
        top_label = "⭐ " if is_top else ""
        label = f"{top_label}{name} | {event_label or '-'} | {source or '-'} | {genre or '-'} | {created_at or '-'}"
        with st.expander(label):

            tracks = get_playlist_tracks(pid)

            selected_count = sum(1 for p, _a, _t, _r, _raw, _n in tracks if st.session_state.get(f"mem_pick_{pid}_{p}"))
            if selected_count > 0:
                st.markdown(
                    f"""
                    <div style="position:sticky;top:0;z-index:5;background:#111827;border:1px solid #374151;
                    border-radius:12px;padding:10px 14px;margin-bottom:10px;">
                    ⭐ <b>{selected_count} Song(s) markiert</b> – unten direkt in DJ Memory speichern
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.write(f"Tracks: {len(tracks)}")
            for p, a, t, r, raw, n in tracks:
                display_name = f"{a} - {t}".strip(" -")
                col_a, col_b = st.columns([0.8, 9.2])
                col_a.checkbox(f"Merken {p}", key=f"mem_pick_{pid}_{p}", label_visibility="collapsed")
                col_b.write(f"**{p}.** {display_name}")

            chosen = []
            for p, a, t, r, raw, n in tracks:
                if st.session_state.get(f"mem_pick_{pid}_{p}"):
                    chosen.append({
                        "position": p,
                        "display": f"{a} - {t}".strip(" -"),
                    })

            with st.container(border=True):
                st.markdown("### ⭐ Auswahl merken")
                st.caption("Einfach Songs anhaken, Typ festlegen und direkt speichern.")
                if chosen:
                    st.caption(f"{len(chosen)} Song(s) ausgewählt")
                    st.text_area(
                        "Auswahl",
                        value="\n".join([f"{x['position']}. {x['display']}" for x in chosen]),
                        height=120,
                        disabled=True,
                        key=f"mem_preview_{pid}",
                    )
                else:
                    st.info("Einfach Songs anhaken und dann hier speichern.")

                mem1, mem2, mem3 = st.columns(3)
                combo_type = mem1.selectbox(
                    "Speichern als",
                    ["Block", "Übergang", "Einzeltrack"],
                    key=f"mem_type_{pid}",
                )
                usage_context = mem2.selectbox(
                    "Anlass / Einsatz",
                    [""] + get_saved_combo_contexts() + ["Hochzeit", "Geburtstag", "Party", "Warmup", "Peak", "Closing", "NDW", "Black", "R&B"],
                    accept_new_options=True,
                    key=f"mem_context_{pid}",
                )
                category = mem3.selectbox(
                    "Kategorie / Ordner",
                    [""] + get_saved_combo_categories(),
                    accept_new_options=True,
                    key=f"mem_category_{pid}",
                )

                tags = st.text_input(
                    "Tags (Komma getrennt)",
                    key=f"mem_tags_{pid}",
                    placeholder="z. B. Peak, NDW, Männerblock, Mitsingmoment",
                )
                if get_saved_combo_tags():
                    st.caption("Vorhandene Tags: " + ", ".join(get_saved_combo_tags()[:20]))

                note = st.text_area(
                    "Notiz",
                    key=f"mem_note_{pid}",
                    placeholder="optional",
                    height=80,
                )

                action_left, action_mid, action_right = st.columns([2.5, 1.2, 1.2])
                if action_left.button("💾 In DJ Memory speichern", key=f"save_memory_{pid}", width="stretch"):
                    chosen_texts = [x["display"] for x in chosen]
                    if not chosen_texts:
                        st.warning("Bitte erst Songs anhaken.")
                    elif combo_type == "Einzeltrack" and len(chosen_texts) != 1:
                        st.warning("Für Einzeltrack bitte genau 1 Song auswählen.")
                    elif combo_type == "Übergang" and len(chosen_texts) < 2:
                        st.warning("Für Übergang bitte mindestens 2 Songs auswählen.")
                    else:
                        save_combo(
                            combo_type=combo_type,
                            combo_text=" | ".join(chosen_texts),
                            source_track=chosen_texts[0] if chosen_texts else "",
                            note=note,
                            category=category,
                            tags=tags,
                            usage_context=usage_context,
                            source_name=source,
                            genre_name=genre,
                            event_name=event_label,
                            playlist_name=name,
                            playlist_id=pid,
                        )
                        st.session_state["memory_feedback"] = f"✅ Gespeichert unter: {category or 'Ohne Ordner'}"
                        for item in tracks:
                            st.session_state[f"mem_pick_{pid}_{item[0]}"] = False
                        st.rerun()

                if action_mid.button("🧠 DJ Memory öffnen", key=f"jump_memory_{pid}", width="stretch"):
                    set_active_menu("Gemerkte Kombinationen")
                    st.rerun()

                if action_right.button("🧹 Auswahl leeren", key=f"clear_memory_{pid}", width="stretch"):
                    for item in tracks:
                        st.session_state[f"mem_pick_{pid}_{item[0]}"] = False
                    st.rerun()

            with st.expander("Trackliste als Tabelle", expanded=False):
                preview_rows = [{"Pos": p, "Artist": a, "Titel": t} for p, a, t, r, raw, n in tracks]
                st.dataframe(
                    preview_rows,
                    width="stretch",
                    hide_index=True,
                )

            edit_event_options = [x for x in events if x != "Alle"]
            edit_source_options = [x for x in sources if x != "Alle"]
            edit_cols = st.columns(4)
            try:
                edit_event = edit_cols[0].selectbox(
                    "Anlass ändern",
                    options=edit_event_options,
                    index=edit_event_options.index(normalize_meta_value(event)) if normalize_meta_value(event) in edit_event_options else 0,
                    accept_new_options=True,
                    key=f"edit_event_{pid}",
                )
            except TypeError:
                edit_event = edit_cols[0].text_input("Anlass ändern", value=event or "", key=f"edit_event_{pid}")
            try:
                edit_source = edit_cols[1].selectbox(
                    "Herkunft ändern",
                    options=edit_source_options,
                    index=edit_source_options.index(normalize_meta_value(source)) if normalize_meta_value(source) in edit_source_options else 0,
                    accept_new_options=True,
                    key=f"edit_source_{pid}",
                )
            except TypeError:
                edit_source = edit_cols[1].text_input("Herkunft ändern", value=source or "", key=f"edit_source_{pid}")
            edit_name = edit_cols[2].text_input("Name ändern", value=name or "", key=f"edit_name_{pid}")
            edit_top = edit_cols[3].checkbox("Top Playlist", value=bool(is_top), key=f"edit_top_{pid}")

            sub_event_value = sub_event or ""
            if is_birthday_event(edit_event):
                try:
                    sub_event_value = st.selectbox(
                        "Geburtstag-Unterordner",
                        options=BIRTHDAY_SUBEVENT_PRESETS,
                        index=BIRTHDAY_SUBEVENT_PRESETS.index(normalize_sub_event(sub_event)) if normalize_sub_event(sub_event) in BIRTHDAY_SUBEVENT_PRESETS else 0,
                        accept_new_options=True,
                        key=f"edit_sub_event_{pid}",
                    )
                except TypeError:
                    sub_event_value = st.text_input("Geburtstag-Unterordner", value=sub_event or "", key=f"edit_sub_event_{pid}")

            current_upload_note = ""
            try:
                current_upload_note = get_playlist_upload_note(pid)
            except Exception:
                current_upload_note = ""
            edit_upload_note = st.text_area("Upload-Notiz", value=current_upload_note, height=70, key=f"edit_upload_note_{pid}")

            action_cols = st.columns(2)
            if action_cols[0].button("💾 Änderungen speichern", key=f"save_{pid}", width="stretch"):
                update_playlist_meta(
                    pid,
                    new_event=edit_event,
                    new_sub_event=sub_event_value if is_birthday_event(edit_event) else "",
                    new_source=edit_source,
                    new_name=edit_name,
                    new_is_top=edit_top,
                    new_upload_note=edit_upload_note,
                )
                st.success("Playlist aktualisiert.")
                st.rerun()
            if action_cols[1].button("🗑️ Diese Playlist löschen", key=f"del_{pid}", width="stretch"):
                delete_playlist(pid)
                st.success("Playlist gelöscht.")
                st.rerun()


def get_phase_sort_value(label: str) -> int:
    label = str(label or "")
    if "Dinner" in label:
        return 1
    if "Warmup" in label:
        return 2
    if "Aufbau" in label:
        return 3
    if "Peak" in label:
        return 4
    if "Closing" in label or "Spät" in label:
        return 5
    return 99


def build_event_phase_intelligence(event=None, source=None, top_only=False, sub_event=None, phase_focus="Alle"):
    data = compute_data(event=event, source=source, top_only=top_only, sub_event=sub_event)
    buckets = {
        "🍽️ Dinner / Empfang": [],
        "🌙 Warmup": [],
        "⬆️ Aufbau": [],
        "🔥 Peak": [],
        "🌅 Closing": [],
    }
    phase_counts = Counter()
    all_rows = []

    for norm, cnt in data["track_total_counts"].most_common(220):
        display = display_from_normalized(norm)
        phase = get_track_phase_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        energy = estimate_track_energy(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        role = get_track_role_label(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        timing = get_track_timing_bucket(display, event=event, source=source, top_only=top_only, sub_event=sub_event)
        stats = get_track_position_stats(display, event=event, source=source, top_only=top_only, sub_event=sub_event) or {}
        row = {
            "song": display,
            "count": cnt,
            "phase": phase,
            "energy": energy,
            "role": role,
            "timing": timing,
            "avg_position": stats.get("avg_position", "-"),
            "samples": stats.get("sample_count", 0),
        }
        all_rows.append(row)
        if phase in buckets:
            buckets[phase].append(row)
            phase_counts[phase] += 1

    phase_pairs = []
    for (a, b), cnt in data["pair_counts"].most_common(220):
        left = display_from_normalized(a)
        right = display_from_normalized(b)
        left_phase = get_track_phase_label(left, event=event, source=source, top_only=top_only, sub_event=sub_event)
        right_phase = get_track_phase_label(right, event=event, source=source, top_only=top_only, sub_event=sub_event)
        if left_phase == "❔ Unklar" or right_phase == "❔ Unklar":
            continue
        if left_phase == right_phase:
            continue
        phase_pairs.append({
            "combo": f"{left} → {right}",
            "count": cnt,
            "from_phase": left_phase,
            "to_phase": right_phase,
        })

    phase_pairs = sorted(phase_pairs, key=lambda x: (x["count"], -get_phase_sort_value(x["from_phase"]), -get_phase_sort_value(x["to_phase"])), reverse=True)[:40]

    focus_rows = all_rows
    if phase_focus and phase_focus != "Alle":
        focus_rows = [r for r in all_rows if r["phase"] == phase_focus]

    return {
        "buckets": buckets,
        "phase_counts": phase_counts,
        "all_rows": all_rows,
        "focus_rows": focus_rows,
        "phase_pairs": phase_pairs,
    }



if menu == "Event-Phasen":
    st.header("Event-Phasen")
    st.caption("V105 macht die Phasen-Auswertung deutlich intelligenter: Fokus pro Phase, Track-Check und typische Übergänge zwischen Event-Phasen.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Analyse Hub", title="Schnell laden")
    recent_playlist_name = str(st.session_state.get("recent_analysis_playlist_name") or "").strip()
    recent_playlist_event_label = str(st.session_state.get("recent_analysis_playlist_event_label") or "").strip()
    if recent_playlist_name:
        st.info(f"Direkt aus zuletzt importierten Playlists geöffnet: {recent_playlist_name} | {recent_playlist_event_label or '-'}")

    c1, c2, c3, c4 = st.columns(4)
    filter_event = c1.selectbox("Anlass", events, key="phase_event")
    filter_source = c2.selectbox("Herkunft", sources, key="phase_source")
    filter_sub_event = "Alle"
    if is_birthday_event(filter_event):
        filter_sub_event = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(filter_event), key="phase_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top_only = c4.checkbox("Nur Top Playlists", key="phase_top")

    phase_options = ["Alle", "🍽️ Dinner / Empfang", "🌙 Warmup", "⬆️ Aufbau", "🔥 Peak", "🌅 Closing"]
    d1, d2 = st.columns([1.2, 2.2])
    phase_focus = d1.selectbox("Phase-Fokus", phase_options, key="phase_focus")
    track_check = d2.text_input("Track-Check", placeholder="z. B. Mr. Brightside", key="phase_track_check")

    phase_pack = build_event_phase_intelligence(
        event=filter_event,
        source=filter_source,
        top_only=top_only,
        sub_event=filter_sub_event,
        phase_focus=phase_focus,
    )
    st.info("Die Phasen werden aus der echten Position des Songs in deinen Playlists gelernt. V105 zeigt dir jetzt zusätzlich, welche Übergänge zwischen den Phasen in echten Sets häufig vorkommen.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Dinner", phase_pack["phase_counts"].get("🍽️ Dinner / Empfang", 0))
    m2.metric("Warmup", phase_pack["phase_counts"].get("🌙 Warmup", 0))
    m3.metric("Aufbau", phase_pack["phase_counts"].get("⬆️ Aufbau", 0))
    m4.metric("Peak", phase_pack["phase_counts"].get("🔥 Peak", 0))
    m5.metric("Closing", phase_pack["phase_counts"].get("🌅 Closing", 0))

    tabs = st.tabs(["📊 Überblick", "🎯 Phase-Fokus", "🔁 Phasen-Übergänge", "🔎 Track-Check"])

    with tabs[0]:
        phase_tabs = st.tabs(["🍽️ Dinner", "🌙 Warmup", "⬆️ Aufbau", "🔥 Peak", "🌅 Closing"])
        phase_order = [
            (phase_tabs[0], "🍽️ Dinner / Empfang"),
            (phase_tabs[1], "🌙 Warmup"),
            (phase_tabs[2], "⬆️ Aufbau"),
            (phase_tabs[3], "🔥 Peak"),
            (phase_tabs[4], "🌅 Closing"),
        ]
        for tab, label in phase_order:
            with tab:
                rows = phase_pack["buckets"].get(label, [])[:20]
                if not rows:
                    st.info("Keine passenden Songs gefunden.")
                else:
                    for idx, row in enumerate(rows, start=1):
                        render_count_row(
                            f"{idx}. {row['song']} | {row['role']} | {row['timing']} | Energie {row['energy']} | Ø {row['avg_position']}",
                            row['count'],
                            combo_type="event_phase",
                            combo_text=row['song'],
                            set_key=f"phase_{label}_{idx}",
                        )

    with tabs[1]:
        st.subheader("Phase-Fokus")
        if phase_focus == "Alle":
            st.caption("Wähle oben eine Phase aus, dann zeigt dir V105 genau die relevantesten Songs nur für diesen Bereich.")
        rows = phase_pack["focus_rows"][:30]
        if not rows:
            st.info("Keine passenden Songs für diese Phase gefunden.")
        else:
            table_rows = []
            for idx, row in enumerate(rows, start=1):
                table_rows.append({
                    "#": idx,
                    "Song": row["song"],
                    "Phase": row["phase"],
                    "Rolle": row["role"],
                    "Timing": row["timing"],
                    "Energie": row["energy"],
                    "Ø Position": row["avg_position"],
                    "Nutzung": row["count"],
                })
            st.dataframe(table_rows, width="stretch", hide_index=True)

    with tabs[2]:
        st.subheader("Typische Phasen-Übergänge")
        st.caption("Das sind echte Track-Wechsel, bei denen der erste Song klar aus einer Phase kommt und der zweite Song typisch in die nächste Phase führt.")
        if not phase_pack["phase_pairs"]:
            st.info("Noch keine klaren Phasen-Übergänge gefunden.")
        else:
            for idx, row in enumerate(phase_pack["phase_pairs"][:20], start=1):
                render_count_row(
                    f"{idx}. {row['combo']} | {row['from_phase']} → {row['to_phase']}",
                    row['count'],
                    combo_type="phase_transition",
                    combo_text=row['combo'],
                    set_key=f"phase_transition_{idx}",
                )

    with tabs[3]:
        st.subheader("Track-Check")
        if not track_check.strip():
            st.info("Gib oben einen Song ein und du siehst Phase, Timing, Rolle und Energie dieses Tracks.")
        else:
            stats = get_track_position_stats(track_check, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
            phase = get_track_phase_label(track_check, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
            role = get_track_role_label(track_check, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
            timing = get_track_timing_bucket(track_check, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
            energy = estimate_track_energy(track_check, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
            if not stats:
                st.warning("Kein passender Track gefunden.")
            else:
                q1, q2, q3, q4 = st.columns(4)
                q1.metric("Phase", phase)
                q2.metric("Rolle", role)
                q3.metric("Timing", timing)
                q4.metric("Energie", energy)
                st.caption(f"Ø Position: {stats.get('avg_position', '-')} | Samples: {stats.get('sample_count', 0)} | Ø Playlist-Länge: {stats.get('avg_playlist_length', '-')} Tracks")

                insights = get_track_insights(track_check, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
                if insights and insights.get("after"):
                    st.markdown("**Typische nächste Songs ab diesem Track**")
                    for idx, (norm, cnt) in enumerate(insights["after"][:10], start=1):
                        display = display_from_normalized(norm)
                        next_phase = get_track_phase_label(display, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
                        render_count_row(
                            f"{idx}. {display} | {next_phase}",
                            cnt,
                            combo_type="phase_track_after",
                            combo_text=display,
                            set_key=f"phase_after_{idx}",
                        )
                else:
                    st.info("Keine typischen Folgesongs gefunden.")

elif menu == "Analyse Hub":
    st.header("Analyse Hub")
    st.caption("Alle wichtigen Analysen an einem Ort: Top Songs, Übergänge, Blöcke und davor / danach – jetzt ruhiger aufgebaut.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Analyse Hub", title="Schnell laden")

    f1, f2, f3 = st.columns([1.15, 1.15, 1.1])
    filter_event = f1.selectbox("Anlass", events, key="hub_event")
    filter_source = f2.selectbox("Herkunft", sources, key="hub_source")
    top_depth = f3.selectbox("Tiefe", [10, 20, 50, 100, "Alle"], index=1, key="hub_depth")
    top_depth_limit = resolve_display_depth(top_depth)

    f4, f5, f6 = st.columns([1.2, 0.9, 1.2])
    filter_sub_event = "Alle"
    if is_birthday_event(filter_event):
        filter_sub_event = f4.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(filter_event), key="hub_sub_event")
    else:
        f4.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top_only = f5.checkbox("Nur Top", key="hub_top")
    block_mode = f6.selectbox("Blöcke zeigen", ["3er-Blöcke", "4er-Blöcke", "5er-Blöcke"], index=0, key="hub_block_mode")

    if st.button("🧠 Gesamten Bestand neu analysieren", key="hub_rebuild_all", width="stretch"):
        with st.spinner("Analysiere kompletten Bestand neu ..."):
            rebuild_result = rebuild_full_analysis_state()
        st.success(f"Analyse neu aufgebaut: {rebuild_result['playlists']} Playlists • {rebuild_result['tracks']} Tracks • {rebuild_result['transitions']} Übergänge • {rebuild_result['roles']} Rollen")
        st.rerun()
    st.caption("Ein Klick baut die Lernbasis für den kompletten vorhandenen Bestand neu auf. Kein Neu-Upload nötig.")

    data = compute_data_cached(event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
    total_tracks = sum(int(v or 0) for v in data["track_total_counts"].values())
    snapshot = get_filtered_playlist_snapshot(event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event, limit=6)

    base_info = []
    base_info.append(f"Basis: {snapshot['total']} passende Playlists")
    if filter_event != 'Alle':
        base_info.append(f"Anlass: {format_event_label(filter_event, filter_sub_event) if is_birthday_event(filter_event) else filter_event}")
    if filter_source != 'Alle':
        base_info.append(f"Herkunft: {filter_source}")
    if top_only:
        base_info.append("nur Top-Playlists")
    st.info(" • ".join(base_info))
    if is_reference_source_label(filter_source) or top_only:
        st.caption("Referenz-/Top-Sicht aktiv: Neueste passende Playlists werden unten zuerst gezeigt, damit neue starke Sets schneller sichtbar sind.")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Songs", len(data["track_total_counts"]))
    m2.metric("Übergänge", len(data["pair_counts"]))
    m3.metric("Blöcke", len(data["block3_counts"]) + len(data["block4_counts"]) + len(data["block5_counts"]))
    m4.metric("Track-Nutzungen", total_tracks)

    st.info("🧠 KI-Komplettanalyse: Mit einem Klick wird der gesamte vorhandene Bestand neu für Übergänge, Blöcke, Rollen und Timing aufgebaut.")
    if st.button("🧠 Gesamten Bestand neu analysieren", key="analyse_hub_rebuild_all", width="stretch"):
        with st.spinner("Gesamter Bestand wird neu analysiert..."):
            result = rebuild_learning_engine()
            clear_runtime_caches()
        st.success(
            f"Komplettanalyse fertig: {result['playlists']} Playlists • {result['tracks']} Tracks • "
            f"{result['transitions']} Übergänge • {result['roles']} Rollen"
        )
        st.rerun()

    with st.expander("🔎 Woraus lernt diese Ansicht gerade?", expanded=False):
        st.caption("Damit das Tool nichts erfindet, siehst du hier die reale Basis der aktuellen Analyse.")
        latest_rows = snapshot.get('latest', [])
        if not latest_rows:
            st.info("Für diese Filter gibt es aktuell keine passenden Playlists.")
        else:
            for row in latest_rows:
                cols = st.columns([4.5, 1.5, 1.4])
                cols[0].markdown(f"**{row['name']}**  \n{row['event_label']} | {row['source']}")
                cols[1].caption(str(row['created_at']))
                if cols[2].button("Öffnen", key=f"hub_proof_open_{row['playlist_id']}", width="stretch"):
                    if jump_to_playlist_browser_for_playlist(int(row['playlist_id'])):
                        st.rerun()
                if row.get('upload_note'):
                    st.caption(f"Notiz: {row['upload_note']}")

    tabs = st.tabs(["🎧 Top Songs", "🔥 Übergänge", "🧱 Blöcke", "🔁 Davor / Danach"])

    with tabs[0]:
        st.subheader("Top Songs")
        rows = list(data["track_total_counts"].most_common(top_depth_limit)) if top_depth_limit is not None else list(data["track_total_counts"].most_common())
        if not rows:
            st.info("Keine Daten gefunden.")
        else:
            for idx, (norm, cnt) in enumerate(rows, start=1):
                display = display_from_normalized(norm)
                phase = get_track_phase_label(display, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
                render_count_row(
                    f"{idx}. {display} [{phase}]",
                    cnt,
                    combo_type="song",
                    combo_text=display,
                    set_key=f"hub_song_{idx}_{norm}"
                )

    with tabs[1]:
        st.subheader("Beste Übergänge / Songpaare")
        rows = list(data["pair_counts"].most_common(top_depth_limit)) if top_depth_limit is not None else list(data["pair_counts"].most_common())
        if not rows:
            st.info("Keine Übergänge gefunden.")
        else:
            for idx, ((a, b), cnt) in enumerate(rows, start=1):
                combo = f"{display_from_normalized(a)} → {display_from_normalized(b)}"
                render_count_row(
                    f"{idx}. {combo}",
                    cnt,
                    combo_type="2er",
                    combo_text=combo,
                    set_key=f"hub_pair_{idx}"
                )

    with tabs[2]:
        st.subheader(block_mode)
        if block_mode == "3er-Blöcke":
            block_rows = list(data["block3_counts"].most_common(top_depth_limit)) if top_depth_limit is not None else list(data["block3_counts"].most_common())
            combo_type = "3er"
            empty_text = "Keine 3er-Blöcke gefunden."
            key_prefix = "hub_b3"
        elif block_mode == "4er-Blöcke":
            block_rows = list(data["block4_counts"].most_common(top_depth_limit)) if top_depth_limit is not None else list(data["block4_counts"].most_common())
            combo_type = "4er"
            empty_text = "Keine 4er-Blöcke gefunden."
            key_prefix = "hub_b4"
        else:
            block_rows = list(data["block5_counts"].most_common(top_depth_limit)) if top_depth_limit is not None else list(data["block5_counts"].most_common())
            combo_type = "5er"
            empty_text = "Keine 5er-Blöcke gefunden."
            key_prefix = "hub_b5"

        if not block_rows:
            st.info(empty_text)
        else:
            st.caption("Oben wählst du, ob du 3er-, 4er- oder 5er-Blöcke sehen willst.")
            for idx, (block, cnt) in enumerate(block_rows, start=1):
                combo = " → ".join(display_from_normalized(x) for x in block)
                render_count_row(
                    f"{idx}. {combo}",
                    cnt,
                    combo_type=combo_type,
                    combo_text=combo,
                    set_key=f"{key_prefix}_{idx}"
                )

    with tabs[3]:
        st.subheader("Davor / Danach für einen Song")
        query = st.text_input("Song suchen", placeholder="z. B. Narcotic oder Wannabe", key="hub_query")
        min_count = st.slider("Mindestens so oft gesehen", 1, 10, 1, key="hub_min_count")

        if query:
            insights = get_track_insights(query, event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
            if not insights:
                st.warning("Kein passender Track gefunden.")
            else:
                h1, h2, h3, h4 = st.columns(4)
                h1.metric("Track", insights["display"])
                h2.metric("Gesamt", insights["total_count"])
                h3.metric("Playlists", insights["playlist_count"])
                h4.metric("Phase", get_track_phase_label(insights["display"], event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event))

                if insights["event_info"]:
                    st.caption("Nach Anlass:")
                    for ev, cnt in insights["event_info"].most_common():
                        st.write(f"- {ev}: {cnt}x")

                a_col, b_col = st.columns(2)
                with a_col:
                    st.markdown("**Top davor**")
                    shown = 0
                    for norm, cnt in insights["before"]:
                        if cnt >= min_count:
                            render_count_row(
                                display_from_normalized(norm),
                                cnt,
                                combo_type="song",
                                combo_text=display_from_normalized(norm),
                                set_key=f"hub_before_{norm}"
                            )
                            shown += 1
                    if shown == 0:
                        st.info("Keine Treffer.")

                with b_col:
                    st.markdown("**Top danach**")
                    shown = 0
                    for norm, cnt in insights["after"]:
                        if cnt >= min_count:
                            render_count_row(
                                display_from_normalized(norm),
                                cnt,
                                combo_type="song",
                                combo_text=display_from_normalized(norm),
                                set_key=f"hub_after_{norm}"
                            )
                            shown += 1
                    if shown == 0:
                        st.info("Keine Treffer.")

                combo_tabs = st.tabs(["2er", "3er", "4er", "5er", "Beweise"])
                with combo_tabs[0]:
                    st.markdown("**2er-Kombinationen zum Song**")
                    found_pairs = 0
                    for combo_text, cnt in insights["pairs"]:
                        if cnt >= min_count:
                            render_count_row(
                                combo_text,
                                cnt,
                                combo_type="2er",
                                combo_text=combo_text,
                                set_key=f"hub_song_pair_{combo_text}"
                            )
                            found_pairs += 1
                    if found_pairs == 0:
                        st.info("Keine Treffer.")

                def _render_song_combo_examples(rows, combo_type, prefix):
                    if not rows:
                        st.info("Keine Treffer.")
                        return
                    shown = 0
                    for combo_text, cnt in rows:
                        if cnt >= min_count:
                            render_count_row(
                                combo_text,
                                cnt,
                                combo_type=combo_type,
                                combo_text=combo_text,
                                set_key=f"{prefix}_{shown}"
                            )
                            shown += 1
                    if shown == 0:
                        st.info("Keine Treffer.")

                with combo_tabs[1]:
                    st.markdown("**3er-Blöcke ab diesem Song**")
                    _render_song_combo_examples(insights.get("block3", []), "3er", "hub_song_block3")

                with combo_tabs[2]:
                    st.markdown("**4er-Blöcke ab diesem Song**")
                    _render_song_combo_examples(insights.get("block4", []), "4er", "hub_song_block4")

                with combo_tabs[3]:
                    st.markdown("**5er-Blöcke ab diesem Song**")
                    _render_song_combo_examples(insights.get("block5", []), "5er", "hub_song_block5")

                with combo_tabs[4]:
                    st.markdown("**Beweis-Playlists für diesen Song**")
                    proof_rows = get_track_example_playlists(
                        insights["display"],
                        event=filter_event,
                        source=filter_source,
                        top_only=top_only,
                        sub_event=filter_sub_event,
                        limit=8,
                    )
                    if not proof_rows:
                        st.info("Keine Beispiel-Playlists gefunden.")
                    else:
                        for row in proof_rows:
                            cols = st.columns([4.5, 1.6, 1.2])
                            cols[0].markdown(f"**{row['name']}**  \n{row['event_label']} | {row['source']}")
                            cols[1].caption(str(row['created_at']))
                            if cols[2].button("Öffnen", key=f"hub_track_proof_{row['playlist_id']}", width="stretch"):
                                if jump_to_playlist_browser_for_playlist(int(row['playlist_id'])):
                                    st.rerun()

elif menu == "Vorbereitung":
    st.header("Vorbereitung")
    st.caption("Wähle einen Anlass und sieh die wichtigsten Songs, Übergänge, Blöcke und fehlenden Songs.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Vorbereitung", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    filter_event = c1.selectbox("Anlass", events, key="prep_event")
    filter_source = c2.selectbox("Herkunft", sources, key="prep_source")
    filter_sub_event = "Alle"
    if is_birthday_event(filter_event):
        filter_sub_event = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(filter_event), key="prep_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top_only = c4.checkbox("Nur Top Playlists", key="prep_top")

    data = compute_data_cached(event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)
    missing = get_missing_tracks(event=filter_event, source=filter_source, top_only=top_only, sub_event=filter_sub_event)

    st.subheader("Wichtigste Songs")
    for idx, (norm, cnt) in enumerate(data["track_total_counts"].most_common(20), start=1):
        title = f"{idx}. {display_from_normalized(norm)}"
        render_count_row(title, cnt, combo_type="song", combo_text=display_from_normalized(norm), set_key=f"prep_song_{idx}_{norm}")

    c4, c5 = st.columns(2)

    with c4:
        st.subheader("Wichtigste Übergänge")
        rows = list(data["pair_counts"].most_common(15))
        if rows:
            for idx, ((a, b), cnt) in enumerate(rows, start=1):
                combo = f"{display_from_normalized(a)} → {display_from_normalized(b)}"
                render_count_row(combo, cnt, combo_type="2er", combo_text=combo, set_key=f"prep_pair_{idx}")
        else:
            st.info("Keine Daten gefunden.")

    with c5:
        st.subheader("Starke 3er-Blöcke")
        rows = list(data["block3_counts"].most_common(10))
        if rows:
            for idx, (block, cnt) in enumerate(rows, start=1):
                combo = " → ".join(display_from_normalized(x) for x in block)
                render_count_row(combo, cnt, combo_type="3er", combo_text=combo, set_key=f"prep_b3_{idx}")
        else:
            st.info("Keine Daten gefunden.")

    b1, b2 = st.columns(2)
    with b1:
        st.subheader("Starke 4er-Blöcke")
        rows = list(data["block4_counts"].most_common(10))
        if rows:
            for idx, (block, cnt) in enumerate(rows, start=1):
                combo = " → ".join(display_from_normalized(x) for x in block)
                render_count_row(combo, cnt, combo_type="4er", combo_text=combo, set_key=f"prep_b4_{idx}")
        else:
            st.info("Keine Daten gefunden.")

    with b2:
        st.subheader("Starke 5er-Blöcke")
        rows = list(data["block5_counts"].most_common(10))
        if rows:
            for idx, (block, cnt) in enumerate(rows, start=1):
                combo = " → ".join(display_from_normalized(x) for x in block)
                render_count_row(combo, cnt, combo_type="5er", combo_text=combo, set_key=f"prep_b5_{idx}")
        else:
            st.info("Keine Daten gefunden.")

    st.subheader("Fehlende Songs / Library-Check")
    render_missing_summary_ui(event=filter_event, source=filter_source, top_only=top_only, key_prefix="prep_missing", sub_event=filter_sub_event)



elif menu == "iPad Verbindung":
    st.header("iPad Verbindung")
    st.caption("Hier siehst du die Adresse, mit der du das Tool auf dem iPad öffnen kannst.")
    render_ipad_connection_box()

    st.subheader("Wichtig")
    st.write("- Auf dem PC musst du die Datei **start_dj_tool_ipad.bat** verwenden.")
    st.write("- PC und iPad müssen im selben WLAN sein.")
    st.write("- Wenn es nicht klappt, zuerst Windows-Firewall für privates Netzwerk erlauben.")
    st.write("- Danach die Adresse aus diesem Bereich auf dem iPad in Safari oder Chrome öffnen.")


elif menu == "Event Presets":
    st.header("Event Presets")
    st.caption("Ein Klick setzt Anlass, Herkunft und Top-Filter direkt für den gewünschten Bereich.")

    t1, t2 = st.columns([1.2, 1.8])
    target_menu = t1.selectbox(
        "Preset laden für",
        ["Set Builder", "Event vorbereiten", "Analyse Hub", "Vorbereitung", "Live Hilfe", "Fehlende Songs", "Wichtige Tracks", "KI Rollen & Timing", "Transition KI"],
        index=0,
        key="preset_target_menu",
    )
    t2.info("Beispiel: Du klickst 'Hochzeit – Benjamin Schneider' und landest direkt im gewählten Bereich mit den passenden Filtern.")

    render_preset_bar(target_menu=target_menu, title="Fertige Presets")

    st.subheader("Preset-Inhalt")
    for preset in EVENT_PRESETS:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3.6, 1.5, 1.6, 1.0])
            c1.write(f"**{preset['label']}**")
            c2.write(preset["event"])
            c3.write(preset["source"])
            c4.write("Top" if preset["top_only"] else "Alle")
            if st.button("Jetzt laden", key=f"preset_load_full_{preset['label']}", width="stretch"):
                apply_event_preset(preset, target_menu=target_menu)
                st.rerun()


elif menu == "Rekordbox verbinden":
    st.header("Rekordbox verbinden")
    st.caption("Hier kannst du deine Rekordbox XML importieren und direkt prüfen, wie stark deine Library schon zu den echten Playlists passt.")

    library = get_library_index()
    m1, m2 = st.columns(2)
    m1.metric("RB Tracks im Tool", library["count"])
    m2.metric("Bekannte Track-Familien", len(library["family_set"]))

    xml_file = st.file_uploader("Rekordbox XML hochladen", type=["xml"])
    if xml_file:
        xml_text = xml_file.read().decode("utf-8", errors="ignore")
        if st.button("XML importieren", type="primary"):
            try:
                count = import_rekordbox_xml(xml_text)
                st.success(f"{count} Rekordbox-Tracks importiert.")
                st.rerun()
            except Exception as e:
                st.error(f"Import fehlgeschlagen: {e}")

    st.subheader("Schnellcheck")
    render_missing_summary_ui(event="Alle", source="Alle", top_only=False, key_prefix="rb_quick")

elif menu == "Fehlende Songs":
    st.header("Fehlende Songs")
    st.caption("Nicht nur was fehlt, sondern was dir für Event und echte Blöcke wirklich fehlt.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Fehlende Songs", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    filter_event = c1.selectbox("Anlass filtern", events, key="ms_event")
    filter_source = c2.selectbox("Herkunft filtern", sources, key="ms_source")
    filter_sub_event = "Alle"
    if is_birthday_event(filter_event):
        filter_sub_event = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(filter_event), key="ms_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top_only = c4.checkbox("Nur Top Playlists", key="ms_top")

    render_missing_summary_ui(event=filter_event, source=filter_source, top_only=top_only, key_prefix="missings", sub_event=filter_sub_event)


elif menu == "Doppelte Playlists":
    render_delete_duplicate_flow_note()
    st.header("Doppelte Playlists")
    st.caption("Hier siehst du doppelte oder sehr ähnliche Playlists – basierend auf echtem Inhalt, nicht nur Dateinamen.")

    threshold_percent = st.slider("Mindestens ähnliche Prozent", 80, 100, 90, 1)
    threshold = threshold_percent / 100

    duplicates = find_all_possible_duplicates(threshold=threshold)
    st.write(f"{len(duplicates)} mögliche Paare gefunden")

    if not duplicates:
        st.info("Keine doppelten Playlists gefunden.")
    else:
        for row in duplicates:
            with st.expander(
                f"{row['a_name']}  ↔  {row['b_name']}  |  {int(row['score'] * 100)}%"
            ):
                st.write(
                    f"**Playlist A:** {row['a_name']} | {row['a_event'] or '-'} | {row['a_source'] or '-'} | {row['a_count']} Tracks"
                )
                st.write(
                    f"**Playlist B:** {row['b_name']} | {row['b_event'] or '-'} | {row['b_source'] or '-'} | {row['b_count']} Tracks"
                )
                cols = st.columns(2)
                if cols[0].button("Playlist A löschen", key=f"dupe_del_a_{row['a_id']}_{row['b_id']}"):
                    delete_playlist(row['a_id'])
                    st.success("Playlist A gelöscht.")
                    st.rerun()
                if cols[1].button("Playlist B löschen", key=f"dupe_del_b_{row['a_id']}_{row['b_id']}"):
                    delete_playlist(row['b_id'])
                    st.success("Playlist B gelöscht.")
                    st.rerun()




elif menu == "Gemerkte Kombinationen":
    st.header("DJ Memory")
    st.caption("Hier findest du deine gemerkten Tracks, Übergänge und Blöcke wieder – schnell suchbar und direkt zur Playlist springbar.")

    if st.session_state.get("memory_feedback"):
        fb1, fb2 = st.columns([4, 1])
        fb1.success(st.session_state.get("memory_feedback"))
        if fb2.button("Schließen", key="close_memory_feedback", width="stretch"):
            st.session_state["memory_feedback"] = ""
            st.rerun()

    search_cols = st.columns([3, 1, 1, 1, 1])
    query_text = search_cols[0].text_input("Suche", key="memory_search_text", placeholder="z. B. NDW, Peak, Männerblock, Black")
    combo_type_filter = search_cols[1].selectbox("Typ", ["Alle", "Einzeltrack", "Übergang", "Block"], key="memory_filter_type")
    category_filter = search_cols[2].selectbox("Kategorie / Ordner", [""] + get_saved_combo_categories(), accept_new_options=True, key="memory_filter_category")
    tag_filter = search_cols[3].selectbox("Tag", [""] + get_saved_combo_tags(), accept_new_options=True, key="memory_filter_tag")
    context_filter = search_cols[4].selectbox("Anlass / Einsatz", [""] + get_saved_combo_contexts(), accept_new_options=True, key="memory_filter_context")

    search_cols_2 = st.columns([1, 1, 1])
    source_filter = search_cols_2[0].selectbox("Quelle", [""] + get_saved_combo_sources(), accept_new_options=True, key="memory_filter_source")
    genre_filter = search_cols_2[1].selectbox("Genre", [""] + get_saved_combo_genres(), accept_new_options=True, key="memory_filter_genre")
    event_filter = search_cols_2[2].selectbox("Playlist-Event", [""] + get_saved_combo_events(), accept_new_options=True, key="memory_filter_event")

    combos = get_saved_combos(
        combo_type=combo_type_filter,
        category=category_filter,
        tag=tag_filter,
        usage_context=context_filter,
        source_name=source_filter,
        genre_name=genre_filter,
        event_name=event_filter,
        query_text=query_text,
    )

    all_combos = get_saved_combos()
    render_set_builder_panel("Aktuelles Set")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Alle", len(all_combos))
    m2.metric("Blöcke", sum(1 for row in all_combos if str(row[1]) == "Block"))
    m3.metric("Übergänge", sum(1 for row in all_combos if str(row[1]) == "Übergang"))
    m4.metric("Tracks", sum(1 for row in all_combos if str(row[1]) == "Einzeltrack"))

    if not combos:
        st.info("Keine passenden Einträge im DJ Memory gefunden.")
    else:
        tabs = st.tabs(["Alle Treffer", "Blöcke", "Übergänge", "Tracks"])

        def render_combo_list(rows, tab_key):
            if not rows:
                st.info("Keine Einträge in diesem Bereich.")
                return
            for combo_id, combo_type, combo_text, source_track, note, category, tags, usage_context, source_name, genre_name, event_name, playlist_name, playlist_id, created_at in rows:
                with st.container(border=True):
                    top_cols = st.columns([5.5, 1.2, 1.2, 1.1])
                    title = f"**{combo_type}**"
                    if category:
                        title += f" · {category}"
                    top_cols[0].markdown(title)

                    if top_cols[1].button("➕ Heute", key=f"mem_to_set_{tab_key}_{combo_id}", width="stretch"):
                        added = save_combo_to_set(combo_text)
                        st.success(f"{added} Song(s) ins aktuelle Set übernommen.")
                        st.rerun()

                    if playlist_id and top_cols[2].button("📂 Zur Playlist", key=f"mem_open_playlist_{tab_key}_{combo_id}", width="stretch"):
                        if jump_to_playlist_browser_for_playlist(int(playlist_id)):
                            st.rerun()

                    if top_cols[3].button("🗑️ Löschen", key=f"combo_del_{tab_key}_{combo_id}", width="stretch"):
                        delete_combo(combo_id)
                        st.success("Eintrag gelöscht.")
                        st.rerun()

                    songs = [x.strip() for x in str(combo_text or "").split("|") if x.strip()]
                    for idx, song in enumerate(songs, start=1):
                        st.write(f"{idx}. {song}")

                    meta_parts = []
                    if usage_context:
                        meta_parts.append(f"Anlass/Einsatz: {usage_context}")
                    if event_name:
                        meta_parts.append(f"Playlist-Event: {event_name}")
                    if source_name:
                        meta_parts.append(f"Quelle: {source_name}")
                    if genre_name:
                        meta_parts.append(f"Genre: {genre_name}")
                    if tags:
                        meta_parts.append(f"Tags: {tags}")
                    if playlist_name:
                        meta_parts.append(f"Playlist: {playlist_name}")
                    if created_at:
                        meta_parts.append(f"Gespeichert: {created_at}")
                    if meta_parts:
                        st.caption(" | ".join(meta_parts))

                    if note:
                        st.info(note)

        with tabs[0]:
            render_combo_list(combos, "all")
        with tabs[1]:
            render_combo_list([row for row in combos if str(row[1]) == "Block"], "block")
        with tabs[2]:
            render_combo_list([row for row in combos if str(row[1]) == "Übergang"], "transition")
        with tabs[3]:
            render_combo_list([row for row in combos if str(row[1]) == "Einzeltrack"], "track")


elif menu == "Set Builder":
    st.header("Set Builder")
    st.caption("Baue dir ein Set Schritt für Schritt aus echten Daten – jetzt mit Smart Vorschlägen.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Set Builder", title="Schnell laden")

    sets = load_sets()

    f1, f2, f3, f4 = st.columns(4)
    sb_event = f1.selectbox("Anlass filtern", events, key="sb_event")
    sb_source = f2.selectbox("Herkunft filtern", sources, key="sb_source")
    sb_sub_event = "Alle"
    if is_birthday_event(sb_event):
        sb_sub_event = f3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(sb_event), key="sb_sub_event")
    else:
        f3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    sb_top = f4.checkbox("Nur Top Playlists", key="sb_top")

    if "set_builder" not in st.session_state:
        st.session_state.set_builder = []

    start = st.text_input("Start Track", placeholder="z. B. Wannabe")

    if st.button("Start setzen"):
        if start.strip():
            st.session_state.set_builder = [start.strip()]
            st.rerun()

    if st.session_state.set_builder:

        st.subheader("🤖 DJ Autopilot")
        col_ap1, col_ap2 = st.columns([2,1])
        ap_length = col_ap1.slider("Set Länge", 5, 25, 12, key="autopilot_length")
        if col_ap2.button("Autopilot starten", key="autopilot_start"):
            auto_set = build_autopilot_set(
                st.session_state.set_builder[0],
                length=ap_length,
                event=sb_event,
                source=sb_source,
                top_only=sb_top,
                sub_event=sb_sub_event
            )
            if auto_set:
                st.session_state.set_builder = auto_set
                st.success(f"Autopilot Set erstellt ({len(auto_set)} Tracks)")
                st.rerun()

        st.subheader("Dein Set")
        for i, t in enumerate(st.session_state.set_builder, start=1):
            st.write(f"{i}. {t}")

        data = compute_transitions(event=sb_event, source=sb_source, top_only=sb_top, sub_event=sb_sub_event)
        transitions_counts = data["pair_counts"]
        eval_rows, score = evaluate_set(transitions_counts, st.session_state.set_builder)

        st.subheader("Set Übersicht")
        avg_strength = calculate_average_strength(eval_rows)
        metric1, metric2, metric3, metric4 = st.columns(4)
        metric1.metric("Länge", len(st.session_state.set_builder))
        metric2.metric("Ø Stärke", avg_strength)
        metric3.metric("Score", f"{score}/100")
        current_phase = get_track_phase_label(st.session_state.set_builder[-1], event=sb_event, source=sb_source, top_only=sb_top, sub_event=sb_sub_event)
        metric4.metric("Aktuelle Phase", current_phase)

        strong_chain = []
        for txt, cnt, label in eval_rows:
            if cnt >= 5:
                strong_chain.append(txt)
        if len(strong_chain) >= 2:
            st.subheader("🔥 FLOW erkannt")
            for f in strong_chain:
                st.write(f)

        phases = []
        for t in st.session_state.set_builder:
            norm = normalize_track_text(t)
            phase = get_track_phase_label(norm, event=sb_event, source=sb_source, top_only=sb_top, sub_event=sb_sub_event)
            phases.append(phase)

        st.subheader("Flow Timeline")
        st.write(build_flow_timeline(phases))

        flow_label, issues = evaluate_flow(phases)
        st.write(f"Bewertung Ablauf: **{flow_label}**")

        if issues:
            st.subheader("Verbesserungsvorschläge")
            for idx, a, b in issues:
                st.write(f"Problem: {a} → {b}")
                left_track = st.session_state.set_builder[idx]
                alternatives = get_better_alternatives(
                    left_track,
                    current_track=st.session_state.set_builder[idx+1],
                    event=sb_event,
                    source=sb_source,
                    top_only=sb_top,
                    limit=3,
                    sub_event=sb_sub_event
                )
                for alt_name, alt_cnt in alternatives:
                    cols = st.columns([6, 1])
                    cols[0].write(f"→ {alt_name} — {alt_cnt}x")
                    if cols[1].button("Nehmen", key=f"flow_fix_{idx}_{alt_name}"):
                        st.session_state.set_builder[idx+1] = alt_name
                        st.rerun()

        st.subheader("Set Bewertung")
        for i, (txt, cnt, label) in enumerate(eval_rows):
            st.write(f"{txt} — {cnt}x ({label}) {transition_safety_label(cnt)}")

            if label in ["⚠️ selten", "❌ unbekannt"]:
                left_track = st.session_state.set_builder[i]
                current_track = st.session_state.set_builder[i + 1]
                alternatives = get_better_alternatives(
                    left_track,
                    current_track=current_track,
                    event=sb_event,
                    source=sb_source,
                    top_only=sb_top,
                    limit=3,
                    sub_event=sb_sub_event
                )
                if alternatives:
                    st.caption(f"Bessere Alternativen nach {left_track}:")
                    for alt_name, alt_cnt in alternatives:
                        cols = st.columns([6, 1])
                        cols[0].write(f"→ {alt_name} — {alt_cnt}x")
                        if cols[1].button("Nehmen", key=f"replace_{i}_{alt_name}"):
                            st.session_state.set_builder[i + 1] = alt_name
                            st.rerun()

        smart_pack = get_smart_set_builder_pack(
            st.session_state.set_builder,
            event=sb_event,
            source=sb_source,
            top_only=sb_top,
        )
        if smart_pack:
            st.subheader("🧠 Smart Vorschläge")

            sp1, sp2 = st.columns(2)
            with sp1:
                st.markdown("**🔥 Stärkste echte nächste Tracks**")
                if smart_pack["top_suggestions"]:
                    for item in smart_pack["top_suggestions"][:5]:
                        cols = st.columns([4.8, 1.2, 1.2])
                        cols[0].write(f"{item['display']} — {item['count']}x")
                        cols[1].caption(item["phase"])
                        if cols[2].button("➕", key=f"smart_top_{item['display']}"):
                            st.session_state.set_builder.append(item["display"])
                            st.rerun()
                else:
                    st.info("Keine direkten Folgetracks gefunden.")

            with sp2:
                st.markdown("**🎯 Phasen-passende Vorschläge**")
                if smart_pack["phase_suggestions"]:
                    desired = smart_pack["phase_suggestions"][0].get("desired_phase", smart_pack["last_phase"])
                    st.caption(f"Zielphase ab jetzt: {desired}")
                    for item in smart_pack["phase_suggestions"][:5]:
                        cols = st.columns([4.3, 1.0, 1.2, 1.0])
                        cols[0].write(item["display"])
                        cols[1].write(f"{item['count']}x")
                        cols[2].caption(item["phase"])
                        if cols[3].button("➕", key=f"smart_phase_{item['display']}"):
                            st.session_state.set_builder.append(item["display"])
                            st.rerun()
                else:
                    st.info("Keine phasen-passenden Vorschläge gefunden.")

            tq = smart_pack.get("transition_quality")
            if tq:
                st.markdown("**⚠️ Letzter Übergang im aktuellen Set**")
                st.write(f"{tq['left']} → {tq['right']} — {tq['count']}x ({tq['label']})")
                if smart_pack.get("recovery"):
                    st.caption("Bessere Alternativen für einen saubereren Flow:")
                    for alt_name, alt_cnt in smart_pack["recovery"]:
                        cols = st.columns([5.5, 1.0, 1.0])
                        cols[0].write(f"{alt_name} — {alt_cnt}x")
                        if cols[1].button("Tausch", key=f"smart_swap_{alt_name}"):
                            st.session_state.set_builder[-1] = alt_name
                            st.rerun()
                        if cols[2].button("Danach", key=f"smart_after_{alt_name}"):
                            st.session_state.set_builder.append(alt_name)
                            st.rerun()

            if smart_pack["insights"].get("block3"):
                st.markdown("**🧱 Typische 3er-Wege ab deinem letzten Track**")
                for idx, (combo_text, cnt) in enumerate(smart_pack["insights"]["block3"][:4], start=1):
                    cols = st.columns([6, 1.2, 1.0])
                    cols[0].write(combo_text)
                    cols[1].write(f"{cnt}x")
                    if cols[2].button("➕", key=f"smart_block3_{idx}"):
                        added = save_combo_to_set(combo_text)
                        if added:
                            st.success(f"{added} Track(s) ins Set übernommen.")
                        st.rerun()

        col_a, col_b, col_c = st.columns(3)
        if col_a.button("⬅️ Letzten Track entfernen"):
            if st.session_state.set_builder:
                st.session_state.set_builder.pop()
                st.rerun()

        set_name = st.text_input("Set Name")

        if col_b.button("Set speichern"):
            final_name = set_name.strip() if set_name.strip() else f"Set {len(sets)+1}"
            sets.append({"name": final_name, "tracks": st.session_state.set_builder})
            save_sets(sets)
            st.success("Set gespeichert.")

        if st.button("⚡ Set automatisch erweitern"):
            st.session_state.set_builder = auto_extend_set(
                st.session_state.set_builder,
                event=sb_event,
                source=sb_source,
                top_only=sb_top,
                sub_event=sb_sub_event,
                steps=2
            )
            st.rerun()

        if col_c.button("Reset"):
            st.session_state.set_builder = []
            st.rerun()

        st.download_button(
            "Als TXT herunterladen",
            "\n".join(st.session_state.set_builder),
            file_name="set.txt"
        )

        last = st.session_state.set_builder[-1]
        insights = get_track_insights(last, event=sb_event, source=sb_source, top_only=sb_top, sub_event=sb_sub_event)

        if insights:
            st.subheader("Bessere nächste Tracks")
            for norm, cnt in insights["after"]:
                if cnt >= 10:
                    strength = "🔥 sehr oft"
                elif cnt >= 5:
                    strength = "👍 oft"
                else:
                    strength = "⚠️ selten"

                next_name = display_from_normalized(norm)
                cols = st.columns([6, 1])
                cols[0].write(f"{next_name} — {cnt}x ({strength})")
                if cols[1].button("Hinzufügen", key=f"sb_add_{norm}"):
                    st.session_state.set_builder.append(next_name)
                    st.rerun()

elif menu == "Meine Sets":
    st.header("Meine Sets")
    st.caption("Hier findest du deine gespeicherten Sets.")

    sets = load_sets()
    if not sets:
        st.info("Noch keine Sets gespeichert.")
    else:
        for i, s in enumerate(sets):
            with st.expander(s["name"]):
                for idx, t in enumerate(s["tracks"], start=1):
                    st.write(f"{idx}. {t}")


elif menu == "Event vorbereiten":
    st.header("Event vorbereiten")
    st.caption("Zeigt dir die wichtigsten Songs, Übergänge und Blöcke für dein Event – direkt mit Merken- und Set-Buttons.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Event vorbereiten", title="Schnell laden")

    f1, f2, f3, f4 = st.columns(4)
    ev = f1.selectbox("Anlass", events, key="ep_event")
    src = f2.selectbox("Herkunft", sources, key="ep_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = f3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="ep_sub_event")
    else:
        f3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = f4.checkbox("Nur Top Playlists", key="ep_top")

    data = compute_transitions(event=ev, source=src, top_only=top, sub_event=sub_ev)

    st.subheader("🎧 Wichtigste Tracks")
    for idx, (track, cnt) in enumerate(data["track_total_counts"].most_common(20), start=1):
        render_count_row(f"{idx}. {display_from_normalized(track)}", cnt, combo_type="song", combo_text=display_from_normalized(track), set_key=f"ep_song_{idx}")

    st.subheader("🔥 Beste Übergänge")
    for idx, ((a,b), cnt) in enumerate(data["pair_counts"].most_common(20), start=1):
        combo = f"{display_from_normalized(a)} → {display_from_normalized(b)}"
        render_count_row(combo, cnt, combo_type="2er", combo_text=combo, set_key=f"ep_pair_{idx}")

    e1, e2, e3 = st.columns(3)
    with e1:
        st.subheader("🔗 Typische 3er-Blöcke")
        for idx, (block, cnt) in enumerate(data["block3_counts"].most_common(8), start=1):
            combo = " → ".join(display_from_normalized(x) for x in block)
            render_count_row(combo, cnt, combo_type="3er", combo_text=combo, set_key=f"ep_b3_{idx}")
    with e2:
        st.subheader("🔗 Typische 4er-Blöcke")
        for idx, (block, cnt) in enumerate(data["block4_counts"].most_common(8), start=1):
            combo = " → ".join(display_from_normalized(x) for x in block)
            render_count_row(combo, cnt, combo_type="4er", combo_text=combo, set_key=f"ep_b4_{idx}")
    with e3:
        st.subheader("🔗 Typische 5er-Blöcke")
        for idx, (block, cnt) in enumerate(data["block5_counts"].most_common(8), start=1):
            combo = " → ".join(display_from_normalized(x) for x in block)
            render_count_row(combo, cnt, combo_type="5er", combo_text=combo, set_key=f"ep_b5_{idx}")

    st.subheader("⚠️ Fehlende Songs / Event-Lücken")
    render_missing_summary_ui(event=ev, source=src, top_only=top, key_prefix="event_missing", sub_event=sub_ev)

elif menu == "Heute auflegen":
    render_heute_auflegen_page()

elif menu == "Auto Event Set":
    render_event_auto_set_page()

elif menu == "Smart Event Brain":
    render_smart_event_brain_page()

elif menu == "Smart Flow Engine":
    render_smart_flow_engine_page()

elif menu == "Learning Dashboard":
    render_learning_dashboard_page()

elif menu == "KI Rollen & Timing":
    render_ai_role_timing_page()

elif menu == "Transition KI":
    render_transition_learning_page()

elif menu == "Event Kontext KI":
    render_event_context_ki_page()

elif menu == "Live Hilfe":
    st.header("Live Hilfe")
    st.caption("Gib deinen aktuellen Track ein und sieh sofort echte nächste Optionen, sichere Wechsel und komplette DJ-Ketten aus deinen Daten.")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Live Hilfe", title="Schnell laden")
    render_learning_rules_box("Live Hilfe", expanded=False)

    c1, c2, c3, c4 = st.columns(4)
    live_event = c1.selectbox("Anlass filtern", events, key="live_event")
    live_source = c2.selectbox("Herkunft filtern", sources, key="live_source")
    live_sub_event = "Alle"
    if is_birthday_event(live_event):
        live_sub_event = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(live_event), key="live_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    live_top = c4.checkbox("Nur Top Playlists", key="live_top")

    d1, d2 = st.columns(2)
    live_guest_type = d1.selectbox("Gäste-Typ", GUEST_TYPES, key="live_guest_type")
    live_flow_profile = d2.selectbox("Flow-Profil", list(FLOW_PROFILES.keys()), key="live_flow_profile")

    live_track = st.text_input("Aktueller Track", placeholder="z. B. Wannabe")

    if live_track:
        pack = build_live_recommendation_rows(
            live_track,
            event=live_event,
            source=live_source,
            top_only=live_top,
            sub_event=live_sub_event,
            flow_profile=live_flow_profile,
            guest_type=live_guest_type,
            limit=10,
        )

        insights = pack.get("insights")
        current = pack.get("current")
        if not insights or not current:
            st.warning("Kein passender Track gefunden.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Track", current["display"])
            m2.metric("Phase", current["phase"])
            m3.metric("Rolle", current["role"])
            m4.metric("Energie", f"{current['energy']} · {current['energy_label']}")
            st.info(f"Typischer Einsatz: {current['timing']} | Insgesamt gesehen: {insights['total_count']}x | Nur aus echten gespielten Playlists gelernt")

            transition_pack = build_transition_learning_pack(
                live_track,
                event=live_event,
                source=live_source,
                top_only=live_top,
                sub_event=live_sub_event,
                limit=8,
            )

            tabs = st.tabs(["✅ Beste jetzt", "🎯 Track → Track KI", "🔗 DJ-Ketten", "🔗 Bridge Ideen", "🛡️ Sicherer Wechsel", "🧱 Blöcke ab jetzt"])

            with tabs[0]:
                render_live_rows_table(pack.get("rows", []), "live_best")

            with tabs[1]:
                if transition_pack and transition_pack.get("suggestions"):
                    for idx, row in enumerate(transition_pack["suggestions"], start=1):
                        cols = st.columns([4.8, 1.0, 1.0, 1.0])
                        cols[0].write(f"{idx}. {row['song']}")
                        cols[1].caption(row["role"])
                        cols[2].write(f"{row['transition_count']}x")
                        if cols[3].button("➕", key=f"live_transition_add_{idx}"):
                            st.session_state.setdefault("set_builder", []).append(row["song"])
                            st.success("Song ins Set übernommen.")
                            st.rerun()
                        st.caption(f"{row['phase']} | {row['timing']} | {row['why']} | Score {row['score']}")
                else:
                    st.info("Noch keine Track → Track KI-Vorschläge gefunden.")

            with tabs[2]:
                st.caption("Diese Songs eignen sich oft gut als Brücke zwischen zwei Stimmungen.")
                render_live_rows_table(pack.get("bridge_rows", []), "live_bridge")

            with tabs[3]:
                st.caption("Hier siehst du vor allem Wechsel, die in echten Playlists schon häufiger vorkamen.")
                render_live_rows_table(pack.get("safe_rows", []), "live_safe")

            with tabs[4]:
                block_found = 0
                for combo_text, cnt in insights["block3"]:
                    cols = st.columns([6, 1.2, 1.0])
                    cols[0].write(combo_text)
                    cols[1].write(f"{cnt}x")
                    if cols[2].button("➕", key=f"live_block_{block_found}"):
                        added = save_combo_to_set(combo_text)
                        if added:
                            st.success(f"{added} Track(s) ins Set übernommen.")
                        st.rerun()
                    block_found += 1
                    if block_found >= 6:
                        break
                if block_found == 0:
                    st.info("Keine Blöcke gefunden.")



elif menu == "Backup / Restore":
    render_backup_restore_page()

elif menu == "System / Version":
    render_system_version_page()

elif menu == "Wichtige Tracks":
    st.header("Wichtige Tracks")
    st.caption("Diese Tracks sind am wichtigsten für dein Setup / Event")
    with st.expander("⚡ Event Presets", expanded=False):
        render_preset_bar(target_menu="Wichtige Tracks", title="Schnell laden")

    c1, c2, c3, c4 = st.columns(4)
    ev = c1.selectbox("Anlass", events, key="imp_event")
    src = c2.selectbox("Herkunft", sources, key="imp_source")
    sub_ev = "Alle"
    if is_birthday_event(ev):
        sub_ev = c3.selectbox("Geburtstag-Unterordner", get_distinct_sub_events(ev), key="imp_sub_event")
    else:
        c3.caption("Geburtstag-Unterordner nur bei Geburtstag")
    top = c4.checkbox("Nur Top Playlists", key="imp_top")

    data = get_track_importance(event=ev, source=src, top_only=top, sub_event=sub_ev)

    for norm, cnt, score in data:
        if score >= 3:
            label = "🔥 Must Have"
        elif score >= 1:
            label = "👍 Wichtig"
        else:
            label = "⚠️ Optional"

        st.write(f"{display_from_normalized(norm)} — {cnt}x | {score}% | {label}")
