"""
Universal Database connection and query helper module.
Supports MySQL/MariaDB with automatic fallback to SQLite for robust cloud deployment.
"""
import os
import sys
import sqlite3

# Support bundled python packages
pkg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'python_packages')
if os.path.exists(pkg_dir) and pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jobpost_aggregator.sqlite')

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'jobuser'),
    'password': os.environ.get('DB_PASSWORD', 'jobpass123'),
    'database': os.environ.get('DB_NAME', 'jobpost_aggregator'),
    'charset': 'utf8mb4',
    'connect_timeout': 1
}

_USE_SQLITE = None

def is_sqlite_mode():
    global _USE_SQLITE
    if _USE_SQLITE is not None:
        return _USE_SQLITE
    try:
        import pymysql
        from pymysql.cursors import DictCursor
        conn = pymysql.connect(cursorclass=DictCursor, autocommit=True, **DB_CONFIG)
        conn.close()
        _USE_SQLITE = False
    except Exception:
        _USE_SQLITE = True
    return _USE_SQLITE

def get_mysql_db():
    import pymysql
    from pymysql.cursors import DictCursor
    return pymysql.connect(cursorclass=DictCursor, autocommit=True, **DB_CONFIG)

def get_sqlite_db():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class DbResult(int):
    def __new__(cls, last_id, affected):
        val = last_id if last_id else affected
        obj = super().__new__(cls, val)
        obj.last_id = last_id
        obj.affected = affected
        return obj

    def __getitem__(self, item):
        if item == 'last_id':
            return self.last_id
        elif item == 'affected':
            return self.affected
        raise KeyError(item)

    def get(self, item, default=None):
        if item == 'last_id':
            return self.last_id
        elif item == 'affected':
            return self.affected
        return default

def query_db(query, args=(), one=False):
    if not is_sqlite_mode():
        try:
            conn = get_mysql_db()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, args)
                    rv = cursor.fetchall()
                    return (rv[0] if rv else None) if one else rv
            finally:
                conn.close()
        except Exception:
            pass  # Fall back to sqlite if mysql drops

    conn = get_sqlite_db()
    try:
        sqlite_query = query.replace('%s', '?').replace('NOW()', 'CURRENT_TIMESTAMP')
        cursor = conn.cursor()
        cursor.execute(sqlite_query, args)
        rows = cursor.fetchall()
        rv = [dict(row) for row in rows]
        return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()

def execute_db(query, args=()):
    if not is_sqlite_mode():
        try:
            conn = get_mysql_db()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, args)
                    last_id = cursor.lastrowid
                    affected = cursor.rowcount
                    return DbResult(last_id, affected)
            finally:
                conn.close()
        except Exception:
            pass  # Fall back to sqlite if mysql drops

    conn = get_sqlite_db()
    try:
        sqlite_query = query.replace('%s', '?').replace('NOW()', 'CURRENT_TIMESTAMP')
        cursor = conn.cursor()
        cursor.execute(sqlite_query, args)
        conn.commit()
        last_id = cursor.lastrowid
        affected = cursor.rowcount
        return DbResult(last_id, affected)
    finally:
        conn.close()

