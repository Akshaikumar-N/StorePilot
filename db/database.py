import os
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

load_dotenv()

def get_db_url(chat_id: str) -> str:
    return f"sqlite:///store_{chat_id}.db"

def init_db(chat_id: str):
    engine = create_engine(get_db_url(chat_id))
    
    with engine.connect() as conn:
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL UNIQUE,
            cost_price REAL NOT NULL DEFAULT 0,
            mrp REAL NOT NULL DEFAULT 0,
            stock REAL NOT NULL DEFAULT 0,
            reorder_level REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT 'piece',
            gst_rate REAL NOT NULL DEFAULT 0,
            hsn_code TEXT
        );
        """)
        
        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            total_amount REAL NOT NULL DEFAULT 0,
            tax_amount REAL NOT NULL DEFAULT 0,
            payment_mode TEXT,
            customer_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER,
            product_name TEXT,
            quantity REAL,
            price REAL,
            tax_amount REAL,
            total REAL,
            FOREIGN KEY(bill_id) REFERENCES bills(id)
        );
        """)

        conn.exec_driver_sql("""
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL UNIQUE,
            balance REAL NOT NULL DEFAULT 0
        );
        """)
        
        conn.commit()

def get_engine(chat_id: str):
    return create_engine(get_db_url(chat_id))

def get_db(chat_id: str) -> SQLDatabase:
    """Returns a Langchain SQLDatabase instance for the specific chat_id."""
    init_db(chat_id)
    return SQLDatabase.from_uri(get_db_url(chat_id))

if __name__ == "__main__":
    print("Run this file with a chat_id to initialize. (e.g. init_db('123'))")
