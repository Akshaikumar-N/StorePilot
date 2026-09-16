import os
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from tools.kirana_tools import (
    add_new_product, receive_stock, check_stock, get_low_stock_items,
    start_new_bill, add_item_to_bill, edit_bill_item, finalize_bill,
    add_khata_credit, settle_khata_payment, check_khata_balance,
    get_daily_sales, set_preference, get_preference
)
from tools.generate_docs import generate_invoice_pdf, generate_analysis_deck

def get_agent_executor(chat_id: str):

    llm = ChatOpenAI(
        model="openai/gpt-oss-120b",
        temperature=0.0,
        api_key=os.getenv("GROQ_API_KEY"),
        base_url="https://api.groq.com/openai/v1"
    )
    
    tools = [
        add_new_product, receive_stock, check_stock, get_low_stock_items,
        start_new_bill, add_item_to_bill, edit_bill_item, finalize_bill,
        add_khata_credit, settle_khata_payment, check_khata_balance,
        get_daily_sales, set_preference, get_preference,
        generate_invoice_pdf, generate_analysis_deck
    ]
    
    system_prompt = """You are a Supermarket Ops Agent running an Indian kirana store. 
You interact with the owner to manage stock, build bills, and handle khata (customer credit).

CRITICAL INSTRUCTIONS:
- When calling ANY tool, you MUST pass `chat_id`="{current_chat_id}" as the first argument.
- To create a bill:
  1. Call `start_new_bill` to get a `pending_bill_id`.
  2. Call `add_item_to_bill` for each item.
  3. If they change their mind, use `edit_bill_item`.
  4. Finally, call `finalize_bill` to deduct stock and generate the bill.
- If a user asks "Which one?", or a request is ambiguous, ask them a clarifying question.
- Memory: If a user sets a preference, save it using `set_preference`. Before making assumptions (like payment mode), you can check `get_preference`.
""".replace("{current_chat_id}", str(chat_id))

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt + "\nPrevious conversation history:\n{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)
    
    return agent_executor
