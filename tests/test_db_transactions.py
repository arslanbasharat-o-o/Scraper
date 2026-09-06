import os
import pytest
import sqlite3
from unittest.mock import patch
from database import DatabaseManager

def test_save_fetch_history_rolls_back_on_item_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)

    # We will pass invalid items to force an error during item insertion
    urls = ["https://example.com"]
    # This item doesn't have the expected dictionary structure and will raise AttributeError/TypeError
    # depending on how _extract_price_fields handles an integer. Actually let's use a MagicMock that raises an exception.
    class BadItem:
        def __init__(self):
            raise ValueError("Intentional error for test")

    with patch.object(db, '_extract_price_fields', side_effect=ValueError("Simulated DB Error")):
        result = db.save_fetch_history("12345", urls, [{"url": "foo"}], {})

    assert result is False

    # Verify transaction rolled back the history insertion
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM fetch_history WHERE id = '12345'")
    assert cursor.fetchone()[0] == 0
    conn.close()

def test_replace_automation_job_targets_rolls_back_on_error(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)

    # Create a job first
    job = db.save_automation_job({"name": "Test Job", "category_query": "foo", "scraper_key": "standard"})
    assert job is not None
    job_id = job["id"]

    # Replace targets - valid
    db.replace_automation_job_targets(job_id, [{"url": "https://example.com/1", "active": True}])

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM automation_job_targets WHERE job_id = ?", (job_id,))
    assert cursor.fetchone()[0] == 1

    # Try to replace with invalid targets that cause an error (e.g., simulating DB failure)
    with patch.object(db, 'get_connection', side_effect=Exception("Simulated connection error")):
        targets = db.replace_automation_job_targets(job_id, [{"url": "https://example.com/2", "active": True}])
        assert targets == []

    # Also test transaction rollback inside the function
    # We mock _normalize_automation_url to raise after DELETE happens, if it happens earlier we can mock cursor.execute
    # But wait, cursor.execute for INSERT happens after DELETE.
    # Let's mock conn.commit to raise an error

    real_get_connection = db.get_connection
    def mock_get_connection():
        conn = real_get_connection()
        original_commit = conn.commit
        def raising_commit():
            raise sqlite3.OperationalError("Simulated commit error")
        conn.commit = raising_commit
        return conn

    with patch.object(db, 'get_connection', side_effect=mock_get_connection):
        result = db.replace_automation_job_targets(job_id, [{"url": "https://example.com/2", "active": True}])
        assert result == []

    # Verify rollback happened: the original target should still exist
    cursor.execute("SELECT url FROM automation_job_targets WHERE job_id = ?", (job_id,))
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "https://example.com/1"
    conn.close()

def test_schema_version_table_exists(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT version, description FROM _schema_version WHERE version = 1")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == 1
    assert "baseline" in row[1].lower()
    conn.close()

def test_save_automation_run_product_details_batch(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)
    job = db.save_automation_job({
        "name": "Batch Test Job",
        "category_query": "screens",
        "scraper_key": "standard",
        "interval_minutes": 1440,
        "enabled": True,
    })
    assert job is not None
    run = db.create_automation_run(job["id"], target_urls=["https://example.com/target"])
    assert run is not None
    run_id = run["id"]

    batch_data = [
        ({"url": f"https://example.com/product-{i}", "sku": f"SKU-{i}", "title": f"Product {i}"}, f"https://example.com/product-{i}")
        for i in range(10)
    ]
    saved_count = db.save_automation_run_product_details_batch(run_id, batch_data)
    assert saved_count == 10

    checkpoints = db.get_automation_run_product_details(run_id)
    assert len(checkpoints) == 10
    for i in range(10):
        key = db._normalize_automation_url(f"https://example.com/product-{i}")
        assert key in checkpoints
        assert checkpoints[key].get("sku") == f"SKU-{i}"
