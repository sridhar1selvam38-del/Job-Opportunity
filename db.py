"""
MySQL Database connection and query helper module.
"""
import pymysql
from pymysql.cursors import DictCursor

DB_CONFIG = {
    'host': 'localhost',
    'user': 'jobuser',
    'password': 'jobpass123',
    'database': 'jobpost_aggregator',
    'charset': 'utf8mb4',
    'cursorclass': DictCursor,
    'autocommit': True
}

def get_db():
    return pymysql.connect(**DB_CONFIG)

def query_db(query, args=(), one=False):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            rv = cursor.fetchall()
            return (rv[0] if rv else None) if one else rv
    finally:
        conn.close()

def execute_db(query, args=()):
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, args)
            last_id = cursor.lastrowid
            affected = cursor.rowcount
            return {'last_id': last_id, 'affected': affected}
    finally:
        conn.close()
