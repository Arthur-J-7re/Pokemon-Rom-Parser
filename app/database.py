import sqlite3
from pathlib import Path


def get_db_path(data_dir: Path) -> Path:
    return data_dir / "pokerando.db"


def table_has_column(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    """Check if a table has a specific column"""
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in c.fetchall()]
    return column_name in columns


def add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, column_def: str):
    """Add a column to a table if it doesn't exist"""
    if not table_has_column(conn, table_name, column_name):
        c = conn.cursor()
        c.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        conn.commit()


def migrate_db(db_path: Path):
    """Handle schema migrations for existing databases"""
    conn = sqlite3.connect(db_path)
    
    # Add missing columns to journey_entries if it exists
    if table_has_column(conn, "journey_entries", "id"):  # table exists
        add_column_if_missing(conn, "journey_entries", "location", "TEXT")
        add_column_if_missing(conn, "journey_entries", "capture_zone", "TEXT")
        add_column_if_missing(conn, "journey_entries", "destination", "TEXT")
        add_column_if_missing(conn, "journey_entries", "swapped_pokemon", "TEXT")
        add_column_if_missing(conn, "journey_entries", "trainer_name", "TEXT")
        add_column_if_missing(conn, "journey_entries", "trainer_class", "TEXT")
        add_column_if_missing(conn, "journey_entries", "trainer_id", "INT")
        add_column_if_missing(conn, "journey_entries", "trainer_team", "TEXT")
        add_column_if_missing(conn, "journey_entries", "deaths_in_battle", "TEXT")
        add_column_if_missing(conn, "journey_entries", "evolved_to", "TEXT")
    
    # Add nickname column to pokemon_state if needed
    if table_has_column(conn, "pokemon_state", "id"):  # table exists
        add_column_if_missing(conn, "pokemon_state", "nickname", "TEXT")
    
    conn.close()


def init_db(db_path: Path, reset: bool = False):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    if reset:
        for t in ["meta","base_stats","movesets","trainers","wild_sets","wild_pokemon",
                  "pickup_items","shops","shop_items","trades","tms","tm_compat","evolutions",
                  "adventures","journey_entries","pokemon_state"]:
            c.execute(f"DROP TABLE IF EXISTS {t}")

    c.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS adventures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        log_file TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        lang TEXT DEFAULT 'fr',
        active BOOLEAN DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS pokemon_state (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL,
        pokemon_name TEXT NOT NULL,
        pokemon_level INT,
        nickname TEXT,
        status TEXT DEFAULT 'team',
        team_position INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(adventure_id) REFERENCES adventures(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS journey_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adventure_id INTEGER NOT NULL,
        entry_type TEXT NOT NULL,
        pokemon_name TEXT,
        pokemon_level INT,
        evolved_to TEXT,
        location TEXT,
        capture_zone TEXT,
        destination TEXT,
        swapped_pokemon TEXT,
        trainer_name TEXT,
        trainer_class TEXT,
        trainer_id INT,
        trainer_team TEXT,
        deaths_in_battle TEXT,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(adventure_id) REFERENCES adventures(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS base_stats (
        num INTEGER PRIMARY KEY, name TEXT, type TEXT,
        hp INT, atk INT, def_ INT, spa INT, spd INT, spe INT,
        ability1 TEXT, ability2 TEXT, item TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS movesets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, evolves_to TEXT, level_moves TEXT, egg_moves TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS trainers (
        id INTEGER PRIMARY KEY, class TEXT, pokemon TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS wild_sets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_num INT, location TEXT, type TEXT, rate INT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS wild_pokemon (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        set_id INT, name TEXT, level INT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS pickup_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level_range TEXT, item TEXT, chance INT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS shops (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, shop_id INT, item TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        give TEXT, receive_nick TEXT, receive TEXT,
        give2 TEXT, receive_nick2 TEXT, receive2 TEXT)""")
    c.execute("CREATE TABLE IF NOT EXISTS tms (tm TEXT PRIMARY KEY, move TEXT)")
    c.execute("""CREATE TABLE IF NOT EXISTS tm_compat (
        id INTEGER PRIMARY KEY AUTOINCREMENT, pokemon_name TEXT, tm TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS evolutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_poke TEXT, to_poke TEXT, method TEXT)""")
    conn.commit()
    conn.close()
    
    # Run migrations for existing databases
    migrate_db(db_path)
