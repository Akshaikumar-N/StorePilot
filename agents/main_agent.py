import os
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate
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

Important Database Schema & Rules:
1. `products` (id, product_name, cost_price, mrp, stock, reorder_level, unit, gst_rate, hsn_code). 
   - OVERSELL GUARD: NEVER SELL IF STOCK < quantity. You MUST manually query and check `stock` before adding an item to a bill.
   - You must update stock atomically: e.g. `UPDATE products SET stock = stock - qty WHERE id = ?`.
2. `pending_bills` & `pending_bill_items`: Use these tables for multi-turn bills. When a user adds items but hasn't finalized, store them here. Do NOT deduct stock until the bill is finalized.
3. `bills` & `bill_items`: When a bill is finalized, move items from pending to here, AND deduct stock from `products`. Set `chat_id` = {current_chat_id}.
4. `credit_ledger` (customer_name, balance): If a user buys on credit, add to their balance. If they pay, subtract from their balance.
5. `preferences` (key, value): Use this to store memory across chats (e.g., default payment mode). Check this table when making assumptions.

When finalizing a bill, calculate taxes correctly based on `gst_rate`.
If a user request is ambiguous (e.g. "add atta" but there are multiple), ask a clarifying question.

For PDF/PPTX generation, use `generate_invoice_pdf` or `generate_analysis_deck` with `chat_id`="{current_chat_id}".
""".replace("{current_chat_id}", str(chat_id))

    template = template_str + """
To answer questions, you have access to the following tools:

{tools}

To use a tool, please use the exact following format:
```
Thought: Do I need to use a tool? Yes
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
```

When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:
```
Thought: Do I need to use a tool? No
Final Answer: [your response here]
```

Begin!
Previous conversation history:
{chat_history}

Question: {input}
Thought:{agent_scratchpad}"""

    prompt = PromptTemplate.from_template(template)
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)
    
    return agent_executor
