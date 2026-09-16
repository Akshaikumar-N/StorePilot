import os
from agents.main_agent import get_agent_executor

def run_tests():
    agent = get_agent_executor("test_eval_1")
    
    scenarios = [
        "new item: Amul Butter 100g, GST 12%, MRP ₹62, cost ₹45, stock 0, reorder 10, unit piece",
        "new item: Aashirvaad atta 5kg, GST 5%, MRP ₹200, cost ₹180, stock 0, reorder 5, unit packet",
        "new item: Maggi 70g, GST 18%, MRP ₹14, cost ₹12, stock 0, reorder 20, unit packet",
        "50 packets of Maggi came in, cost ₹12, MRP ₹14",
        "20 Aashirvaad atta 5kg came in",
        "30 Amul Butter 100g came in",
        "how much maggi is left?",
        "put ₹500 on Ramesh's credit",
        "make a bill: 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter",
        "drop the butter, make it 6 Maggi",
        "finalize the bill with UPI",
        "Ramesh paid ₹300",
        "Ramesh's balance?",
        "what's running out?",
        "always assume UPI unless I say cash",
        "send me that bill as a PDF",
        "make this week's sales analysis deck"
    ]
    
    history = ""
    for s in scenarios:
        print(f"\n--- USER: {s} ---")
        try:
            res = agent.invoke({"input": s, "chat_history": history})
            output = res["output"]
            print(f"AGENT: {output}")
            history += f"User: {s}\nAgent: {output}\n"
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    run_tests()
