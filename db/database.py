import os
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from dotenv import load_dotenv

load_dotenv()

DB_URL = "sqlite:///store.db"

def init_db():
    engine = create_engine(DB_URL)
    
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
        
        res = conn.exec_driver_sql("SELECT count(*) FROM products").scalar()
        if res == 0:
            conn.exec_driver_sql("""
                INSERT INTO products (product_name, cost_price, mrp, stock, reorder_level, unit, gst_rate) VALUES
                ('Aashirvaad Atta 5kg', 180, 200, 20, 5, 'packet', 5),
                ('Tata Salt 1kg', 20, 24, 50, 10, 'packet', 5),
                ('Amul Butter 100g', 45, 50, 30, 10, 'piece', 12),
                ('Maggi 70g', 12, 14, 100, 20, 'packet', 18),
                ('Sugar (Loose)', 38, 42, 50, 10, 'kg', 0)
            """)
        conn.commit()

def get_engine():
    return create_engine(DB_URL)

def get_db() -> SQLDatabase:
    """Returns a Langchain SQLDatabase instance."""
    init_db()
    return SQLDatabase.from_uri(DB_URL)

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
