#!/usr/bin/env python3
"""Initialize SQLite database for database.

This script is designed to be **idempotent**:
- It can be run multiple times without failing.
- It creates required tables if they do not exist.
- It applies minimal "migration" logic for older databases by adding missing columns
  when it is safe to do so (via `ALTER TABLE ... ADD COLUMN`).

Current required application tables:
- app_info: basic metadata key/value store
- users: sample table (kept from template)
- notes: Simple Notes application notes table

notes schema requirement:
    notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
"""

import os
import sqlite3

DB_NAME = "myapp.db"
DB_USER = "kaviasqlite"  # Not used for SQLite, but kept for consistency
DB_PASSWORD = "kaviadefaultpassword"  # Not used for SQLite, but kept for consistency
DB_PORT = "5000"  # Not used for SQLite, but kept for consistency


def _get_existing_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    """Return a set of column names for a given table (empty if table does not exist)."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    if cursor.fetchone() is None:
        return set()

    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """Return True if table exists."""
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _ensure_notes_schema(cursor: sqlite3.Cursor) -> None:
    """Create or migrate the notes table to match the required schema.

    Migration strategy:
    - If notes doesn't exist: create it with the required schema.
    - If it exists: add any missing columns that are safe to add via ALTER TABLE.
      (SQLite supports ADD COLUMN but not full column alterations.)
    """
    if not _table_exists(cursor, "notes"):
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        return

    # Minimal migration: add missing columns if they somehow don't exist.
    existing_cols = _get_existing_columns(cursor, "notes")

    # Note: Adding NOT NULL columns to an existing table can fail if no DEFAULT is provided
    # and there are existing rows. We therefore add missing columns as NULLable with a default
    # where appropriate to keep the migration safe and idempotent.
    #
    # This ensures repeated runs won't fail and existing DBs won't break.
    if "title" not in existing_cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN title TEXT")
    if "content" not in existing_cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN content TEXT")
    if "created_at" not in existing_cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN created_at TEXT")
    if "updated_at" not in existing_cols:
        cursor.execute("ALTER TABLE notes ADD COLUMN updated_at TEXT")


print("Starting SQLite setup...")

# Check if database already exists
db_exists = os.path.exists(DB_NAME)
if db_exists:
    print(f"SQLite database already exists at {DB_NAME}")
    # Verify it's accessible
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("SELECT 1")
        conn.close()
        print("Database is accessible and working.")
    except Exception as e:
        print(f"Warning: Database exists but may be corrupted: {e}")
else:
    print("Creating new SQLite database...")

# Create/open database and ensure schema
conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

# Create initial schema
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS app_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL,
        value TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""
)

# Create a sample users table as an example
cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""
)

# Ensure notes table exists + migrate if needed
_ensure_notes_schema(cursor)

# Insert initial data (idempotent)
cursor.execute(
    "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
    ("project_name", "database"),
)
cursor.execute(
    "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
    ("version", "0.1.0"),
)
cursor.execute(
    "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
    ("author", "John Doe"),
)
cursor.execute(
    "INSERT OR REPLACE INTO app_info (key, value) VALUES (?, ?)",
    ("description", ""),
)

conn.commit()

# Get database statistics
cursor.execute(
    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
)
table_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM app_info")
record_count = cursor.fetchone()[0]

conn.close()

# Save connection information to a file
current_dir = os.getcwd()
connection_string = f"sqlite:///{current_dir}/{DB_NAME}"

try:
    with open("db_connection.txt", "w", encoding="utf-8") as f:
        f.write("# SQLite connection methods:\n")
        f.write(f"# Python: sqlite3.connect('{DB_NAME}')\n")
        f.write(f"# Connection string: {connection_string}\n")
        f.write(f"# File path: {current_dir}/{DB_NAME}\n")
    print("Connection information saved to db_connection.txt")
except Exception as e:
    print(f"Warning: Could not save connection info: {e}")

# Create environment variables file for Node.js viewer
db_path = os.path.abspath(DB_NAME)

# Ensure db_visualizer directory exists
if not os.path.exists("db_visualizer"):
    os.makedirs("db_visualizer", exist_ok=True)
    print("Created db_visualizer directory")

try:
    with open("db_visualizer/sqlite.env", "w", encoding="utf-8") as f:
        f.write(f'export SQLITE_DB="{db_path}"\n')
    print("Environment variables saved to db_visualizer/sqlite.env")
except Exception as e:
    print(f"Warning: Could not save environment variables: {e}")

print("\nSQLite setup complete!")
print(f"Database: {DB_NAME}")
print(f"Location: {current_dir}/{DB_NAME}")
print("")

print("To use with Node.js viewer, run: source db_visualizer/sqlite.env")

print("\nTo connect to the database, use one of the following methods:")
print(f"1. Python: sqlite3.connect('{DB_NAME}')")
print(f"2. Connection string: {connection_string}")
print(f"3. Direct file access: {current_dir}/{DB_NAME}")
print("")

print("Database statistics:")
print(f"  Tables: {table_count}")
print(f"  App info records: {record_count}")

# If sqlite3 CLI is available, show how to use it
try:
    import subprocess

    result = subprocess.run(["which", "sqlite3"], capture_output=True, text=True)
    if result.returncode == 0:
        print("")
        print("SQLite CLI is available. You can also use:")
        print(f"  sqlite3 {DB_NAME}")
except Exception:
    pass

# Exit successfully
print("\nScript completed successfully.")
