import os
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from db.database import get_db
from tools.generate_docs import generate_invoice_pdf, generate_analysis_deck

def get_agent_executor(chat_id: str):

    llm = ChatOpenAI(
        model="openai/gpt-oss-120b",
        temperature=0.0,
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )

    db = get_db(chat_id)
    # use_query_checker is disabled to prevent LLM hallucinations on validation
    toolkit = SQLDatabaseToolkit(db=db, llm=llm, use_query_checker=False)

    tools = toolkit.get_tools() + [generate_invoice_pdf, generate_analysis_deck]
    
    template_str = """You are a Supermarket Ops Agent running an Indian kirana store.
You interact with the owner to manage stock, build bills, and handle customer credit (khata).
You have access to a SQLite database representing the store's state.

Exact Database Schema:
1. `products`
   CREATE TABLE products (id INTEGER PRIMARY KEY, product_name TEXT NOT NULL UNIQUE, cost_price REAL NOT NULL DEFAULT 0, mrp REAL NOT NULL DEFAULT 0, stock REAL NOT NULL DEFAULT 0, reorder_level REAL NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT 'piece', gst_rate REAL NOT NULL DEFAULT 0, hsn_code TEXT)
2. `bills`
   CREATE TABLE bills (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, total_amount REAL NOT NULL DEFAULT 0, tax_amount REAL NOT NULL DEFAULT 0, payment_mode TEXT, customer_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
3. `bill_items`
   CREATE TABLE bill_items (id INTEGER PRIMARY KEY, bill_id INTEGER, product_name TEXT, quantity REAL, price REAL, tax_amount REAL, total REAL, FOREIGN KEY(bill_id) REFERENCES bills(id))
4. `credit_ledger`
   CREATE TABLE credit_ledger (id INTEGER PRIMARY KEY, customer_name TEXT NOT NULL UNIQUE, balance REAL NOT NULL DEFAULT 0)
5. `preferences`
   CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)
6. `pending_bills`
   CREATE TABLE pending_bills (id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, customer_name TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
7. `pending_bill_items`
   CREATE TABLE pending_bill_items (id INTEGER PRIMARY KEY, pending_bill_id INTEGER, product_name TEXT, quantity REAL, FOREIGN KEY(pending_bill_id) REFERENCES pending_bills(id))

Important Business Rules:
- OVERSELL GUARD: NEVER SELL IF STOCK < quantity. You MUST manually query and check `stock` in `products` before adding an item to a bill.
- You must update stock atomically: e.g. `UPDATE products SET stock = stock - qty WHERE product_name = ?`.
- `pending_bills` & `pending_bill_items`: Use these tables for multi-turn bills. When a user adds items but hasn't finalized, store them here. Do NOT deduct stock until the bill is finalized.
- `bills` & `bill_items`: When a bill is finalized, move items from pending to here, AND deduct stock from `products`. Set `chat_id` = {current_chat_id}.
- `credit_ledger`: If a user buys on credit, add to their balance. If they pay, subtract from their balance.
- `preferences`: Use this to store memory across chats (e.g., default payment mode). Check this table when making assumptions.

When finalizing a bill, calculate taxes correctly based on `gst_rate`.
If a user request is ambiguous (e.g. "add atta" but there are multiple), ask a clarifying question.

For PDF/PPTX generation, use `generate_invoice_pdf` or `generate_analysis_deck` with `chat_id`="{current_chat_id}".

Previous conversation history:
{chat_history}
""".replace("{current_chat_id}", str(chat_id))

    prompt = ChatPromptTemplate.from_messages([
        ("system", template_str),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    
    return agent_executor
