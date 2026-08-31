"""
Database module for Parts Extractor
Handles persistent storage of scraping history and items
"""

import sqlite3
import json
import datetime
import re
import uuid
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import asdict
import threading
import pytz
import os
import shutil

from scrapers import SCRAPER_CONFIG, detect_scraper_key, get_db_filename, get_db_key, split_urls_by_scraper

# Thread-local storage for database connections
_local = threading.local()

# Pakistan timezone for consistent handling
PAKISTAN_TZ = pytz.timezone('Asia/Karachi')

def get_pakistan_time(dt=None):
    """Get current time in Pakistan timezone or convert a datetime to Pakistan timezone"""
    if dt is None:
        return datetime.datetime.now(PAKISTAN_TZ)
    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(PAKISTAN_TZ)

def utc_to_pakistan(utc_dt):
    """Convert UTC datetime to Pakistan timezone"""
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    return utc_dt.astimezone(PAKISTAN_TZ)

class DatabaseManager:
    def __init__(self, db_path: str = None):
        configured_path = db_path or os.environ.get("DATABASE_PATH")
        if configured_path:
            self.db_path = configured_path
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, "mobilesentrix.db")

        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        self._connection_key = os.path.abspath(self.db_path)

        self.init_database()

    def get_connection(self):
        """Get thread-local database connection"""
        connections = getattr(_local, 'connections', None)
        if connections is None:
            connections = {}
            _local.connections = connections

        conn = connections.get(self._connection_key)
        if conn is None:
            conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            try:
                conn.execute('PRAGMA foreign_keys = ON')
                conn.execute('PRAGMA busy_timeout = 30000')
                conn.execute('PRAGMA journal_mode = WAL')
                conn.execute('PRAGMA synchronous = NORMAL')
            except Exception:
                pass
            connections[self._connection_key] = conn
        return conn

    def close_connection(self):
        """Close the thread-local database connection, if one exists."""
        connections = getattr(_local, 'connections', None)
        if not connections:
            return

        conn = connections.get(self._connection_key)
        if conn is None:
            return

        try:
            if conn.in_transaction:
                conn.rollback()
        except Exception:
            pass

        try:
            conn.close()
        finally:
            connections.pop(self._connection_key, None)
            if not connections and hasattr(_local, 'connections'):
                delattr(_local, 'connections')

    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Create schema version tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS _schema_version (
                version INTEGER PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        ''')
        cursor.execute('INSERT OR IGNORE INTO _schema_version (version, description) VALUES (1, "Initial baseline")')

        # Create fetch_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fetch_history (
                id TEXT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                urls TEXT NOT NULL,  -- JSON array of URLs
                urls_key TEXT,
                items_count INTEGER NOT NULL,
                rules TEXT NOT NULL,  -- JSON object with scraping rules
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create items table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id TEXT NOT NULL,
                url TEXT NOT NULL,
                site TEXT,
                title TEXT,
                price_value REAL,
                price_currency TEXT,
                price_text TEXT,
                discounted_value REAL,
                discounted_formatted TEXT,
                original_formatted TEXT,
                sku TEXT,
                stock_status TEXT,
                description TEXT,
                extra_json TEXT,
                source TEXT,
                image_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (history_id) REFERENCES fetch_history (id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist_items (
                url TEXT PRIMARY KEY,
                site TEXT,
                title TEXT,
                price_value REAL,
                price_currency TEXT,
                price_text TEXT,
                discounted_value REAL,
                discounted_formatted TEXT,
                original_formatted TEXT,
                sku TEXT,
                stock_status TEXT,
                description TEXT,
                extra_json TEXT,
                source TEXT,
                image_url TEXT,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS automation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                scraper_key TEXT NOT NULL,
                category_query TEXT NOT NULL,
                root_url TEXT NOT NULL,
                interval_minutes INTEGER NOT NULL DEFAULT 1440,
                enabled INTEGER NOT NULL DEFAULT 1,
                auto_discover INTEGER NOT NULL DEFAULT 1,
                crawl_pagination INTEGER NOT NULL DEFAULT 1,
                max_pages INTEGER NOT NULL DEFAULT 10,
                delay_ms INTEGER NOT NULL DEFAULT 50,
                retries INTEGER NOT NULL DEFAULT 1,
                verify_ssl INTEGER NOT NULL DEFAULT 1,
                use_parallel INTEGER NOT NULL DEFAULT 1,
                enrich_details INTEGER NOT NULL DEFAULT 1,
                drop_pct REAL NOT NULL DEFAULT 10,
                rules_json TEXT NOT NULL DEFAULT '{}',
                last_discovery_at DATETIME,
                last_run_at DATETIME,
                next_run_at DATETIME,
                last_status TEXT NOT NULL DEFAULT 'idle',
                last_error TEXT DEFAULT '',
                last_history_ids TEXT DEFAULT '[]',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS automation_job_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                group_label TEXT,
                url TEXT NOT NULL,
                url_key TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                position INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY (job_id) REFERENCES automation_jobs (id) ON DELETE CASCADE,
                UNIQUE (job_id, url_key)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS automation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                run_uuid TEXT NOT NULL UNIQUE,
                trigger_type TEXT NOT NULL DEFAULT 'manual',
                status TEXT NOT NULL DEFAULT 'running',
                started_at DATETIME NOT NULL,
                completed_at DATETIME,
                current_history_id TEXT,
                previous_history_id TEXT,
                target_urls_json TEXT DEFAULT '[]',
                items_count INTEGER NOT NULL DEFAULT 0,
                summary_json TEXT DEFAULT '{}',
                error_text TEXT DEFAULT '',
                created_at DATETIME NOT NULL,
                FOREIGN KEY (job_id) REFERENCES automation_jobs (id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS automation_run_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                item_index INTEGER NOT NULL,
                item_json TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (run_id) REFERENCES automation_runs (id) ON DELETE CASCADE,
                UNIQUE (run_id, item_index)
            )
        ''')

        # ===== AUTO-SCRAPER TABLES =====

        # Scraper runs tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed, stopped
                started_at DATETIME NOT NULL,
                completed_at DATETIME,
                total_brands INTEGER DEFAULT 0,
                total_categories INTEGER DEFAULT 0,
                total_models INTEGER DEFAULT 0,
                total_products INTEGER DEFAULT 0,
                new_products INTEGER DEFAULT 0,
                updated_products INTEGER DEFAULT 0,
                errors_count INTEGER DEFAULT 0,
                current_brand TEXT,
                current_category TEXT,
                current_model TEXT,
                checkpoint TEXT,  -- JSON for resume capability
                error_log TEXT,  -- JSON array of errors
                config TEXT  -- JSON with schedule config
            )
        ''')

        # Brands table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_brands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Categories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brand_id) REFERENCES ms_brands (id) ON DELETE CASCADE,
                UNIQUE (brand_id, slug)
            )
        ''')

        # Models table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES ms_categories (id) ON DELETE CASCADE,
                UNIQUE (category_id, slug)
            )
        ''')

        # Products table - the main data store
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id INTEGER NOT NULL,
                sku TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                price REAL,
                stock_status TEXT,  -- in_stock, out_of_stock, back_order
                availability TEXT,
                condition TEXT,  -- New, OEM, Refurbished, etc.
                product_url TEXT NOT NULL UNIQUE,
                image_urls TEXT,  -- JSON array
                variant_details TEXT,  -- JSON object (color, storage, grade, etc.)
                compatibility TEXT,  -- JSON array of compatible models
                bulk_discounts TEXT,  -- JSON object
                last_scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (model_id) REFERENCES ms_models (id) ON DELETE CASCADE
            )
        ''')

        # Users table for multi-user auth
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Price history for tracking changes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ms_price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                price REAL NOT NULL,
                stock_status TEXT,
                recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES ms_products (id) ON DELETE CASCADE
            )
        ''')

        # Ensure schema migrations on existing databases before creating indexes.
        self._ensure_history_columns()
        self._ensure_item_columns()
        self._ensure_watchlist_columns()

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON fetch_history (timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_urls_key ON fetch_history (urls_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_history_id ON items (history_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_url ON items (url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_site ON items (site)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_sku ON items (sku)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_site ON watchlist_items (site)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_watchlist_updated_at ON watchlist_items (updated_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_jobs_enabled ON automation_jobs (enabled)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_jobs_next_run ON automation_jobs (next_run_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_targets_job ON automation_job_targets (job_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_runs_job ON automation_runs (job_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_runs_started ON automation_runs (started_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_automation_run_items_run ON automation_run_items (run_id, item_index)')

        # Auto-scraper indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_runs_status ON scraper_runs (status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_runs_started ON scraper_runs (started_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_brands_slug ON ms_brands (slug)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_categories_brand ON ms_categories (brand_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_models_category ON ms_models (category_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_products_model ON ms_products (model_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_products_sku ON ms_products (sku)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_products_url ON ms_products (product_url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_price_history_product ON ms_price_history (product_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ms_price_history_recorded ON ms_price_history (recorded_at)')

        conn.commit()
        self._bootstrap_auth()
        self._backfill_urls_key()

    def _ensure_column(self, table: str, column: str, definition: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f'PRAGMA table_info({table})')
        existing = {row['name'] for row in cursor.fetchall()}
        if column in existing:
            return
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
        conn.commit()

    def _ensure_history_columns(self):
        self._ensure_column('fetch_history', 'urls_key', 'TEXT')

    def _ensure_item_columns(self):
        self._ensure_column('items', 'sku', 'TEXT')
        self._ensure_column('items', 'stock_status', 'TEXT')
        self._ensure_column('items', 'description', 'TEXT')
        self._ensure_column('items', 'extra_json', 'TEXT')

    def _ensure_watchlist_columns(self):
        self._ensure_column('watchlist_items', 'site', 'TEXT')
        self._ensure_column('watchlist_items', 'title', 'TEXT')
        self._ensure_column('watchlist_items', 'price_value', 'REAL')
        self._ensure_column('watchlist_items', 'price_currency', 'TEXT')
        self._ensure_column('watchlist_items', 'price_text', 'TEXT')
        self._ensure_column('watchlist_items', 'discounted_value', 'REAL')
        self._ensure_column('watchlist_items', 'discounted_formatted', 'TEXT')
        self._ensure_column('watchlist_items', 'original_formatted', 'TEXT')
        self._ensure_column('watchlist_items', 'sku', 'TEXT')
        self._ensure_column('watchlist_items', 'stock_status', 'TEXT')
        self._ensure_column('watchlist_items', 'description', 'TEXT')
        self._ensure_column('watchlist_items', 'extra_json', 'TEXT')
        self._ensure_column('watchlist_items', 'source', 'TEXT')
        self._ensure_column('watchlist_items', 'image_url', 'TEXT')
        self._ensure_column('watchlist_items', 'created_at', 'DATETIME')
        self._ensure_column('watchlist_items', 'updated_at', 'DATETIME')

    @staticmethod
    def build_urls_key(urls: List[str]) -> str:
        normalized = sorted({str(url or '').strip() for url in urls if str(url or '').strip()})
        return json.dumps(normalized, separators=(',', ':'))

    def _backfill_urls_key(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, urls FROM fetch_history WHERE urls_key IS NULL OR urls_key = ""')
            rows = cursor.fetchall()
            for row in rows:
                try:
                    urls = json.loads(row['urls'])
                except Exception:
                    urls = []
                cursor.execute(
                    'UPDATE fetch_history SET urls_key = ? WHERE id = ?',
                    (self.build_urls_key(urls), row['id'])
                )
            if rows:
                conn.commit()
        except Exception as e:
            print(f"Error backfilling urls_key: {e}")

    @staticmethod
    def _coerce_price_number(*values) -> Optional[float]:
        """Extract a positive numeric price from mixed numeric/formatted inputs."""
        for value in values:
            if value is None:
                continue
            if isinstance(value, (int, float)):
                number = float(value)
                if number > 0:
                    return round(number, 2)
                continue
            clean = re.sub(r'[^\d.]', '', str(value))
            if not clean:
                continue
            try:
                number = float(clean)
            except ValueError:
                continue
            if number > 0:
                return round(number, 2)
        return None

    @staticmethod
    def _detect_currency(*values) -> str:
        for value in values:
            text = str(value or '')
            if 'CA$' in text.upper():
                return 'CAD'
            if '$' in text:
                return 'USD'
        return ''

    def _extract_price_fields(self, item_dict: Dict[str, Any]) -> Tuple[Optional[float], str, str, Optional[float], str, str]:
        """Normalize item pricing across standard and specialized scraper shapes."""
        price_text = str(
            item_dict.get('price_text')
            or item_dict.get('original_formatted')
            or item_dict.get('discounted_formatted')
            or ''
        )
        original_formatted = str(
            item_dict.get('original_formatted')
            or item_dict.get('price_text')
            or item_dict.get('discounted_formatted')
            or ''
        )
        discounted_formatted = str(
            item_dict.get('discounted_formatted')
            or item_dict.get('original_formatted')
            or item_dict.get('price_text')
            or ''
        )

        price_value = self._coerce_price_number(
            item_dict.get('price_value'),
            item_dict.get('original'),
            original_formatted,
            price_text,
        )
        discounted_value = self._coerce_price_number(
            item_dict.get('discounted_value'),
            item_dict.get('discounted'),
            discounted_formatted,
            original_formatted,
            price_text,
        )

        if price_value is None:
            price_value = discounted_value
        if discounted_value is None:
            discounted_value = price_value

        price_currency = str(
            item_dict.get('price_currency')
            or self._detect_currency(price_text, original_formatted, discounted_formatted)
        )

        return (
            price_value,
            price_currency,
            price_text,
            discounted_value,
            discounted_formatted,
            original_formatted,
        )

    def _extract_item_metadata(self, item_dict: Dict[str, Any]) -> Tuple[str, str, str, str]:
        extra = item_dict.get('extra') if isinstance(item_dict.get('extra'), dict) else {}
        sku = str(item_dict.get('sku') or extra.get('sku') or '').strip()
        stock_status = str(item_dict.get('stock_status') or extra.get('stock_status') or '').strip()
        description = str(item_dict.get('description') or extra.get('description') or '').strip()
        extra_json = json.dumps(extra, ensure_ascii=True, separators=(',', ':')) if extra else ''
        return sku, stock_status, description, extra_json

    def _extract_stored_price(self, row: sqlite3.Row) -> Optional[float]:
        """Get the most relevant saved price for comparisons from a stored item row."""
        return self._coerce_price_number(
            row['discounted_value'],
            row['price_value'],
            row['discounted_formatted'],
            row['original_formatted'],
            row['price_text'],
        )

    def _watchlist_row_to_item(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            'url': row['url'],
            'site': row['site'] or '',
            'title': row['title'] or '',
            'price_value': row['price_value'],
            'price_currency': row['price_currency'] or '',
            'price_text': row['price_text'] or '',
            'discounted_value': row['discounted_value'],
            'discounted_formatted': row['discounted_formatted'] or '',
            'original_formatted': row['original_formatted'] or '',
            'sku': row['sku'] or '',
            'stock_status': row['stock_status'] or '',
            'description': row['description'] or '',
            'extra': json.loads(row['extra_json']) if row['extra_json'] else {},
            'source': row['source'] or '',
            'image_url': row['image_url'] or '',
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        }

    @staticmethod
    def _parse_json_text(value, fallback):
        if value in (None, ''):
            return fallback
        try:
            return json.loads(value)
        except Exception:
            return fallback

    @staticmethod
    def _normalize_automation_url(url: str) -> str:
        normalized = str(url or '').strip()
        if not normalized:
            return ''
        if normalized.endswith('/') and len(normalized) > len('https://a/'):
            normalized = normalized.rstrip('/')
        return normalized

    @staticmethod
    def _format_interval_minutes(minutes: int) -> str:
        total = max(1, int(minutes or 0))
        if total % (60 * 24 * 7) == 0:
            weeks = total // (60 * 24 * 7)
            return f"Every {weeks} week{'s' if weeks != 1 else ''}"
        if total % (60 * 24) == 0:
            days = total // (60 * 24)
            return f"Every {days} day{'s' if days != 1 else ''}"
        if total % 60 == 0:
            hours = total // 60
            return f"Every {hours} hour{'s' if hours != 1 else ''}"
        return f"Every {total} minute{'s' if total != 1 else ''}"

    @staticmethod
    def _add_minutes_to_iso(timestamp_value, minutes: int) -> str:
        base = get_pakistan_time()
        if timestamp_value:
            try:
                base = datetime.datetime.fromisoformat(str(timestamp_value).replace('Z', '+00:00'))
                if base.tzinfo is None:
                    base = PAKISTAN_TZ.localize(base)
                else:
                    base = base.astimezone(PAKISTAN_TZ)
            except Exception:
                base = get_pakistan_time()
        return (base + datetime.timedelta(minutes=max(1, int(minutes or 0)))).isoformat()

    def _row_to_automation_target(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            'id': int(row['id']),
            'job_id': int(row['job_id']),
            'label': row['label'] or '',
            'group_label': row['group_label'] or '',
            'url': row['url'] or '',
            'url_key': row['url_key'] or '',
            'active': bool(row['active']),
            'position': int(row['position'] or 0),
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        }

    def _row_to_automation_job(self, row: sqlite3.Row, *, targets: Optional[List[Dict[str, Any]]] = None, target_counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        scraper_key = str(row['scraper_key'] or 'standard')
        interval_minutes = int(row['interval_minutes'] or 1440)
        target_list = list(targets or [])
        if targets is not None:
            total_target_count = len(target_list)
            active_target_count = sum(1 for target in target_list if target.get('active', True))
        elif target_counts is not None:
            total_target_count = int(target_counts.get('target_count', 0))
            active_target_count = int(target_counts.get('active_target_count', 0))
        else:
            total_target_count = 0
            active_target_count = 0

        return {
            'id': int(row['id']),
            'name': row['name'] or '',
            'scraper_key': scraper_key,
            'site_label': (SCRAPER_CONFIG.get(scraper_key) or SCRAPER_CONFIG['standard'])['label'],
            'category_query': row['category_query'] or '',
            'root_url': row['root_url'] or '',
            'interval_minutes': interval_minutes,
            'interval_label': self._format_interval_minutes(interval_minutes),
            'enabled': bool(row['enabled']),
            'auto_discover': bool(row['auto_discover']),
            'crawl_pagination': bool(row['crawl_pagination']),
            'max_pages': int(row['max_pages'] or 10),
            'delay_ms': int(row['delay_ms'] or 0),
            'retries': int(row['retries'] or 1),
            'verify_ssl': bool(row['verify_ssl']),
            'use_parallel': bool(row['use_parallel']),
            'enrich_details': bool(row['enrich_details']),
            'drop_pct': float(row['drop_pct'] or 10.0),
            'rules': self._parse_json_text(row['rules_json'], {}),
            'last_discovery_at': row['last_discovery_at'],
            'last_run_at': row['last_run_at'],
            'next_run_at': row['next_run_at'],
            'last_status': row['last_status'] or 'idle',
            'last_error': row['last_error'] or '',
            'last_history_ids': self._parse_json_text(row['last_history_ids'], []),
            'targets': target_list,
            'target_count': total_target_count,
            'active_target_count': active_target_count,
            'skipped_target_count': max(0, total_target_count - active_target_count),
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
        }

    def _row_to_automation_run(self, row: sqlite3.Row) -> Dict[str, Any]:
        summary = self._parse_json_text(row['summary_json'], {})
        return {
            'id': int(row['id']),
            'job_id': int(row['job_id']),
            'job_name': row['job_name'] or '',
            'scraper_key': row['scraper_key'] or '',
            'category_query': row['category_query'] or '',
            'run_uuid': row['run_uuid'] or '',
            'trigger_type': row['trigger_type'] or 'manual',
            'status': row['status'] or 'running',
            'started_at': row['started_at'],
            'completed_at': row['completed_at'],
            'current_history_id': row['current_history_id'] or '',
            'previous_history_id': row['previous_history_id'] or '',
            'target_urls': self._parse_json_text(row['target_urls_json'], []),
            'items_count': int(row['items_count'] or 0),
            'summary': summary,
            'error_text': row['error_text'] or '',
            'created_at': row['created_at'],
        }

    def save_fetch_history(self, history_id: str, urls: List[str], items: List[Any], rules: Dict) -> bool:
        """Save fetch history and items to database"""
        conn = None
        try:
            conn = self.get_connection()
            # Explicitly begin a transaction to guarantee atomicity of history + items
            conn.execute("BEGIN TRANSACTION")
            cursor = conn.cursor()

            # Save fetch history - use the history_id as timestamp (it's already a Unix timestamp in ms)
            # Convert to Pakistan timezone for consistent storage
            timestamp_ms = int(history_id)
            timestamp_utc = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0, tz=pytz.UTC)
            timestamp_pakistan = timestamp_utc.astimezone(PAKISTAN_TZ)

            cursor.execute('''
                INSERT INTO fetch_history (id, timestamp, urls, urls_key, items_count, rules)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                history_id,
                timestamp_pakistan.isoformat(),
                json.dumps(urls),
                self.build_urls_key(urls),
                len(items),
                json.dumps(rules)
            ))

            # Save items
            for item in items:
                item_dict = asdict(item) if hasattr(item, '__dict__') else item
                price_value, price_currency, price_text, discounted_value, discounted_formatted, original_formatted = self._extract_price_fields(item_dict)
                sku, stock_status, description, extra_json = self._extract_item_metadata(item_dict)
                cursor.execute('''
                    INSERT INTO items (
                        history_id, url, site, title, price_value, price_currency,
                        price_text, discounted_value, discounted_formatted,
                        original_formatted, sku, stock_status, description,
                        extra_json, source, image_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    history_id,
                    item_dict.get('url', ''),
                    item_dict.get('site', ''),
                    item_dict.get('title', ''),
                    price_value,
                    price_currency,
                    price_text,
                    discounted_value,
                    discounted_formatted,
                    original_formatted,
                    sku,
                    stock_status,
                    description,
                    extra_json,
                    item_dict.get('source', ''),
                    item_dict.get('image_url', '')
                ))

            conn.commit()
            return True

        except Exception as e:
            print(f"Error saving to database: {e}")
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return False

    def save_watchlist_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create or update a saved watchlist item snapshot."""
        conn = None
        try:
            item_dict = asdict(item) if hasattr(item, '__dict__') else dict(item or {})
            url = str(item_dict.get('url') or '').strip()
            if not url:
                return None

            conn = self.get_connection()
            cursor = conn.cursor()
            price_value, price_currency, price_text, discounted_value, discounted_formatted, original_formatted = self._extract_price_fields(item_dict)
            sku, stock_status, description, extra_json = self._extract_item_metadata(item_dict)
            site = str(item_dict.get('site') or '').strip()
            title = str(item_dict.get('title') or '').strip()
            source = str(item_dict.get('source') or '').strip()
            image_url = str(item_dict.get('image_url') or '').strip()
            now_iso = get_pakistan_time().isoformat()

            cursor.execute('''
                INSERT INTO watchlist_items (
                    url, site, title, price_value, price_currency, price_text,
                    discounted_value, discounted_formatted, original_formatted,
                    sku, stock_status, description, extra_json, source,
                    image_url, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    site = excluded.site,
                    title = excluded.title,
                    price_value = excluded.price_value,
                    price_currency = excluded.price_currency,
                    price_text = excluded.price_text,
                    discounted_value = excluded.discounted_value,
                    discounted_formatted = excluded.discounted_formatted,
                    original_formatted = excluded.original_formatted,
                    sku = excluded.sku,
                    stock_status = excluded.stock_status,
                    description = excluded.description,
                    extra_json = excluded.extra_json,
                    source = excluded.source,
                    image_url = excluded.image_url,
                    updated_at = excluded.updated_at
            ''', (
                url,
                site,
                title,
                price_value,
                price_currency,
                price_text,
                discounted_value,
                discounted_formatted,
                original_formatted,
                sku,
                stock_status,
                description,
                extra_json,
                source,
                image_url,
                now_iso,
                now_iso,
            ))
            conn.commit()
            return self.get_watchlist_item(url)
        except Exception as e:
            print(f"Error saving watchlist item: {e}")
            if conn:
                conn.rollback()
            return None

    def get_watchlist_item(self, url: str) -> Optional[Dict[str, Any]]:
        normalized_url = str(url or '').strip()
        if not normalized_url:
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    url, site, title, price_value, price_currency, price_text,
                    discounted_value, discounted_formatted, original_formatted,
                    sku, stock_status, description, extra_json, source,
                    image_url, created_at, updated_at
                FROM watchlist_items
                WHERE url = ?
                LIMIT 1
            ''', (normalized_url,))
            row = cursor.fetchone()
            return self._watchlist_row_to_item(row) if row else None
        except Exception as e:
            print(f"Error getting watchlist item: {e}")
            return None

    def get_watchlist_items(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            query = '''
                SELECT
                    url, site, title, price_value, price_currency, price_text,
                    discounted_value, discounted_formatted, original_formatted,
                    sku, stock_status, description, extra_json, source,
                    image_url, created_at, updated_at
                FROM watchlist_items
                ORDER BY updated_at DESC, title COLLATE NOCASE ASC, url ASC
            '''
            params: Tuple[Any, ...] = ()
            if limit is not None:
                query += ' LIMIT ?'
                params = (max(1, int(limit)),)
            cursor.execute(query, params)
            return [self._watchlist_row_to_item(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting watchlist items: {e}")
            return []

    def get_product_metadata_cache(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """Look up known SKU, description, stock_status for a list of URLs from previous scrape items."""
        if not urls:
            return {}
        result: Dict[str, Dict[str, Any]] = {}
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            for i in range(0, len(urls), 500):
                batch = [str(u).strip() for u in urls[i:i+500] if str(u).strip()]
                if not batch:
                    continue
                placeholders = ','.join('?' for _ in batch)
                cursor.execute(f'''
                    SELECT url, sku, description, stock_status
                    FROM items
                    WHERE url IN ({placeholders})
                      AND ((sku IS NOT NULL AND sku != '') OR (description IS NOT NULL AND description != ''))
                    ORDER BY id DESC
                ''', batch)
                for row in cursor.fetchall():
                    url_key = str(row['url'] or '').strip()
                    if url_key and url_key not in result:
                        result[url_key] = {
                            'sku': row['sku'] or '',
                            'description': row['description'] or '',
                            'stock_status': row['stock_status'] or '',
                        }
        except Exception as e:
            print(f"Error getting product metadata cache: {e}")
        return result

    def get_watchlist_urls(self) -> List[str]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT url FROM watchlist_items ORDER BY updated_at DESC, url ASC')
            return [str(row['url']) for row in cursor.fetchall() if row['url']]
        except Exception as e:
            print(f"Error getting watchlist urls: {e}")
            return []

    def remove_watchlist_item(self, url: str) -> bool:
        conn = None
        normalized_url = str(url or '').strip()
        if not normalized_url:
            return False

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM watchlist_items WHERE url = ?', (normalized_url,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing watchlist item: {e}")
            if conn:
                conn.rollback()
            return False

    def clear_watchlist(self) -> int:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM watchlist_items')
            deleted = cursor.rowcount if isinstance(cursor.rowcount, int) and cursor.rowcount > 0 else 0
            conn.commit()
            return int(deleted)
        except Exception as e:
            print(f"Error clearing watchlist: {e}")
            if conn:
                conn.rollback()
            return 0

    def get_automation_job_targets(self, job_id: int) -> List[Dict[str, Any]]:
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return []

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, job_id, label, group_label, url, url_key, active, position, created_at, updated_at
                FROM automation_job_targets
                WHERE job_id = ?
                ORDER BY position ASC, label COLLATE NOCASE ASC, id ASC
            ''', (normalized_job_id,))
            return [self._row_to_automation_target(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting automation job targets: {e}")
            return []

    def get_automation_job(self, job_id: int, include_targets: bool = True) -> Optional[Dict[str, Any]]:
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    id, name, scraper_key, category_query, root_url,
                    interval_minutes, enabled, auto_discover, crawl_pagination,
                    max_pages, delay_ms, retries, verify_ssl, use_parallel,
                    enrich_details, drop_pct, rules_json,
                    last_discovery_at, last_run_at, next_run_at, last_status,
                    last_error, last_history_ids, created_at, updated_at
                FROM automation_jobs
                WHERE id = ?
                LIMIT 1
            ''', (normalized_job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            targets = self.get_automation_job_targets(normalized_job_id) if include_targets else []
            return self._row_to_automation_job(row, targets=targets)
        except Exception as e:
            print(f"Error getting automation job: {e}")
            return None

    def list_automation_jobs(self, include_targets: bool = True, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    id, name, scraper_key, category_query, root_url,
                    interval_minutes, enabled, auto_discover, crawl_pagination,
                    max_pages, delay_ms, retries, verify_ssl, use_parallel,
                    enrich_details, drop_pct, rules_json,
                    last_discovery_at, last_run_at, next_run_at, last_status,
                    last_error, last_history_ids, created_at, updated_at
                FROM automation_jobs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            ''', (max(1, int(limit)),))
            rows = cursor.fetchall()
            targets_by_job: Dict[int, List[Dict[str, Any]]] = {}
            target_counts_by_job: Dict[int, Dict[str, int]] = {}

            if rows:
                job_ids = [int(row['id']) for row in rows]
                placeholders = ','.join(['?' for _ in job_ids])

                # Fetch counts for all jobs
                cursor.execute(f'''
                    SELECT job_id, COUNT(*) as total_count, SUM(CASE WHEN active = 1 THEN 1 ELSE 0 END) as active_count
                    FROM automation_job_targets
                    WHERE job_id IN ({placeholders})
                    GROUP BY job_id
                ''', job_ids)
                for count_row in cursor.fetchall():
                    target_counts_by_job[int(count_row['job_id'])] = {
                        'target_count': int(count_row['total_count'] or 0),
                        'active_target_count': int(count_row['active_count'] or 0),
                    }

                if include_targets:
                    cursor.execute(f'''
                        SELECT id, job_id, label, group_label, url, url_key, active, position, created_at, updated_at
                        FROM automation_job_targets
                        WHERE job_id IN ({placeholders})
                        ORDER BY job_id ASC, position ASC, label COLLATE NOCASE ASC, id ASC
                    ''', job_ids)
                    for target_row in cursor.fetchall():
                        target = self._row_to_automation_target(target_row)
                        targets_by_job.setdefault(target['job_id'], []).append(target)

            return [
                self._row_to_automation_job(
                    row,
                    targets=targets_by_job.get(int(row['id']), []) if include_targets else None,
                    target_counts=target_counts_by_job.get(int(row['id']))
                )
                for row in rows
            ]
        except Exception as e:
            print(f"Error listing automation jobs: {e}")
            return []

    def replace_automation_job_targets(self, job_id: int, targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return []

        conn = None
        try:
            conn = self.get_connection()
            conn.execute("BEGIN TRANSACTION")
            cursor = conn.cursor()
            now_iso = get_pakistan_time().isoformat()
            cursor.execute('SELECT url_key, active FROM automation_job_targets WHERE job_id = ?', (normalized_job_id,))
            existing_active_by_url = {
                str(row['url_key'] or '').strip().lower(): bool(row['active'])
                for row in cursor.fetchall()
            }
            normalized_targets = []
            seen = set()
            for position, target in enumerate(targets or []):
                target_data = target if isinstance(target, dict) else {}
                url = self._normalize_automation_url(target_data.get('url'))
                if not url:
                    continue
                url_key = url.lower()
                if url_key in seen:
                    continue
                seen.add(url_key)
                raw_active = target_data['active'] if 'active' in target_data else existing_active_by_url.get(url_key, True)
                active = 0 if str(raw_active).strip().lower() in {'0', 'false', 'no', 'off'} else 1
                normalized_targets.append({
                    'label': str(target_data.get('label') or '').strip() or url,
                    'group_label': str(target_data.get('group_label') or '').strip(),
                    'url': url,
                    'url_key': url_key,
                    'active': active,
                    'position': position,
                })

            cursor.execute('DELETE FROM automation_job_targets WHERE job_id = ?', (normalized_job_id,))
            for target in normalized_targets:
                cursor.execute('''
                    INSERT INTO automation_job_targets (
                        job_id, label, group_label, url, url_key, active, position, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    normalized_job_id,
                    target['label'],
                    target['group_label'],
                    target['url'],
                    target['url_key'],
                    target['active'],
                    target['position'],
                    now_iso,
                    now_iso,
                ))

            cursor.execute('''
                UPDATE automation_jobs
                SET last_discovery_at = ?, updated_at = ?
                WHERE id = ?
            ''', (now_iso, now_iso, normalized_job_id))
            conn.commit()
            return self.get_automation_job_targets(normalized_job_id)
        except Exception as e:
            print(f"Error replacing automation targets: {e}")
            if conn:
                conn.rollback()
            return []

    def save_automation_job(self, job_data: Dict[str, Any], targets: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            payload = dict(job_data or {})
            raw_job_id = payload.get('id')
            job_id = int(raw_job_id) if raw_job_id not in (None, '') else None
            raw_scraper_value = payload.get('scraper_key') or payload.get('site') or payload.get('site_key') or ''
            scraper_key = str(raw_scraper_value or '').strip().lower()
            if scraper_key not in SCRAPER_CONFIG:
                scraper_key = detect_scraper_key(str(raw_scraper_value or payload.get('root_url') or '').strip())
            if scraper_key not in SCRAPER_CONFIG:
                scraper_key = 'standard'

            category_query = str(payload.get('category_query') or '').strip()
            if not category_query:
                return None

            site_label = (SCRAPER_CONFIG.get(scraper_key) or SCRAPER_CONFIG['standard'])['label']
            name = str(payload.get('name') or '').strip() or f"{site_label} - {category_query}"
            root_url = self._normalize_automation_url(payload.get('root_url'))
            if not root_url:
                default_domain = (SCRAPER_CONFIG.get(scraper_key) or SCRAPER_CONFIG['standard'])['domains'][0]
                root_url = f"https://{default_domain}"

            interval_minutes = max(5, min(60 * 24 * 30, int(payload.get('interval_minutes') or 1440)))
            enabled = 1 if bool(payload.get('enabled', True)) else 0
            auto_discover = 1 if bool(payload.get('auto_discover', True)) else 0
            crawl_pagination = 1 if bool(payload.get('crawl_pagination', True)) else 0
            max_pages = max(1, min(20, int(payload.get('max_pages') or 10)))
            delay_ms = max(0, min(5000, int(payload.get('delay_ms') or 50)))
            retries = max(1, min(5, int(payload.get('retries') or 1)))
            verify_ssl = 1 if bool(payload.get('verify_ssl', True)) else 0
            use_parallel = 1 if bool(payload.get('use_parallel', True)) else 0
            enrich_details = 1 if bool(payload.get('enrich_details', True)) else 0
            drop_pct = max(1.0, min(90.0, float(payload.get('drop_pct') or 10.0)))
            rules = payload.get('rules') if isinstance(payload.get('rules'), dict) else {}
            rules_json = json.dumps(rules, ensure_ascii=True, separators=(',', ':'))
            now_iso = get_pakistan_time().isoformat()

            conn = self.get_connection()
            cursor = conn.cursor()

            scope_changed = False
            if job_id:
                cursor.execute('''
                    SELECT
                        scraper_key, category_query, root_url,
                        interval_minutes, enabled, next_run_at,
                        last_run_at, last_discovery_at, last_status, last_error, last_history_ids
                    FROM automation_jobs
                    WHERE id = ?
                ''', (job_id,))
                existing = cursor.fetchone()
                if not existing:
                    return None
                previous_scraper_key = str(existing['scraper_key'] or '').strip().lower()
                previous_category_query = str(existing['category_query'] or '').strip()
                previous_root_url = self._normalize_automation_url(existing['root_url'])
                previous_interval_minutes = int(existing['interval_minutes'] or 1440)
                previous_enabled = 1 if bool(existing['enabled']) else 0
                scope_changed = (
                    previous_scraper_key != scraper_key
                    or previous_category_query != category_query
                    or previous_root_url != root_url
                )
                schedule_changed = (
                    previous_interval_minutes != interval_minutes
                    or previous_enabled != enabled
                )

                next_run_at = None
                if enabled:
                    if schedule_changed:
                        # Restart the countdown when schedule settings change on an existing job.
                        next_run_at = self._add_minutes_to_iso(now_iso, interval_minutes)
                    else:
                        next_run_at = existing['next_run_at'] or self._add_minutes_to_iso(now_iso, interval_minutes)
                cursor.execute('''
                    UPDATE automation_jobs
                    SET
                        name = ?, scraper_key = ?, category_query = ?, root_url = ?,
                        interval_minutes = ?, enabled = ?, auto_discover = ?, crawl_pagination = ?,
                        max_pages = ?, delay_ms = ?, retries = ?, verify_ssl = ?,
                        use_parallel = ?, enrich_details = ?, drop_pct = ?, rules_json = ?,
                        next_run_at = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    name,
                    scraper_key,
                    category_query,
                    root_url,
                    interval_minutes,
                    enabled,
                    auto_discover,
                    crawl_pagination,
                    max_pages,
                    delay_ms,
                    retries,
                    verify_ssl,
                    use_parallel,
                    enrich_details,
                    drop_pct,
                    rules_json,
                    next_run_at,
                    now_iso,
                    job_id,
                ))
                if scope_changed and targets is None:
                    cursor.execute('DELETE FROM automation_job_targets WHERE job_id = ?', (job_id,))
                    cursor.execute('''
                        UPDATE automation_jobs
                        SET last_discovery_at = NULL, updated_at = ?
                        WHERE id = ?
                    ''', (now_iso, job_id))
            else:
                next_run_at = self._add_minutes_to_iso(now_iso, interval_minutes) if enabled else None
                cursor.execute('''
                    INSERT INTO automation_jobs (
                        name, scraper_key, category_query, root_url,
                        interval_minutes, enabled, auto_discover, crawl_pagination,
                        max_pages, delay_ms, retries, verify_ssl, use_parallel,
                        enrich_details, drop_pct, rules_json, next_run_at,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name,
                    scraper_key,
                    category_query,
                    root_url,
                    interval_minutes,
                    enabled,
                    auto_discover,
                    crawl_pagination,
                    max_pages,
                    delay_ms,
                    retries,
                    verify_ssl,
                    use_parallel,
                    enrich_details,
                    drop_pct,
                    rules_json,
                    next_run_at,
                    now_iso,
                    now_iso,
                ))
                job_id = int(cursor.lastrowid)

            conn.commit()
            if targets is not None:
                self.replace_automation_job_targets(job_id, targets)
            return self.get_automation_job(job_id, include_targets=True)
        except Exception as e:
            print(f"Error saving automation job: {e}")
            if conn:
                conn.rollback()
            return None

    def delete_automation_job(self, job_id: int) -> bool:
        conn = None
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return False

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM automation_jobs WHERE id = ?', (normalized_job_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting automation job: {e}")
            if conn:
                conn.rollback()
            return False

    def delete_automation_run(self, run_id: int) -> bool:
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return False

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM automation_runs WHERE id = ?', (normalized_run_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting automation run: {e}")
            if conn:
                conn.rollback()
            return False

    def set_automation_job_enabled(self, job_id: int, enabled: bool) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT interval_minutes FROM automation_jobs WHERE id = ?', (normalized_job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            now_iso = get_pakistan_time().isoformat()
            next_run_at = self._add_minutes_to_iso(now_iso, row['interval_minutes']) if enabled else None
            cursor.execute('''
                UPDATE automation_jobs
                SET enabled = ?, next_run_at = ?, updated_at = ?
                WHERE id = ?
            ''', (1 if enabled else 0, next_run_at, now_iso, normalized_job_id))
            conn.commit()
            return self.get_automation_job(normalized_job_id, include_targets=True)
        except Exception as e:
            print(f"Error toggling automation job: {e}")
            if conn:
                conn.rollback()
            return None

    def get_due_automation_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            now_iso = get_pakistan_time().isoformat()
            cursor.execute('''
                SELECT
                    id, name, scraper_key, category_query, root_url,
                    interval_minutes, enabled, auto_discover, crawl_pagination,
                    max_pages, delay_ms, retries, verify_ssl, use_parallel,
                    enrich_details, drop_pct, rules_json,
                    last_discovery_at, last_run_at, next_run_at, last_status,
                    last_error, last_history_ids, created_at, updated_at
                FROM automation_jobs
                WHERE enabled = 1
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
                  AND (last_status IS NULL OR last_status NOT IN ('running', 'resuming'))
                ORDER BY next_run_at ASC, id ASC
                LIMIT ?
            ''', (now_iso, max(1, int(limit))))
            rows = cursor.fetchall()
            return [self._row_to_automation_job(row, targets=self.get_automation_job_targets(int(row['id']))) for row in rows]
        except Exception as e:
            print(f"Error getting due automation jobs: {e}")
            return []

    def create_automation_run(
        self,
        job_id: int,
        trigger_type: str = 'manual',
        target_urls: Optional[List[str]] = None,
        previous_history_id: str = '',
    ) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            began_transaction = False
            if not conn.in_transaction:
                cursor.execute('BEGIN IMMEDIATE')
                began_transaction = True
            cursor.execute('SELECT id FROM automation_jobs WHERE id = ?', (normalized_job_id,))
            if not cursor.fetchone():
                if began_transaction:
                    conn.rollback()
                return None
            cursor.execute('''
                SELECT id
                FROM automation_runs
                WHERE job_id = ?
                  AND status IN ('running', 'resuming')
                ORDER BY started_at DESC, id DESC
                LIMIT 1
            ''', (normalized_job_id,))
            if cursor.fetchone():
                if began_transaction:
                    conn.rollback()
                return None

            now_iso = get_pakistan_time().isoformat()
            run_uuid = f"automation-{normalized_job_id}-{int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:8]}"
            cursor.execute('''
                INSERT INTO automation_runs (
                    job_id, run_uuid, trigger_type, status, started_at,
                    previous_history_id, target_urls_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                normalized_job_id,
                run_uuid,
                str(trigger_type or 'manual').strip() or 'manual',
                'running',
                now_iso,
                str(previous_history_id or ''),
                json.dumps(list(target_urls or []), ensure_ascii=True, separators=(',', ':')),
                now_iso,
            ))
            run_id = int(cursor.lastrowid)
            cursor.execute('''
                UPDATE automation_jobs
                SET last_status = ?, last_error = '', updated_at = ?
                WHERE id = ?
            ''', ('running', now_iso, normalized_job_id))
            conn.commit()
            return self.get_automation_run(run_id)
        except Exception as e:
            print(f"Error creating automation run: {e}")
            if conn:
                conn.rollback()
            return None

    def update_automation_run_progress(
        self,
        run_id: int,
        *,
        items_count: Optional[int] = None,
        summary: Optional[Dict[str, Any]] = None,
        error_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, job_id, items_count, summary_json, error_text
                FROM automation_runs
                WHERE id = ?
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            if not row:
                return None

            existing_summary = self._parse_json_text(row['summary_json'], {})
            merged_summary = dict(existing_summary)
            if isinstance(summary, dict):
                merged_summary.update(summary)

            next_items_count = int(items_count if items_count is not None else row['items_count'] or 0)
            next_error_text = str(error_text if error_text is not None else row['error_text'] or '')
            now_iso = get_pakistan_time().isoformat()

            cursor.execute('''
                UPDATE automation_runs
                SET items_count = ?, summary_json = ?, error_text = ?
                WHERE id = ?
            ''', (
                next_items_count,
                json.dumps(merged_summary, ensure_ascii=True, separators=(',', ':')),
                next_error_text,
                normalized_run_id,
            ))
            cursor.execute('''
                UPDATE automation_jobs
                SET updated_at = ?
                WHERE id = ?
            ''', (now_iso, int(row['job_id'])))
            conn.commit()
            return self.get_automation_run(normalized_run_id)
        except Exception as e:
            print(f"Error updating automation run progress: {e}")
            if conn:
                conn.rollback()
            return None

    def append_automation_run_items(self, run_id: int, items: List[Dict[str, Any]]) -> int:
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return 0

        rows = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            rows.append(json.dumps(item, ensure_ascii=True, separators=(',', ':')))
        if not rows:
            return 0

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COALESCE(MAX(item_index), -1) AS max_index FROM automation_run_items WHERE run_id = ?', (normalized_run_id,))
            row = cursor.fetchone()
            start_index = int((row['max_index'] if row else -1) or -1) + 1
            now_iso = get_pakistan_time().isoformat()
            cursor.executemany('''
                INSERT INTO automation_run_items (run_id, item_index, item_json, created_at)
                VALUES (?, ?, ?, ?)
            ''', [
                (normalized_run_id, start_index + offset, item_json, now_iso)
                for offset, item_json in enumerate(rows)
            ])
            conn.commit()
            return len(rows)
        except Exception as e:
            print(f"Error appending automation run items: {e}")
            if conn:
                conn.rollback()
            return 0

    def get_automation_run_items(self, run_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return []

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            params: List[Any] = [normalized_run_id]
            limit_clause = ''
            if limit not in (None, ''):
                limit_clause = 'LIMIT ?'
                params.append(max(1, int(limit)))
            cursor.execute(f'''
                SELECT item_json
                FROM automation_run_items
                WHERE run_id = ?
                ORDER BY item_index ASC
                {limit_clause}
            ''', tuple(params))
            items = []
            for row in cursor.fetchall():
                parsed = self._parse_json_text(row['item_json'], {})
                if isinstance(parsed, dict):
                    items.append(parsed)
            return items
        except Exception as e:
            print(f"Error getting automation run items: {e}")
            return []

    def mark_automation_run_resuming(
        self,
        run_id: int,
        *,
        target_urls: Optional[List[str]] = None,
        previous_history_id: str = '',
        summary: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.id, r.job_id, r.target_urls_json, r.previous_history_id
                FROM automation_runs r
                WHERE r.id = ?
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            if not row:
                return None

            serialized_targets = json.dumps(
                list(target_urls if target_urls is not None else self._parse_json_text(row['target_urls_json'], [])),
                ensure_ascii=True,
                separators=(',', ':'),
            )
            safe_previous_history_id = str(previous_history_id or row['previous_history_id'] or '')
            safe_summary = dict(summary or {})
            now_iso = get_pakistan_time().isoformat()

            cursor.execute('''
                UPDATE automation_runs
                SET
                    status = 'running',
                    completed_at = NULL,
                    current_history_id = '',
                    previous_history_id = ?,
                    target_urls_json = ?,
                    items_count = ?,
                    summary_json = ?,
                    error_text = ''
                WHERE id = ?
            ''', (
                safe_previous_history_id,
                serialized_targets,
                int(safe_summary.get('current_items') or safe_summary.get('items_count') or 0),
                json.dumps(safe_summary, ensure_ascii=True, separators=(',', ':')),
                normalized_run_id,
            ))
            cursor.execute('''
                UPDATE automation_jobs
                SET last_status = 'running', last_error = '', updated_at = ?
                WHERE id = ?
            ''', (now_iso, int(row['job_id'])))
            conn.commit()
            return self.get_automation_run(normalized_run_id)
        except Exception as e:
            print(f"Error marking automation run as resuming: {e}")
            if conn:
                conn.rollback()
            return None

    def claim_automation_run_resume(self, run_id: int) -> Optional[Dict[str, Any]]:
        """Atomically reserve one resumable run before launching its worker process."""
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute('''
                SELECT id, job_id, status, summary_json
                FROM automation_runs
                WHERE id = ?
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return None

            current_status = str(row['status'] or '').strip().lower()
            if current_status not in {'paused', 'interrupted', 'failed'}:
                conn.rollback()
                return None

            now_iso = get_pakistan_time().isoformat()
            summary = self._parse_json_text(row['summary_json'], {})
            summary = dict(summary) if isinstance(summary, dict) else {}
            summary['resume_launch_requested_at'] = now_iso
            summary['resumed_from_status'] = current_status
            summary['resume_available'] = False
            cursor.execute('''
                UPDATE automation_runs
                SET status = 'resuming', summary_json = ?, error_text = ''
                WHERE id = ? AND status = ?
            ''', (
                json.dumps(summary, ensure_ascii=True, separators=(',', ':')),
                normalized_run_id,
                row['status'],
            ))
            if cursor.rowcount != 1:
                conn.rollback()
                return None
            cursor.execute('''
                UPDATE automation_jobs
                SET last_status = 'resuming', last_error = '', updated_at = ?
                WHERE id = ?
            ''', (now_iso, int(row['job_id'])))
            conn.commit()
            return self.get_automation_run(normalized_run_id)
        except Exception as e:
            print(f"Error claiming automation run resume: {e}")
            if conn:
                conn.rollback()
            return None

    def fail_automation_run_resume_launch(self, run_id: int, error_text: str) -> Optional[Dict[str, Any]]:
        """Return a claimed run to a resumable failed state if its worker cannot launch."""
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, job_id, summary_json
                FROM automation_runs
                WHERE id = ? AND status = 'resuming'
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            if not row:
                return self.get_automation_run(normalized_run_id)

            now_iso = get_pakistan_time().isoformat()
            summary = self._parse_json_text(row['summary_json'], {})
            summary = dict(summary) if isinstance(summary, dict) else {}
            summary['resume_available'] = True
            summary['resume_launch_failed_at'] = now_iso
            message = str(error_text or 'Failed to launch resume worker.')
            cursor.execute('''
                UPDATE automation_runs
                SET status = 'failed', summary_json = ?, error_text = ?
                WHERE id = ? AND status = 'resuming'
            ''', (
                json.dumps(summary, ensure_ascii=True, separators=(',', ':')),
                message,
                normalized_run_id,
            ))
            cursor.execute('''
                UPDATE automation_jobs
                SET last_status = 'failed', last_error = ?, updated_at = ?
                WHERE id = ?
            ''', (message, now_iso, int(row['job_id'])))
            conn.commit()
            return self.get_automation_run(normalized_run_id)
        except Exception as e:
            print(f"Error recording automation resume launch failure: {e}")
            if conn:
                conn.rollback()
            return None

    def pause_automation_run(
        self,
        run_id: int,
        *,
        reason: str = 'Automation run paused.',
    ) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, job_id, summary_json, error_text
                FROM automation_runs
                WHERE id = ?
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            if not row:
                return None

            existing_summary = self._parse_json_text(row['summary_json'], {})
            paused_summary = dict(existing_summary)
            paused_summary['paused'] = True
            paused_summary['paused_at'] = get_pakistan_time().isoformat()
            paused_summary['resume_available'] = True
            next_error_text = str(reason or row['error_text'] or 'Automation run paused.')
            now_iso = get_pakistan_time().isoformat()

            cursor.execute('''
                UPDATE automation_runs
                SET status = 'paused', summary_json = ?, error_text = ?
                WHERE id = ?
            ''', (
                json.dumps(paused_summary, ensure_ascii=True, separators=(',', ':')),
                next_error_text,
                normalized_run_id,
            ))
            cursor.execute('''
                UPDATE automation_jobs
                SET last_status = 'paused', last_error = ?, updated_at = ?
                WHERE id = ?
            ''', (next_error_text, now_iso, int(row['job_id'])))
            conn.commit()
            return self.get_automation_run(normalized_run_id)
        except Exception as e:
            print(f"Error pausing automation run: {e}")
            if conn:
                conn.rollback()
            return None

    def complete_automation_run(
        self,
        run_id: int,
        *,
        status: str,
        current_history_id: str = '',
        previous_history_id: str = '',
        target_urls: Optional[List[str]] = None,
        items_count: int = 0,
        summary: Optional[Dict[str, Any]] = None,
        error_text: str = '',
    ) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    r.id, r.job_id, r.trigger_type, r.started_at,
                    j.interval_minutes, j.enabled, j.next_run_at, j.last_history_ids
                FROM automation_runs r
                JOIN automation_jobs j ON j.id = r.job_id
                WHERE r.id = ?
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            if not row:
                return None

            now_iso = get_pakistan_time().isoformat()
            safe_status = str(status or 'completed').strip() or 'completed'
            safe_summary = dict(summary or {})
            serialized_targets = json.dumps(list(target_urls or []), ensure_ascii=True, separators=(',', ':'))
            cursor.execute('''
                UPDATE automation_runs
                SET
                    status = ?, completed_at = ?, current_history_id = ?, previous_history_id = ?,
                    target_urls_json = ?, items_count = ?, summary_json = ?, error_text = ?
                WHERE id = ?
            ''', (
                safe_status,
                now_iso,
                str(current_history_id or ''),
                str(previous_history_id or ''),
                serialized_targets,
                int(items_count or 0),
                json.dumps(safe_summary, ensure_ascii=True, separators=(',', ':')),
                str(error_text or ''),
                normalized_run_id,
            ))

            next_run_at = None
            if bool(row['enabled']):
                trigger_type = str(row['trigger_type'] or 'manual').strip().lower()
                existing_next_run = str(row['next_run_at'] or '').strip()
                if trigger_type == 'manual' and existing_next_run and existing_next_run > now_iso:
                    next_run_at = existing_next_run
                else:
                    next_run_at = self._add_minutes_to_iso(existing_next_run or row['started_at'], row['interval_minutes'])
                    guard = 0
                    while next_run_at <= now_iso and guard < 8:
                        next_run_at = self._add_minutes_to_iso(next_run_at, row['interval_minutes'])
                        guard += 1

            last_history_ids = row['last_history_ids'] or '[]'
            if safe_status == 'completed' and current_history_id:
                last_history_ids = json.dumps([str(current_history_id)], ensure_ascii=True, separators=(',', ':'))

            cursor.execute('''
                UPDATE automation_jobs
                SET
                    last_run_at = ?, next_run_at = ?, last_status = ?, last_error = ?,
                    last_history_ids = ?, updated_at = ?
                WHERE id = ?
            ''', (
                now_iso,
                next_run_at,
                safe_status,
                str(error_text or ''),
                last_history_ids,
                now_iso,
                int(row['job_id']),
            ))
            conn.commit()
            return self.get_automation_run(normalized_run_id)
        except Exception as e:
            print(f"Error completing automation run: {e}")
            if conn:
                conn.rollback()
            return None

    def recover_running_automation_runs(self, reason: str = 'Automation run interrupted by server restart.') -> int:
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT r.id, r.job_id, r.previous_history_id, r.summary_json, j.last_history_ids
                FROM automation_runs r
                JOIN automation_jobs j ON j.id = r.job_id
                WHERE r.status IN ('running', 'resuming')
            ''')
            running_rows = cursor.fetchall()
            if not running_rows:
                return 0

            now_iso = get_pakistan_time().isoformat()
            run_ids = [int(row['id']) for row in running_rows]
            job_ids = sorted({int(row['job_id']) for row in running_rows})
            run_placeholders = ','.join(['?' for _ in run_ids])
            job_placeholders = ','.join(['?' for _ in job_ids])

            for row in running_rows:
                previous_history_id = str(row['previous_history_id'] or '').strip()
                if not previous_history_id:
                    last_history_ids = self._parse_json_text(row['last_history_ids'], [])
                    if isinstance(last_history_ids, list) and last_history_ids:
                        previous_history_id = str(last_history_ids[0] or '').strip()
                summary = self._parse_json_text(row['summary_json'], {})
                if not isinstance(summary, dict):
                    summary = {}
                summary['interrupted'] = True
                summary['interrupted_at'] = now_iso
                summary['resume_available'] = True
                cursor.execute('''
                    UPDATE automation_runs
                    SET status = 'interrupted', completed_at = ?, error_text = ?, previous_history_id = ?, summary_json = ?
                    WHERE id = ?
                ''', (
                    now_iso,
                    str(reason or ''),
                    previous_history_id,
                    json.dumps(summary, ensure_ascii=True, separators=(',', ':')),
                    int(row['id']),
                ))
            cursor.execute(f'''
                UPDATE automation_jobs
                SET last_status = 'interrupted', last_error = ?, updated_at = ?
                WHERE id IN ({job_placeholders})
            ''', [str(reason or ''), now_iso] + job_ids)
            conn.commit()
            return len(run_ids)
        except Exception as e:
            print(f"Error recovering running automation runs: {e}")
            if conn:
                conn.rollback()
            return 0

    def list_automation_runs(
        self,
        job_id: Optional[int] = None,
        scraper_key: Optional[str] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            params: List[Any] = []
            where_parts: List[str] = []
            if job_id not in (None, ''):
                where_parts.append('r.job_id = ?')
                params.append(int(job_id))
            normalized_scraper_key = str(scraper_key or '').strip().lower()
            if normalized_scraper_key:
                if normalized_scraper_key not in SCRAPER_CONFIG:
                    normalized_scraper_key = detect_scraper_key(normalized_scraper_key)
                if normalized_scraper_key in SCRAPER_CONFIG:
                    where_parts.append('j.scraper_key = ?')
                    params.append(normalized_scraper_key)
            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''
            params.append(max(1, int(limit)))
            cursor.execute(f'''
                SELECT
                    r.id, r.job_id, r.run_uuid, r.trigger_type, r.status,
                    r.started_at, r.completed_at, r.current_history_id,
                    r.previous_history_id, r.target_urls_json, r.items_count,
                    r.summary_json, r.error_text, r.created_at,
                    j.name AS job_name, j.scraper_key, j.category_query
                FROM automation_runs r
                JOIN automation_jobs j ON j.id = r.job_id
                {where_clause}
                ORDER BY r.started_at DESC, r.id DESC
                LIMIT ?
            ''', tuple(params))
            return [self._row_to_automation_run(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error listing automation runs: {e}")
            return []

    def get_active_automation_run_for_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        try:
            normalized_job_id = int(job_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    r.id, r.job_id, r.run_uuid, r.trigger_type, r.status,
                    r.started_at, r.completed_at, r.current_history_id,
                    r.previous_history_id, r.target_urls_json, r.items_count,
                    r.summary_json, r.error_text, r.created_at,
                    j.name AS job_name, j.scraper_key, j.category_query
                FROM automation_runs r
                JOIN automation_jobs j ON j.id = r.job_id
                WHERE r.job_id = ?
                  AND r.status IN ('running', 'resuming')
                ORDER BY r.started_at DESC, r.id DESC
                LIMIT 1
            ''', (normalized_job_id,))
            row = cursor.fetchone()
            return self._row_to_automation_run(row) if row else None
        except Exception as e:
            print(f"Error getting active automation run: {e}")
            return None

    def get_automation_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        try:
            normalized_run_id = int(run_id)
        except (TypeError, ValueError):
            return None

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    r.id, r.job_id, r.run_uuid, r.trigger_type, r.status,
                    r.started_at, r.completed_at, r.current_history_id,
                    r.previous_history_id, r.target_urls_json, r.items_count,
                    r.summary_json, r.error_text, r.created_at,
                    j.name AS job_name, j.scraper_key, j.category_query
                FROM automation_runs r
                JOIN automation_jobs j ON j.id = r.job_id
                WHERE r.id = ?
                LIMIT 1
            ''', (normalized_run_id,))
            row = cursor.fetchone()
            return self._row_to_automation_run(row) if row else None
        except Exception as e:
            print(f"Error getting automation run: {e}")
            return None

    def get_automation_overview(self) -> Dict[str, Any]:
        try:
            jobs = self.list_automation_jobs(include_targets=True, limit=500)
            runs = self.list_automation_runs(limit=100)
            enabled_jobs = sum(1 for job in jobs if job.get('enabled'))
            running_jobs = sum(1 for job in jobs if job.get('last_status') == 'running')
            total_targets = sum(int(job.get('target_count') or 0) for job in jobs)
            changed_runs = sum(
                1 for run in runs
                if (run.get('summary') or {}).get('changed')
                or (run.get('summary') or {}).get('added')
                or (run.get('summary') or {}).get('removed')
            )
            return {
                'total_jobs': len(jobs),
                'enabled_jobs': enabled_jobs,
                'running_jobs': running_jobs,
                'total_targets': total_targets,
                'recent_runs': len(runs),
                'changed_runs': changed_runs,
            }
        except Exception as e:
            print(f"Error getting automation overview: {e}")
            return {
                'total_jobs': 0,
                'enabled_jobs': 0,
                'running_jobs': 0,
                'total_targets': 0,
                'recent_runs': 0,
                'changed_runs': 0,
            }

    def get_latest_prices_for_urls(self, urls: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return the latest saved price snapshot for each product URL."""
        try:
            normalized_urls = []
            seen = set()
            for url in urls:
                normalized = str(url or '').strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                normalized_urls.append(normalized)

            if not normalized_urls:
                return {}

            conn = self.get_connection()
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in normalized_urls])
            cursor.execute(f'''
                SELECT
                    i.url,
                    i.title,
                    i.site,
                    i.price_value,
                    i.price_text,
                    i.discounted_value,
                    i.discounted_formatted,
                    i.original_formatted,
                    i.history_id,
                    h.timestamp
                FROM items i
                JOIN fetch_history h ON h.id = i.history_id
                WHERE i.url IN ({placeholders})
                ORDER BY h.timestamp DESC, i.id DESC
            ''', normalized_urls)

            latest_by_url = {}
            for row in cursor.fetchall():
                url = str(row['url'] or '').strip()
                if not url or url in latest_by_url:
                    continue
                price = self._extract_stored_price(row)
                if price is None:
                    continue
                latest_by_url[url] = {
                    'price': price,
                    'title': row['title'] or '',
                    'site': row['site'] or '',
                    'history_id': row['history_id'],
                    'timestamp': row['timestamp'],
                }

            return latest_by_url
        except Exception as e:
            print(f"Error getting latest prices: {e}")
            return {}

    def get_history_list(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get list of fetch history entries"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, timestamp, urls, items_count, rules, created_at
                FROM fetch_history
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))

            histories = []
            for row in cursor.fetchall():
                # Convert ISO timestamp back to milliseconds for frontend
                timestamp_str = row['timestamp']
                if 'T' in timestamp_str:  # ISO format
                    timestamp_dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    timestamp_ms = int(timestamp_dt.timestamp() * 1000)
                else:  # Already a number
                    timestamp_ms = int(timestamp_str)

                histories.append({
                    'id': row['id'],
                    'timestamp': timestamp_ms,
                    'urls': json.loads(row['urls']),
                    'items_count': row['items_count'],
                    'rules': json.loads(row['rules']),
                    'created_at': row['created_at']
                })

            return histories

        except Exception as e:
            print(f"Error getting history list: {e}")
            return []

    def get_history_detail(self, history_id: str) -> Optional[Dict]:
        """Get detailed history entry with items"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Get history entry
            cursor.execute('''
                SELECT id, timestamp, urls, urls_key, items_count, rules, created_at
                FROM fetch_history
                WHERE id = ?
            ''', (history_id,))

            row = cursor.fetchone()
            if not row:
                return None

            # Get items for this history
            cursor.execute('''
                SELECT url, site, title, price_value, price_currency, price_text,
                       discounted_value, discounted_formatted, original_formatted,
                       sku, stock_status, description, extra_json, source, image_url
                FROM items
                WHERE history_id = ?
                ORDER BY id
            ''', (history_id,))

            items = []
            for item_row in cursor.fetchall():
                items.append({
                    'url': item_row['url'],
                    'site': item_row['site'],
                    'title': item_row['title'],
                    'price_value': item_row['price_value'],
                    'price_currency': item_row['price_currency'],
                    'price_text': item_row['price_text'],
                    'discounted_value': item_row['discounted_value'],
                    'discounted_formatted': item_row['discounted_formatted'],
                    'original_formatted': item_row['original_formatted'],
                    'sku': item_row['sku'],
                    'stock_status': item_row['stock_status'],
                    'description': item_row['description'],
                    'extra': json.loads(item_row['extra_json']) if item_row['extra_json'] else {},
                    'source': item_row['source'],
                    'image_url': item_row['image_url']
                })

            # Convert ISO timestamp back to milliseconds for frontend
            timestamp_str = row['timestamp']
            if 'T' in timestamp_str:  # ISO format
                timestamp_dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                timestamp_ms = int(timestamp_dt.timestamp() * 1000)
            else:  # Already a number
                timestamp_ms = int(timestamp_str)

            return {
                'id': row['id'],
                'timestamp': timestamp_ms,
                'urls': json.loads(row['urls']),
                'urls_key': row['urls_key'],
                'items_count': row['items_count'],
                'rules': json.loads(row['rules']),
                'created_at': row['created_at'],
                'items': items
            }

        except Exception as e:
            print(f"Error getting history detail: {e}")
            return None

    @staticmethod
    def _history_rules_mark_baseline_rejected(rules_text: str) -> bool:
        try:
            rules = json.loads(rules_text or '{}')
            return bool(isinstance(rules, dict) and rules.get('_baseline_rejected'))
        except Exception:
            return False

    def get_latest_history_for_urls(self, urls: List[str]) -> Optional[Dict]:
        """Get the most recent saved session for the exact same target URL set."""
        try:
            urls_key = self.build_urls_key(urls)
            if not urls_key:
                return None

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, rules
                FROM fetch_history
                WHERE urls_key = ?
                ORDER BY timestamp DESC
                LIMIT 20
            ''', (urls_key,))
            for row in cursor.fetchall():
                if self._history_rules_mark_baseline_rejected(row['rules']):
                    continue
                return self.get_history_detail(row['id'])
            return None
        except Exception as e:
            print(f"Error getting latest history for urls: {e}")
            return None

    def delete_history(self, history_id: str) -> bool:
        """Delete history entry and associated items"""
        conn = None
        try:
            normalized_history_id = str(history_id).strip()
            if not normalized_history_id:
                return False

            conn = self.get_connection()
            cursor = conn.cursor()

            # Delete items first (due to foreign key)
            cursor.execute('DELETE FROM items WHERE history_id = ?', (normalized_history_id,))

            # Delete history entry
            cursor.execute('DELETE FROM fetch_history WHERE id = ?', (normalized_history_id,))
            deleted_rows = cursor.rowcount

            conn.commit()
            return deleted_rows > 0

        except Exception as e:
            print(f"Error deleting history: {e}")
            if conn:
                conn.rollback()
            return False

    def prune_histories_for_urls(self, urls: List[str], keep: int = 2) -> List[str]:
        """Keep the newest valid histories for an exact URL set and delete older ones."""
        conn = None
        try:
            urls_key = self.build_urls_key(urls)
            keep = max(1, int(keep or 2))
            if not urls_key:
                return []

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, rules
                FROM fetch_history
                WHERE urls_key = ?
                ORDER BY timestamp DESC
            ''', (urls_key,))
            rows = cursor.fetchall()
            if len(rows) <= keep:
                return []

            kept_valid = 0
            ids_to_delete = []
            for row in rows:
                if self._history_rules_mark_baseline_rejected(row['rules']):
                    ids_to_delete.append(row['id'])
                    continue
                if kept_valid < keep:
                    kept_valid += 1
                    continue
                ids_to_delete.append(row['id'])

            if not ids_to_delete:
                return []

            placeholders = ','.join(['?' for _ in ids_to_delete])
            cursor.execute(f'DELETE FROM items WHERE history_id IN ({placeholders})', ids_to_delete)
            cursor.execute(f'DELETE FROM fetch_history WHERE id IN ({placeholders})', ids_to_delete)
            conn.commit()
            return ids_to_delete
        except Exception as e:
            print(f"Error pruning histories for urls: {e}")
            if conn:
                conn.rollback()
            return []

    def get_statistics(self) -> Dict:
        """Get comprehensive database statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Total histories
            cursor.execute('SELECT COUNT(*) as count FROM fetch_history')
            total_histories = cursor.fetchone()['count']

            # Total items
            cursor.execute('SELECT COUNT(*) as count FROM items')
            total_items = cursor.fetchone()['count']

            # Recent activity (last 30 days in Pakistan timezone)
            now_pakistan = get_pakistan_time()
            thirty_days_ago = now_pakistan - datetime.timedelta(days=30)
            thirty_days_ago_str = thirty_days_ago.isoformat()

            cursor.execute('''
                SELECT COUNT(*) as count FROM fetch_history
                WHERE timestamp >= ?
            ''', (thirty_days_ago_str,))
            recent_histories = cursor.fetchone()['count']

            # Unique models (approximation based on titles)
            cursor.execute('''
                SELECT COUNT(DISTINCT
                    CASE
                        WHEN title LIKE '%iPhone%' THEN 'iPhone'
                        WHEN title LIKE '%Galaxy%' THEN 'Galaxy'
                        WHEN title LIKE '%iPad%' THEN 'iPad'
                        WHEN title LIKE '%Pixel%' THEN 'Pixel'
                        WHEN title LIKE '%OnePlus%' THEN 'OnePlus'
                        ELSE SUBSTR(title, 1, 20)
                    END
                ) as unique_models FROM items WHERE title != ''
            ''')
            unique_models = cursor.fetchone()['unique_models'] or 0

            # Unique sites
            cursor.execute('SELECT COUNT(DISTINCT site) as count FROM items WHERE site != ""')
            unique_sites = cursor.fetchone()['count']

            # Database size
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            db_size = cursor.fetchone()['size']

            # Average items per session
            avg_items = round(total_items / max(total_histories, 1), 1)

            # Average price (from items with valid prices)
            cursor.execute('''
                SELECT AVG(price_value) as avg_price FROM items
                WHERE price_value IS NOT NULL AND price_value > 0
            ''')
            avg_price_result = cursor.fetchone()
            avg_price = round(avg_price_result['avg_price'] or 0, 2)

            # Success rate (items with prices vs total items)
            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN price_value IS NOT NULL AND price_value > 0 THEN 1 END) as successful,
                    COUNT(*) as total
                FROM items
            ''')
            success_data = cursor.fetchone()
            success_rate = round((success_data['successful'] / max(success_data['total'], 1)) * 100, 1)

            # Top site by item count
            cursor.execute('''
                SELECT site, COUNT(*) as item_count
                FROM items
                WHERE site != ""
                GROUP BY site
                ORDER BY item_count DESC
                LIMIT 1
            ''')
            top_site_result = cursor.fetchone()
            top_site = top_site_result['site'] if top_site_result else 'N/A'

            # Clean up site name for display
            if top_site and top_site != 'N/A':
                # Remove common prefixes and make it shorter
                top_site = top_site.replace('www.', '').replace('.com', '').replace('.ca', '')
                if '.' in top_site:
                    top_site = top_site.split('.')[0]
                top_site = top_site.capitalize()

            # Latest session date
            cursor.execute('''
                SELECT timestamp
                FROM fetch_history
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            latest_session_result = cursor.fetchone()
            latest_session = 'Never'
            if latest_session_result:
                try:
                    # Parse the timestamp and convert to Pakistan time
                    ts_str = latest_session_result['timestamp']
                    if '+' in ts_str or 'Z' in ts_str:
                        # Has timezone info
                        ts = datetime.datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if ts.tzinfo is None:
                            ts = pytz.UTC.localize(ts)
                        ts_pakistan = ts.astimezone(PAKISTAN_TZ)
                    else:
                        # Assume it's already in Pakistan time
                        ts = datetime.datetime.fromisoformat(ts_str)
                        ts_pakistan = PAKISTAN_TZ.localize(ts)

                    latest_session = ts_pakistan.strftime('%b %d')  # e.g., "Oct 17"
                except Exception as e:
                    print(f"Error parsing latest session timestamp: {e}")
                    latest_session = 'Recent'

            # Oldest session date
            cursor.execute('''
                SELECT timestamp
                FROM fetch_history
                ORDER BY timestamp ASC
                LIMIT 1
            ''')
            oldest_session_result = cursor.fetchone()
            oldest_session = 'N/A'
            if oldest_session_result:
                try:
                    # Parse the timestamp and convert to Pakistan time
                    ts_str = oldest_session_result['timestamp']
                    if '+' in ts_str or 'Z' in ts_str:
                        # Has timezone info
                        ts = datetime.datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                        if ts.tzinfo is None:
                            ts = pytz.UTC.localize(ts)
                        ts_pakistan = ts.astimezone(PAKISTAN_TZ)
                    else:
                        # Assume it's already in Pakistan time
                        ts = datetime.datetime.fromisoformat(ts_str)
                        ts_pakistan = PAKISTAN_TZ.localize(ts)

                    oldest_session = ts_pakistan.strftime('%b %d, %Y')  # e.g., "Oct 17, 2024"
                except Exception as e:
                    print(f"Error parsing oldest session timestamp: {e}")
                    oldest_session = 'Unknown'

            # Total value of all items
            cursor.execute('''
                SELECT SUM(price_value) as total_value FROM items
                WHERE price_value IS NOT NULL AND price_value > 0
            ''')
            total_value_result = cursor.fetchone()
            total_value = round(total_value_result['total_value'] or 0, 2)

            # Highest price
            cursor.execute('''
                SELECT MAX(price_value) as highest_price FROM items
                WHERE price_value IS NOT NULL AND price_value > 0
            ''')
            highest_price_result = cursor.fetchone()
            highest_price = round(highest_price_result['highest_price'] or 0, 2)

            # Lowest price
            cursor.execute('''
                SELECT MIN(price_value) as lowest_price FROM items
                WHERE price_value IS NOT NULL AND price_value > 0
            ''')
            lowest_price_result = cursor.fetchone()
            lowest_price = round(lowest_price_result['lowest_price'] or 0, 2)

            return {
                'total_histories': total_histories,
                'total_items': total_items,
                'recent_histories': recent_histories,
                'unique_models': unique_models,
                'unique_sites': unique_sites,
                'database_size': db_size,
                'avg_items_per_session': avg_items,
                'avg_price': avg_price,
                'success_rate': success_rate,
                'top_site': top_site,
                'latest_session': latest_session,
                'oldest_session': oldest_session,
                'total_value': total_value,
                'highest_price': highest_price,
                'lowest_price': lowest_price
            }

        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {}


    def cleanup_old_entries(self, days: int = 90) -> int:
        """Remove entries older than specified days (calculated in Pakistan timezone)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # If days is very large (99999), delete everything
            if days >= 99999:
                # Count total entries before deletion
                cursor.execute('SELECT COUNT(*) as count FROM fetch_history')
                total_count = cursor.fetchone()['count']

                # Delete all items
                cursor.execute('DELETE FROM items')

                # Delete all history
                cursor.execute('DELETE FROM fetch_history')

                conn.commit()
                return total_count

            # Calculate cutoff date in Pakistan timezone
            now_pakistan = get_pakistan_time()
            cutoff_date = now_pakistan - datetime.timedelta(days=days)
            cutoff_date_str = cutoff_date.isoformat()

            # Get old history IDs
            cursor.execute('''
                SELECT id FROM fetch_history
                WHERE timestamp < ?
            ''', (cutoff_date_str,))

            old_ids = [row['id'] for row in cursor.fetchall()]

            if old_ids:
                # Delete items for old histories
                placeholders = ','.join(['?' for _ in old_ids])
                cursor.execute(f'DELETE FROM items WHERE history_id IN ({placeholders})', old_ids)

                # Delete old histories
                cursor.execute(f'DELETE FROM fetch_history WHERE id IN ({placeholders})', old_ids)

                conn.commit()
                return len(old_ids)

            return 0

        except Exception as e:
            print(f"Error cleaning up old entries: {e}")
            conn.rollback()
            return 0

    def search_items(self, query: str, limit: int = 100) -> List[Dict]:
        """Search items by title or URL"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT i.*, h.timestamp
                FROM items i
                JOIN fetch_history h ON i.history_id = h.id
                WHERE i.title LIKE ? OR i.url LIKE ?
                ORDER BY h.timestamp DESC
                LIMIT ?
            ''', (f'%{query}%', f'%{query}%', limit))

            items = []
            for row in cursor.fetchall():
                items.append({
                    'url': row['url'],
                    'site': row['site'],
                    'title': row['title'],
                    'price_value': row['price_value'],
                    'price_currency': row['price_currency'],
                    'price_text': row['price_text'],
                    'discounted_value': row['discounted_value'],
                    'discounted_formatted': row['discounted_formatted'],
                    'original_formatted': row['original_formatted'],
                    'source': row['source'],
                    'image_url': row['image_url'],
                    'timestamp': row['timestamp'],
                    'history_id': row['history_id']
                })

            return items

        except Exception as e:
            print(f"Error searching items: {e}")
            return []

    # ===== AUTO-SCRAPER METHODS =====

    def create_scraper_run(self, run_id: str, config: Dict = None) -> bool:
        """Create a new scraper run entry"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO scraper_runs (run_id, status, started_at, config)
                VALUES (?, 'running', ?, ?)
            ''', (run_id, datetime.datetime.now(), json.dumps(config or {})))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error creating scraper run: {e}")
            return False

    def update_scraper_run(self, run_id: str, updates: Dict) -> bool:
        """Update scraper run with progress or completion"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            set_clauses = []
            values = []

            for key, value in updates.items():
                if key in ['status', 'completed_at', 'total_brands', 'total_categories',
                           'total_models', 'total_products', 'new_products', 'updated_products',
                           'errors_count', 'current_brand', 'current_category', 'current_model']:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
                elif key in ['checkpoint', 'error_log']:
                    set_clauses.append(f"{key} = ?")
                    values.append(json.dumps(value) if value else None)

            if not set_clauses:
                return False

            values.append(run_id)
            query = f"UPDATE scraper_runs SET {', '.join(set_clauses)} WHERE run_id = ?"

            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating scraper run: {e}")
            return False

    def get_scraper_run(self, run_id: str) -> Optional[Dict]:
        """Get scraper run details"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM scraper_runs WHERE run_id = ?
            ''', (run_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                'id': row['id'],
                'run_id': row['run_id'],
                'status': row['status'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'total_brands': row['total_brands'],
                'total_categories': row['total_categories'],
                'total_models': row['total_models'],
                'total_products': row['total_products'],
                'new_products': row['new_products'],
                'updated_products': row['updated_products'],
                'errors_count': row['errors_count'],
                'current_brand': row['current_brand'],
                'current_category': row['current_category'],
                'current_model': row['current_model'],
                'checkpoint': json.loads(row['checkpoint']) if row['checkpoint'] else None,
                'error_log': json.loads(row['error_log']) if row['error_log'] else [],
                'config': json.loads(row['config']) if row['config'] else {}
            }

        except Exception as e:
            print(f"Error getting scraper run: {e}")
            return None

    def get_scraper_runs_list(self, limit: int = 20) -> List[Dict]:
        """Get list of recent scraper runs"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, run_id, status, started_at, completed_at,
                       total_brands, total_categories, total_models, total_products,
                       new_products, updated_products, errors_count
                FROM scraper_runs
                ORDER BY started_at DESC
                LIMIT ?
            ''', (limit,))

            runs = []
            for row in cursor.fetchall():
                runs.append({
                    'id': row['id'],
                    'run_id': row['run_id'],
                    'status': row['status'],
                    'started_at': row['started_at'],
                    'completed_at': row['completed_at'],
                    'total_brands': row['total_brands'],
                    'total_categories': row['total_categories'],
                    'total_models': row['total_models'],
                    'total_products': row['total_products'],
                    'new_products': row['new_products'],
                    'updated_products': row['updated_products'],
                    'errors_count': row['errors_count']
                })

            return runs

        except Exception as e:
            print(f"Error getting scraper runs list: {e}")
            return []

    def save_brand(self, name: str, slug: str, url: str) -> int:
        """Save or update brand, returns brand_id"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO ms_brands (name, slug, url, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    updated_at = excluded.updated_at
            ''', (name, slug, url, datetime.datetime.now()))

            conn.commit()

            cursor.execute('SELECT id FROM ms_brands WHERE slug = ?', (slug,))
            return cursor.fetchone()['id']

        except Exception as e:
            print(f"Error saving brand: {e}")
            return 0

    def save_category(self, brand_id: int, name: str, slug: str, url: str) -> int:
        """Save or update category, returns category_id"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO ms_categories (brand_id, name, slug, url, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(brand_id, slug) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    updated_at = excluded.updated_at
            ''', (brand_id, name, slug, url, datetime.datetime.now()))

            conn.commit()

            cursor.execute('SELECT id FROM ms_categories WHERE brand_id = ? AND slug = ?', (brand_id, slug))
            return cursor.fetchone()['id']

        except Exception as e:
            print(f"Error saving category: {e}")
            return 0

    def save_model(self, category_id: int, name: str, slug: str, url: str) -> int:
        """Save or update model, returns model_id"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO ms_models (category_id, name, slug, url, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(category_id, slug) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    updated_at = excluded.updated_at
            ''', (category_id, name, slug, url, datetime.datetime.now()))

            conn.commit()

            cursor.execute('SELECT id FROM ms_models WHERE category_id = ? AND slug = ?', (category_id, slug))
            return cursor.fetchone()['id']

        except Exception as e:
            print(f"Error saving model: {e}")
            return 0

    def save_product(self, product_data: Dict) -> Tuple[int, bool]:
        """
        Save or update product, returns (product_id, is_new)
        is_new indicates if this was a new insert or an update
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if product exists
            cursor.execute('SELECT id, price, stock_status FROM ms_products WHERE sku = ?',
                          (product_data['sku'],))
            existing = cursor.fetchone()

            is_new = existing is None
            now = datetime.datetime.now()

            if is_new:
                # Insert new product
                cursor.execute('''
                    INSERT INTO ms_products (
                        model_id, sku, title, description, price, stock_status,
                        availability, condition, product_url, image_urls,
                        variant_details, compatibility, bulk_discounts,
                        last_scraped_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product_data['model_id'],
                    product_data['sku'],
                    product_data['title'],
                    product_data.get('description', ''),
                    product_data.get('price'),
                    product_data.get('stock_status', ''),
                    product_data.get('availability', ''),
                    product_data.get('condition', ''),
                    product_data['product_url'],
                    json.dumps(product_data.get('image_urls', [])),
                    json.dumps(product_data.get('variant_details', {})),
                    json.dumps(product_data.get('compatibility', [])),
                    json.dumps(product_data.get('bulk_discounts', {})),
                    now, now, now
                ))

                product_id = cursor.lastrowid

            else:
                # Update existing product
                product_id = existing['id']

                cursor.execute('''
                    UPDATE ms_products SET
                        title = ?, description = ?, price = ?, stock_status = ?,
                        availability = ?, condition = ?, image_urls = ?,
                        variant_details = ?, compatibility = ?, bulk_discounts = ?,
                        last_scraped_at = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    product_data['title'],
                    product_data.get('description', ''),
                    product_data.get('price'),
                    product_data.get('stock_status', ''),
                    product_data.get('availability', ''),
                    product_data.get('condition', ''),
                    json.dumps(product_data.get('image_urls', [])),
                    json.dumps(product_data.get('variant_details', {})),
                    json.dumps(product_data.get('compatibility', [])),
                    json.dumps(product_data.get('bulk_discounts', {})),
                    now, now, product_id
                ))

                # Track price change
                if existing and product_data.get('price') != existing['price']:
                    cursor.execute('''
                        INSERT INTO ms_price_history (product_id, price, stock_status, recorded_at)
                        VALUES (?, ?, ?, ?)
                    ''', (product_id, product_data.get('price'),
                          product_data.get('stock_status', ''), now))

            conn.commit()
            return (product_id, is_new)

        except Exception as e:
            print(f"Error saving product: {e}")
            return (0, False)

    def get_scraper_statistics(self) -> Dict:
        """Get comprehensive auto-scraper statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            stats = {}

            # Total counts
            cursor.execute('SELECT COUNT(*) as count FROM ms_brands')
            stats['total_brands'] = cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) as count FROM ms_categories')
            stats['total_categories'] = cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) as count FROM ms_models')
            stats['total_models'] = cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) as count FROM ms_products')
            stats['total_products'] = cursor.fetchone()['count']

            # Recent runs
            cursor.execute('''
                SELECT COUNT(*) as count FROM scraper_runs
                WHERE started_at >= datetime('now', '-7 days')
            ''')
            stats['runs_last_7_days'] = cursor.fetchone()['count']

            # Last run info
            cursor.execute('''
                SELECT status, started_at, completed_at, total_products
                FROM scraper_runs
                ORDER BY started_at DESC
                LIMIT 1
            ''')
            last_run = cursor.fetchone()
            if last_run:
                stats['last_run_status'] = last_run['status']
                stats['last_run_date'] = last_run['started_at']
                stats['last_run_products'] = last_run['total_products']

            # Products with price changes (last 7 days)
            cursor.execute('''
                SELECT COUNT(DISTINCT product_id) as count
                FROM ms_price_history
                WHERE recorded_at >= datetime('now', '-7 days')
            ''')
            stats['price_changes_7_days'] = cursor.fetchone()['count']

            # Average price
            cursor.execute('SELECT AVG(price) as avg FROM ms_products WHERE price > 0')
            avg_result = cursor.fetchone()
            stats['avg_price'] = round(avg_result['avg'] or 0, 2)

            # In stock products
            cursor.execute('''
                SELECT COUNT(*) as count FROM ms_products
                WHERE stock_status = 'in_stock'
            ''')
            stats['in_stock_products'] = cursor.fetchone()['count']

            return stats

        except Exception as e:
            print(f"Error getting scraper statistics: {e}")
            return {}

    def search_products(self, query: str = '', brand: str = '', category: str = '',
                       model: str = '', limit: int = 100) -> List[Dict]:
        """Search products with filters"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            sql = '''
                SELECT
                    p.*,
                    m.name as model_name,
                    c.name as category_name,
                    b.name as brand_name
                FROM ms_products p
                JOIN ms_models m ON p.model_id = m.id
                JOIN ms_categories c ON m.category_id = c.id
                JOIN ms_brands b ON c.brand_id = b.id
                WHERE 1=1
            '''
            params = []

            if query:
                sql += ' AND (p.title LIKE ? OR p.description LIKE ? OR p.sku LIKE ?)'
                params.extend([f'%{query}%', f'%{query}%', f'%{query}%'])

            if brand:
                sql += ' AND b.slug = ?'
                params.append(brand)

            if category:
                sql += ' AND c.slug = ?'
                params.append(category)

            if model:
                sql += ' AND m.slug = ?'
                params.append(model)

            sql += ' ORDER BY p.updated_at DESC LIMIT ?'
            params.append(limit)

            cursor.execute(sql, params)

            products = []
            for row in cursor.fetchall():
                products.append({
                    'id': row['id'],
                    'sku': row['sku'],
                    'title': row['title'],
                    'description': row['description'],
                    'price': row['price'],
                    'stock_status': row['stock_status'],
                    'availability': row['availability'],
                    'condition': row['condition'],
                    'product_url': row['product_url'],
                    'image_urls': json.loads(row['image_urls']) if row['image_urls'] else [],
                    'brand_name': row['brand_name'],
                    'category_name': row['category_name'],
                    'model_name': row['model_name'],
                    'updated_at': row['updated_at']
                })

            return products

        except Exception as e:
            print(f"Error searching products: {e}")
            return []

# ===== USER MANAGEMENT =====

    def _bootstrap_auth(self):
        """Bootstrap the initial admin user from environment variables if the users table is empty."""
        import os

        # We need to import this carefully or we can just read the env.
        # It's better to just use os.environ or dotenv here.
        # Actually auth.py handles the default env. Let's just do it directly.

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM users")
        row = cursor.fetchone()
        if row and row['count'] == 0:
            username = os.environ.get("AUTH_USERNAME", "admin")
            role = os.environ.get("AUTH_ROLE", "admin")
            password = os.environ.get("AUTH_PASSWORD", "admin")
            password_hash = os.environ.get("AUTH_PASSWORD_HASH", "")

            if not password_hash and password:
                from werkzeug.security import generate_password_hash
                password_hash = generate_password_hash(password)

            if password_hash:
                print(f"Bootstrapping initial user: {username} ({role})")
                self.add_user(username, password_hash, role)


    def get_all_users(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, role, created_at FROM users')
        return [dict(row) for row in cursor.fetchall()]

    def get_user_by_username(self, username):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def add_user(self, username, password_hash, role):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role)
                VALUES (?, ?, ?)
            """, (username, password_hash, role))
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            conn.rollback()
            print(f'Error adding user: {e}')
            return None

    def update_user(self, user_id, role=None, password_hash=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if password_hash and role:
                cursor.execute('UPDATE users SET password_hash = ?, role = ? WHERE id = ?', (password_hash, role, user_id))
            elif password_hash:
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (password_hash, user_id))
            elif role:
                cursor.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f'Error updating user: {e}')
            return False

    def delete_user(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f'Error deleting user: {e}')
            return False

class MultiDatabaseManager:
    """Facade that keeps one SQLite database per scraper/site while aggregating reads."""

    def __init__(self, base_dir: str = None):
        app_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir or os.environ.get("DATABASES_DIR") or os.path.join(app_dir, "data", "site_dbs")
        os.makedirs(self.base_dir, exist_ok=True)
        self.app_dir = app_dir
        self.managers: Dict[str, DatabaseManager] = {}

        for scraper_key in SCRAPER_CONFIG.keys():
            db_path = os.path.join(self.base_dir, get_db_filename(scraper_key))
            self._seed_site_database(scraper_key, db_path)
            self.managers[scraper_key] = DatabaseManager(db_path=db_path)

    def _seed_site_database(self, scraper_key: str, target_path: str) -> None:
        if os.path.exists(target_path):
            return

        legacy_candidates = []
        if scraper_key == 'standard':
            legacy_candidates.extend([
                os.path.join(self.app_dir, "mobilesentrix.db"),
                os.path.join(self.app_dir, "data", "mobilesentrix.db"),
            ])

        for candidate in legacy_candidates:
            if candidate and os.path.exists(candidate):
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(candidate, target_path)
                return

    def _get_manager(self, scraper_key: str) -> DatabaseManager:
        return self.managers.get(scraper_key, self.managers['standard'])

    @staticmethod
    def _public_history_id(scraper_key: str, raw_history_id: str) -> str:
        return f"{scraper_key}:{raw_history_id}"

    def _parse_history_id(self, history_id: str) -> Tuple[Optional[str], str]:
        normalized = str(history_id or '').strip()
        if ':' in normalized:
            scraper_key, raw_history_id = normalized.split(':', 1)
            if scraper_key in self.managers and raw_history_id:
                return scraper_key, raw_history_id
        return None, normalized

    @staticmethod
    def _history_timestamp_to_ms(timestamp_value) -> int:
        if timestamp_value in (None, ''):
            return 0
        if isinstance(timestamp_value, (int, float)):
            return int(timestamp_value)
        text = str(timestamp_value)
        if 'T' in text:
            try:
                return int(datetime.datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp() * 1000)
            except Exception:
                return 0
        try:
            return int(float(text))
        except Exception:
            return 0

    @staticmethod
    def _format_session_label(timestamp_value, *, latest: bool) -> str:
        if not timestamp_value:
            return 'Never' if latest else 'N/A'
        try:
            text = str(timestamp_value)
            if '+' in text or 'Z' in text:
                ts = datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))
                if ts.tzinfo is None:
                    ts = pytz.UTC.localize(ts)
                ts_pakistan = ts.astimezone(PAKISTAN_TZ)
            else:
                ts = datetime.datetime.fromisoformat(text)
                ts_pakistan = PAKISTAN_TZ.localize(ts)
            return ts_pakistan.strftime('%b %d' if latest else '%b %d, %Y')
        except Exception:
            return 'Recent' if latest else 'Unknown'

    def _decorate_history(self, scraper_key: str, history: Optional[Dict]) -> Optional[Dict]:
        if not history:
            return None
        decorated = dict(history)
        decorated['id'] = self._public_history_id(scraper_key, history.get('id', ''))
        decorated['scraper_key'] = scraper_key
        decorated['database_key'] = get_db_key(scraper_key)
        return decorated

    def _decorate_watchlist_item(self, scraper_key: str, item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not item:
            return None
        decorated = dict(item)
        decorated['scraper_key'] = scraper_key
        decorated['database_key'] = get_db_key(scraper_key)
        return decorated

    @staticmethod
    def _watchlist_sort_key(item: Dict[str, Any]) -> Tuple[float, str]:
        timestamp = str(item.get('updated_at') or item.get('created_at') or '')
        if timestamp:
            try:
                dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = PAKISTAN_TZ.localize(dt)
                return dt.timestamp(), str(item.get('title') or '')
            except Exception:
                pass
        return 0.0, str(item.get('title') or '')

    def close_connection(self):
        for manager in self.managers.values():
            manager.close_connection()

    def save_fetch_history(self, history_id: str, urls: List[str], items: List[Any], rules: Dict) -> bool:
        urls_by_scraper = split_urls_by_scraper(urls)
        items_by_scraper: Dict[str, List[Any]] = {}

        for item in items or []:
            item_dict = asdict(item) if hasattr(item, '__dict__') else dict(item or {})
            scraper_key = detect_scraper_key(item_dict.get('url') or item_dict.get('site'))
            items_by_scraper.setdefault(scraper_key, []).append(item)

        all_scraper_keys = list(dict.fromkeys([*urls_by_scraper.keys(), *items_by_scraper.keys()]))
        if not all_scraper_keys:
            all_scraper_keys = ['standard']

        success = True
        for scraper_key in all_scraper_keys:
            site_urls = urls_by_scraper.get(scraper_key, [])
            site_items = items_by_scraper.get(scraper_key, [])
            if not site_urls and site_items:
                site_urls = sorted({
                    str(getattr(item, 'url', '') or '')
                    for item in site_items
                    if str(getattr(item, 'url', '') or '').strip()
                })
            success = self._get_manager(scraper_key).save_fetch_history(history_id, site_urls, site_items, rules) and success

        return success

    def get_latest_history_for_urls(self, urls: List[str]) -> Optional[Dict]:
        urls_by_scraper = split_urls_by_scraper(urls)
        combined_histories = []

        for scraper_key, site_urls in urls_by_scraper.items():
            history = self._get_manager(scraper_key).get_latest_history_for_urls(site_urls)
            if history:
                combined_histories.append((scraper_key, history))

        if not combined_histories:
            return None

        if len(combined_histories) == 1:
            scraper_key, history = combined_histories[0]
            return self._decorate_history(scraper_key, history)

        latest_timestamp = max(self._history_timestamp_to_ms(history.get('timestamp')) for _, history in combined_histories)
        combined_items = []
        combined_urls = []
        previous_ids = []
        for scraper_key, history in combined_histories:
            combined_items.extend(history.get('items', []))
            combined_urls.extend(history.get('urls', []))
            previous_ids.append(self._public_history_id(scraper_key, history.get('id', '')))

        return {
            'id': '|'.join(previous_ids),
            'timestamp': latest_timestamp,
            'urls': combined_urls,
            'items_count': len(combined_items),
            'rules': {},
            'items': combined_items,
            'scraper_key': 'multi',
            'database_key': 'multi',
        }

    def get_history_list(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        sample_size = max(limit + offset, limit, 50)
        histories = []
        for scraper_key, manager in self.managers.items():
            for history in manager.get_history_list(limit=sample_size, offset=0):
                decorated = self._decorate_history(scraper_key, history)
                if decorated:
                    histories.append(decorated)

        histories.sort(key=lambda entry: entry.get('timestamp') or 0, reverse=True)
        return histories[offset:offset + limit]

    def get_history_detail(self, history_id: str) -> Optional[Dict]:
        scraper_key, raw_history_id = self._parse_history_id(history_id)
        if scraper_key:
            return self._decorate_history(scraper_key, self._get_manager(scraper_key).get_history_detail(raw_history_id))

        for candidate_key, manager in self.managers.items():
            history = manager.get_history_detail(raw_history_id)
            if history:
                return self._decorate_history(candidate_key, history)
        return None

    def delete_history(self, history_id: str) -> bool:
        scraper_key, raw_history_id = self._parse_history_id(history_id)
        if scraper_key:
            return self._get_manager(scraper_key).delete_history(raw_history_id)

        for manager in self.managers.values():
            if manager.delete_history(raw_history_id):
                return True
        return False

    def prune_histories_for_urls(self, urls: List[str], keep: int = 2) -> List[str]:
        deleted_public_ids = []
        urls_by_scraper = split_urls_by_scraper(urls)
        for scraper_key, site_urls in urls_by_scraper.items():
            raw_deleted = self._get_manager(scraper_key).prune_histories_for_urls(site_urls, keep=keep)
            deleted_public_ids.extend(
                self._public_history_id(scraper_key, history_id)
                for history_id in raw_deleted
            )
        return deleted_public_ids

    def get_product_metadata_cache(self, urls: List[str], scraper_key: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        if not urls:
            return {}
        if scraper_key and scraper_key in self.managers:
            return self._get_manager(scraper_key).get_product_metadata_cache(urls)
        result: Dict[str, Dict[str, Any]] = {}
        for manager in self.managers.values():
            result.update(manager.get_product_metadata_cache(urls))
        return result

    def save_watchlist_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        item_dict = asdict(item) if hasattr(item, '__dict__') else dict(item or {})
        scraper_key = detect_scraper_key(item_dict.get('url') or item_dict.get('site'))
        saved = self._get_manager(scraper_key).save_watchlist_item(item_dict)
        return self._decorate_watchlist_item(scraper_key, saved)

    def get_watchlist_item(self, url: str) -> Optional[Dict[str, Any]]:
        normalized_url = str(url or '').strip()
        if not normalized_url:
            return None

        scraper_key = detect_scraper_key(normalized_url)
        item = self._get_manager(scraper_key).get_watchlist_item(normalized_url)
        if item:
            return self._decorate_watchlist_item(scraper_key, item)

        for candidate_key, manager in self.managers.items():
            if candidate_key == scraper_key:
                continue
            item = manager.get_watchlist_item(normalized_url)
            if item:
                return self._decorate_watchlist_item(candidate_key, item)
        return None

    def get_watchlist_items(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for scraper_key, manager in self.managers.items():
            for item in manager.get_watchlist_items():
                decorated = self._decorate_watchlist_item(scraper_key, item)
                if decorated:
                    items.append(decorated)

        items.sort(key=self._watchlist_sort_key, reverse=True)
        if limit is not None:
            return items[:max(1, int(limit))]
        return items

    def get_watchlist_urls(self) -> List[str]:
        urls = []
        seen = set()
        for manager in self.managers.values():
            for url in manager.get_watchlist_urls():
                normalized = str(url or '').strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                urls.append(normalized)
        return urls

    def remove_watchlist_item(self, url: str) -> bool:
        normalized_url = str(url or '').strip()
        if not normalized_url:
            return False

        scraper_key = detect_scraper_key(normalized_url)
        if self._get_manager(scraper_key).remove_watchlist_item(normalized_url):
            return True

        for candidate_key, manager in self.managers.items():
            if candidate_key == scraper_key:
                continue
            if manager.remove_watchlist_item(normalized_url):
                return True
        return False

    def clear_watchlist(self) -> int:
        return sum(manager.clear_watchlist() for manager in self.managers.values())

    def get_statistics(self) -> Dict:
        now_pakistan = get_pakistan_time()
        thirty_days_ago_str = (now_pakistan - datetime.timedelta(days=30)).isoformat()

        total_histories = 0
        total_items = 0
        recent_histories = 0
        database_size = 0
        successful_items = 0
        priced_items = 0
        sum_prices = 0.0
        total_value = 0.0
        highest_price = 0.0
        lowest_price = None
        latest_timestamp = None
        oldest_timestamp = None
        unique_models = set()
        unique_sites = set()
        site_counts: Dict[str, int] = {}

        for manager in self.managers.values():
            conn = manager.get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) AS count FROM fetch_history')
            total_histories += cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) AS count FROM items')
            db_total_items = cursor.fetchone()['count']
            total_items += db_total_items

            cursor.execute('SELECT COUNT(*) AS count FROM fetch_history WHERE timestamp >= ?', (thirty_days_ago_str,))
            recent_histories += cursor.fetchone()['count']

            cursor.execute("SELECT page_count * page_size AS size FROM pragma_page_count(), pragma_page_size()")
            database_size += cursor.fetchone()['size'] or 0

            cursor.execute('''
                SELECT
                    COUNT(CASE WHEN price_value IS NOT NULL AND price_value > 0 THEN 1 END) AS successful,
                    SUM(CASE WHEN price_value IS NOT NULL AND price_value > 0 THEN price_value ELSE 0 END) AS price_sum,
                    MAX(CASE WHEN price_value IS NOT NULL AND price_value > 0 THEN price_value END) AS max_price,
                    MIN(CASE WHEN price_value IS NOT NULL AND price_value > 0 THEN price_value END) AS min_price
                FROM items
            ''')
            price_row = cursor.fetchone()
            successful_items += price_row['successful'] or 0
            priced_items += price_row['successful'] or 0
            sum_prices += float(price_row['price_sum'] or 0.0)
            total_value += float(price_row['price_sum'] or 0.0)
            highest_price = max(highest_price, float(price_row['max_price'] or 0.0))
            if price_row['min_price'] is not None:
                min_price = float(price_row['min_price'])
                lowest_price = min(min_price, lowest_price) if lowest_price is not None else min_price

            cursor.execute('''
                SELECT DISTINCT
                    CASE
                        WHEN title LIKE '%iPhone%' THEN 'iPhone'
                        WHEN title LIKE '%Galaxy%' THEN 'Galaxy'
                        WHEN title LIKE '%iPad%' THEN 'iPad'
                        WHEN title LIKE '%Pixel%' THEN 'Pixel'
                        WHEN title LIKE '%OnePlus%' THEN 'OnePlus'
                        ELSE SUBSTR(title, 1, 20)
                    END AS model_label
                FROM items
                WHERE title != ''
            ''')
            unique_models.update(row['model_label'] for row in cursor.fetchall() if row['model_label'])

            cursor.execute('SELECT DISTINCT site FROM items WHERE site != ""')
            unique_sites.update(str(row['site']) for row in cursor.fetchall() if row['site'])

            cursor.execute('SELECT site, COUNT(*) AS item_count FROM items WHERE site != "" GROUP BY site')
            for row in cursor.fetchall():
                site_name = str(row['site'] or '')
                site_counts[site_name] = site_counts.get(site_name, 0) + int(row['item_count'] or 0)

            cursor.execute('SELECT MAX(timestamp) AS latest_timestamp, MIN(timestamp) AS oldest_timestamp FROM fetch_history')
            ts_row = cursor.fetchone()
            if ts_row['latest_timestamp']:
                candidate = str(ts_row['latest_timestamp'])
                if latest_timestamp is None or self._history_timestamp_to_ms(candidate) > self._history_timestamp_to_ms(latest_timestamp):
                    latest_timestamp = candidate
            if ts_row['oldest_timestamp']:
                candidate = str(ts_row['oldest_timestamp'])
                if oldest_timestamp is None or self._history_timestamp_to_ms(candidate) < self._history_timestamp_to_ms(oldest_timestamp):
                    oldest_timestamp = candidate

        avg_items = round(total_items / max(total_histories, 1), 1)
        avg_price = round(sum_prices / max(priced_items, 1), 2) if priced_items else 0.0
        success_rate = round((successful_items / max(total_items, 1)) * 100, 1) if total_items else 0.0

        top_site = 'N/A'
        if site_counts:
            top_site = max(site_counts.items(), key=lambda item: item[1])[0]
            top_site = top_site.replace('www.', '').replace('.com', '').replace('.ca', '')
            if '.' in top_site:
                top_site = top_site.split('.')[0]
            top_site = top_site.capitalize()

        return {
            'total_histories': total_histories,
            'total_items': total_items,
            'recent_histories': recent_histories,
            'unique_models': len(unique_models),
            'unique_sites': len(unique_sites),
            'database_size': database_size,
            'avg_items_per_session': avg_items,
            'avg_price': avg_price,
            'success_rate': success_rate,
            'top_site': top_site,
            'latest_session': self._format_session_label(latest_timestamp, latest=True),
            'oldest_session': self._format_session_label(oldest_timestamp, latest=False),
            'total_value': round(total_value, 2),
            'highest_price': round(highest_price, 2),
            'lowest_price': round(lowest_price or 0, 2),
        }

    def cleanup_old_entries(self, days: int = 90) -> int:
        return sum(manager.cleanup_old_entries(days) for manager in self.managers.values())

    def search_items(self, query: str, limit: int = 100) -> List[Dict]:
        results = []
        for scraper_key, manager in self.managers.items():
            for item in manager.search_items(query, limit):
                enriched = dict(item)
                enriched['history_id'] = self._public_history_id(scraper_key, item.get('history_id', ''))
                enriched['scraper_key'] = scraper_key
                enriched['database_key'] = get_db_key(scraper_key)
                results.append(enriched)

        results.sort(key=lambda item: self._history_timestamp_to_ms(item.get('timestamp')), reverse=True)
        return results[:limit]

    def __getattr__(self, name: str):
        """Fallback to the default site database manager for advanced APIs."""
        return getattr(self.managers['standard'], name)


# Global database instance




    # ===== USER MANAGEMENT DELEGATORS =====
    def get_all_users(self):
        return self.managers['standard'].get_all_users()

    def get_user_by_username(self, username):
        return self.managers['standard'].get_user_by_username(username)

    def get_user_by_id(self, user_id):
        return self.managers['standard'].get_user_by_id(user_id)

    def add_user(self, username, password_hash, role):
        return self.managers['standard'].add_user(username, password_hash, role)

    def update_user(self, user_id, role=None, password_hash=None):
        return self.managers['standard'].update_user(user_id, role, password_hash)

    def delete_user(self, user_id):
        return self.managers['standard'].delete_user(user_id)


db_manager = MultiDatabaseManager()
