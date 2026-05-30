
import sqlite3
import os
import pytest
from unittest.mock import patch, MagicMock

# Assuming config.py is in the parent directory or accessible via PYTHONPATH
# For testing, we'll mock DB_PATH or use a temporary one
from database import init_db, get_connection, _run_migrations

# Use a temporary database path for testing
TEST_DB_PATH = 'test_tennis_predictor.db'

@pytest.fixture(scope='function')
def temp_db():
    """Fixture to create and tear down a temporary database for testing."""
    original_db_path = os.environ.get('DB_PATH')
    os.environ['DB_PATH'] = TEST_DB_PATH

    # Ensure the directory exists
    os.makedirs(os.path.dirname(TEST_DB_PATH), exist_ok=True)

    # Initialize a clean database for each test
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_db()

    yield # This is where the test runs

    # Clean up after the test
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    if original_db_path:
        os.environ['DB_PATH'] = original_db_path
    else:
        del os.environ['DB_PATH']

def test_init_db_creates_tables(temp_db):
    """Test that init_db creates all necessary tables."""
    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]

    expected_tables = [
        'matches', 'matches_2026', 'players_rankings', 'predictions',
        'elo_ratings', 'algo_performance', 'tournament_surfaces', 'match_features'
    ]

    for table in expected_tables:
        assert table in tables, f"Table {table} was not created."

    conn.close()

def test_get_connection_returns_valid_connection(temp_db):
    """Test that get_connection returns a valid SQLite connection."""
    conn = get_connection()
    assert isinstance(conn, sqlite3.Connection)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result == (1,)
    except sqlite3.Error as e:
        pytest.fail(f"Could not execute a simple query, connection might be invalid: {e}")
    finally:
        conn.close()

def test_run_migrations_adds_new_columns(temp_db):
    """
    Test that _run_migrations correctly adds new columns without failing on existing ones.
    This test will modify the database schema temporarily.
    """
    conn = sqlite3.connect(TEST_DB_PATH)
    c = conn.cursor()

    # Verify a column that should be added by migration is present
    c.execute("PRAGMA table_info(predictions);")
    columns = [col[1] for col in c.fetchall()]
    assert 'surface' in columns
    assert 'p1_rank' in columns
    assert 'odds_p1' in columns
    assert 'sent_in_email' in columns

    # Ensure running migrations again doesn't cause errors
    try:
        _run_migrations(c)
        conn.commit()
    except sqlite3.OperationalError as e:
        pytest.fail(f"_run_migrations failed on re-run: {e}")

    conn.close()

