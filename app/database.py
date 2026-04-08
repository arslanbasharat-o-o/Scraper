"""
Database module for MobileSentrix Extractor
Handles persistent storage of scraping history and items
"""

import sqlite3
import json
import datetime
import re
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import asdict
import threading
import pytz
import os

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
        
        self.init_database()
    
    def get_connection(self):
        """Get thread-local database connection"""
        if not hasattr(_local, 'connection'):
            _local.connection = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
            _local.connection.row_factory = sqlite3.Row  # Enable dict-like access
            _local.connection.execute('PRAGMA foreign_keys = ON')
        return _local.connection

    def close_connection(self):
        """Close the thread-local database connection, if one exists."""
        conn = getattr(_local, 'connection', None)
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
            delattr(_local, 'connection')
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
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

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_timestamp ON fetch_history (timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_urls_key ON fetch_history (urls_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_history_id ON items (history_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_url ON items (url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_site ON items (site)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_items_sku ON items (sku)')

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
    
    def save_fetch_history(self, history_id: str, urls: List[str], items: List[Any], rules: Dict) -> bool:
        """Save fetch history and items to database"""
        try:
            conn = self.get_connection()
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
            conn.rollback()
            return False

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

    def get_latest_history_for_urls(self, urls: List[str]) -> Optional[Dict]:
        """Get the most recent saved session for the exact same target URL set."""
        try:
            urls_key = self.build_urls_key(urls)
            if not urls_key:
                return None

            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id
                FROM fetch_history
                WHERE urls_key = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (urls_key,))
            row = cursor.fetchone()
            if not row:
                return None
            return self.get_history_detail(row['id'])
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

# Global database instance
db_manager = DatabaseManager()
