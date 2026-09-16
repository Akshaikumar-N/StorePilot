import os
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_groq import ChatGroq
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate

from db.database import get_db
from tools.generate_docs import generate_invoice_pdf, generate_analysis_deck

def get_agent_executor(chat_id: str):

    llm = ChatGroq(
        model="openai/gpt-oss-120b",
        temperature=0.0
    )
    

    db = get_db(chat_id)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm, use_query_checker=False)
    

    tools = toolkit.get_tools() + [generate_invoice_pdf, generate_analysis_deck]
    

    template = """You are a Supermarket Ops Agent running an Indian kirana store. 
You interact with the owner to manage stock, build bills, and handle credit_ledger (customer credit).
You have access to a SQLite database. 

Important Database Rules:
1. `products` table: Has cost_price, mrp, stock, gst_rate. NEVER SELL IF STOCK < quantity. You must manually check stock before inserting a bill item. Update stock atomically.
2. `bills` table: When finalizing a bill, insert into `bills` (get the bill_id) and then insert into `bill_items`.
3. `credit_ledger` table: Track credit balances. If payment is 'khata' or 'credit', insert/update the customer's balance.

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
