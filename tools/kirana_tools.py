from langchain.tools import tool
from db.database import get_engine
from sqlalchemy import text
from datetime import datetime

@tool
def add_new_product(chat_id: str, name: str, cost: float, mrp: float, stock: float, reorder: float, unit: str, gst: float) -> str:
    """Adds a new product to the store inventory."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO products (product_name, cost_price, mrp, stock, reorder_level, unit, gst_rate) VALUES (:name, :cost, :mrp, :stock, :reorder, :unit, :gst)"),
            {"name": name, "cost": cost, "mrp": mrp, "stock": stock, "reorder": reorder, "unit": unit, "gst": gst}
        )
        conn.commit()
    return f"Successfully added {name} to inventory."

@tool
def receive_stock(chat_id: str, name: str, qty: float, cost: float = None, mrp: float = None) -> str:
    """Receives new stock for an existing product, and optionally updates cost/mrp."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM products WHERE product_name LIKE :name"), {"name": f"%{name}%"}).fetchone()
        if not res:
            return f"Product matching '{name}' not found. Please add it as a new product first."
        p = res._mapping
        new_cost = cost if cost is not None else p['cost_price']
        new_mrp = mrp if mrp is not None else p['mrp']
        
        conn.execute(
            text("UPDATE products SET stock = stock + :qty, cost_price = :cost, mrp = :mrp WHERE id = :id"),
            {"qty": qty, "cost": new_cost, "mrp": new_mrp, "id": p['id']}
        )
        conn.commit()
    return f"Received {qty} of {p['product_name']}. Stock updated."

@tool
def check_stock(chat_id: str, name: str) -> str:
    """Checks the current stock of a product."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM products WHERE product_name LIKE :name"), {"name": f"%{name}%"}).fetchall()
        if not res:
            return f"Product matching '{name}' not found."
        
        out = []
        for r in res:
            p = r._mapping
            out.append(f"{p['product_name']}: {p['stock']} {p['unit']} left at MRP ₹{p['mrp']}")
        return "\n".join(out)

@tool
def get_low_stock_items(chat_id: str) -> str:
    """Returns items that are at or below their reorder level."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT * FROM products WHERE stock <= reorder_level")).fetchall()
        if not res:
            return "No items are low on stock."
        
        out = ["Low stock items:"]
        for r in res:
            p = r._mapping
            out.append(f"- {p['product_name']}: {p['stock']} left (Reorder at: {p['reorder_level']})")
        return "\n".join(out)

@tool
def start_new_bill(chat_id: str, customer_name: str = None) -> str:
    """Starts building a new bill. Returns the pending_bill_id."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(
            text("INSERT INTO pending_bills (chat_id, customer_name) VALUES (:chat_id, :customer) RETURNING id"),
            {"chat_id": chat_id, "customer": customer_name}
        ).fetchone()
        conn.commit()
        return f"Started new bill #{res[0]}. You can now add items to it."

@tool
def add_item_to_bill(chat_id: str, pending_bill_id: int, product_name: str, qty: float) -> str:
    """Adds an item to a pending bill. ENFORCES OVERSELL GUARD."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        # Check stock
        p = conn.execute(text("SELECT * FROM products WHERE product_name LIKE :name"), {"name": f"%{product_name}%"}).fetchone()
        if not p:
            return f"Product '{product_name}' not found."
        p = p._mapping
        
        # Guardrails: Oversell
        if p['stock'] < qty:
            return f"OVERSELL GUARD BLOCKED: Cannot sell {qty} {p['unit']} of {p['product_name']}. Only {p['stock']} in stock."
            
        # Add to pending
        conn.execute(
            text("INSERT INTO pending_bill_items (pending_bill_id, product_name, quantity) VALUES (:pb_id, :name, :qty)"),
            {"pb_id": pending_bill_id, "name": p['product_name'], "qty": qty}
        )
        conn.commit()
        return f"Added {qty} {p['unit']} of {p['product_name']} to bill #{pending_bill_id}."

@tool
def edit_bill_item(chat_id: str, pending_bill_id: int, product_name: str, new_qty: float) -> str:
    """Edits the quantity of an item in a pending bill. If new_qty is 0, removes it."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        if new_qty <= 0:
            conn.execute(
                text("DELETE FROM pending_bill_items WHERE pending_bill_id = :pb_id AND product_name LIKE :name"),
                {"pb_id": pending_bill_id, "name": f"%{product_name}%"}
            )
            conn.commit()
            return f"Removed {product_name} from bill #{pending_bill_id}."
            
        # Check stock
        p = conn.execute(text("SELECT * FROM products WHERE product_name LIKE :name"), {"name": f"%{product_name}%"}).fetchone()
        if not p:
            return f"Product '{product_name}' not found."
        p = p._mapping
        
        # Guardrails: Oversell
        if p['stock'] < new_qty:
            return f"OVERSELL GUARD BLOCKED: Cannot sell {new_qty} of {p['product_name']}. Only {p['stock']} in stock."
            
        res = conn.execute(
            text("UPDATE pending_bill_items SET quantity = :qty WHERE pending_bill_id = :pb_id AND product_name LIKE :name"),
            {"qty": new_qty, "pb_id": pending_bill_id, "name": f"%{product_name}%"}
        )
        if res.rowcount == 0:
             return f"{product_name} not found in bill #{pending_bill_id}."
        conn.commit()
        return f"Updated {p['product_name']} to {new_qty} in bill #{pending_bill_id}."

@tool
def finalize_bill(chat_id: str, pending_bill_id: int, payment_mode: str) -> str:
    """Finalizes a pending bill. Computes GST, atomically decrements stock, and returns the final bill ID."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        pb = conn.execute(text("SELECT * FROM pending_bills WHERE id = :id"), {"id": pending_bill_id}).fetchone()
        if not pb:
            return f"Pending bill {pending_bill_id} not found or already finalized (Idempotency)."
        pb = pb._mapping
        
        items = conn.execute(text("SELECT * FROM pending_bill_items WHERE pending_bill_id = :id"), {"id": pending_bill_id}).fetchall()
        if not items:
            return "Cannot finalize an empty bill."
            
        total_amount = 0
        total_tax = 0
        final_items_data = []
        
        for item in items:
            item = item._mapping
            p = conn.execute(text("SELECT * FROM products WHERE product_name = :name"), {"name": item['product_name']}).fetchone()._mapping
            
            # Idempotency / Concurrency Check: re-verify stock right before decrementing
            if p['stock'] < item['quantity']:
                return f"CONCURRENCY GUARD BLOCKED: Stock for {p['product_name']} dropped below requested {item['quantity']} before finalizing."
            
            qty = item['quantity']
            base_price_ex_gst = p['mrp'] / (1 + (p['gst_rate'] / 100))
            tax_amount = (base_price_ex_gst * (p['gst_rate'] / 100)) * qty
            total_item = p['mrp'] * qty
            
            total_amount += total_item
            total_tax += tax_amount
            
            final_items_data.append({
                "name": p['product_name'], "qty": qty, "price": base_price_ex_gst, "tax": tax_amount, "total": total_item
            })
            
            # Decrement stock
            conn.execute(
                text("UPDATE products SET stock = stock - :qty WHERE product_name = :name"),
                {"qty": qty, "name": p['product_name']}
            )
            
        # Insert finalized bill
        res = conn.execute(
            text("INSERT INTO bills (chat_id, total_amount, tax_amount, payment_mode, customer_name) VALUES (:chat_id, :total, :tax, :pm, :cust) RETURNING id"),
            {"chat_id": chat_id, "total": total_amount, "tax": total_tax, "pm": payment_mode, "cust": pb['customer_name']}
        ).fetchone()
        bill_id = res[0]
        
        # Insert finalized items
        for fd in final_items_data:
            conn.execute(
                text("INSERT INTO bill_items (bill_id, product_name, quantity, price, tax_amount, total) VALUES (:bid, :name, :qty, :price, :tax, :total)"),
                {"bid": bill_id, "name": fd['name'], "qty": fd['qty'], "price": fd['price'], "tax": fd['tax'], "total": fd['total']}
            )
            
        # Delete pending bill (idempotency safety)
        conn.execute(text("DELETE FROM pending_bills WHERE id = :id"), {"id": pending_bill_id})
        conn.execute(text("DELETE FROM pending_bill_items WHERE pending_bill_id = :id"), {"id": pending_bill_id})
        
        conn.commit()
        return f"Bill finalized successfully! Bill ID: {bill_id}. Total: ₹{total_amount:.2f} (Tax: ₹{total_tax:.2f})"

@tool
def add_khata_credit(chat_id: str, customer_name: str, amount: float) -> str:
    """Adds a credit amount to a customer's khata ledger."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO credit_ledger (customer_name, balance) VALUES (:cust, :amt) ON CONFLICT(customer_name) DO UPDATE SET balance = balance + :amt"),
            {"cust": customer_name.lower(), "amt": amount}
        )
        conn.commit()
        return f"Added ₹{amount} to {customer_name}'s khata."

@tool
def settle_khata_payment(chat_id: str, customer_name: str, amount: float) -> str:
    """Settles (pays off) an amount from a customer's khata ledger."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT balance FROM credit_ledger WHERE customer_name = :cust"), {"cust": customer_name.lower()}).fetchone()
        if not res:
            return f"Guardrail: Khata for '{customer_name}' doesn't exist."
            
        conn.execute(
            text("UPDATE credit_ledger SET balance = balance - :amt WHERE customer_name = :cust"),
            {"cust": customer_name.lower(), "amt": amount}
        )
        conn.commit()
        return f"{customer_name} paid ₹{amount} towards their khata."

@tool
def check_khata_balance(chat_id: str, customer_name: str) -> str:
    """Checks the balance of a customer's khata ledger."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT balance FROM credit_ledger WHERE customer_name = :cust"), {"cust": customer_name.lower()}).fetchone()
        if not res:
            return f"Khata for '{customer_name}' doesn't exist."
        return f"{customer_name}'s balance is ₹{res[0]}."

@tool
def get_daily_sales(chat_id: str) -> str:
    """Gets the sales and tax collected for today, grouped by payment mode."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT payment_mode, SUM(total_amount) as tot, SUM(tax_amount) as tax FROM bills WHERE date(created_at) = date('now') GROUP BY payment_mode")).fetchall()
        if not res:
            return "No sales today."
            
        out = ["Today's Sales:"]
        overall = 0
        for r in res:
            pm, tot, tax = r
            # Handle potential None values when there are no sales
            tot = tot or 0
            tax = tax or 0
            if pm is not None:
                out.append(f"- {pm.upper()}: ₹{tot:.2f} (Tax: ₹{tax:.2f})")
            overall += tot
        out.append(f"Total: ₹{overall:.2f}")
        return "\n".join(out)

@tool
def set_preference(chat_id: str, key: str, value: str) -> str:
    """Sets a user preference (e.g., 'default_payment'='UPI', 'default_brand'='Aashirvaad')."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO preferences (key, value) VALUES (:k, :v) ON CONFLICT(key) DO UPDATE SET value = :v"),
            {"k": key, "v": value}
        )
        conn.commit()
        return f"Preference saved: {key} = {value}"

@tool
def get_preference(chat_id: str, key: str) -> str:
    """Gets a user preference by key."""
    engine = get_engine(chat_id)
    with engine.connect() as conn:
        res = conn.execute(text("SELECT value FROM preferences WHERE key = :k"), {"k": key}).fetchone()
        if not res:
            return f"Preference '{key}' not found."
        return res[0]
