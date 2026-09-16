import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.main_agent import get_agent_executor

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


chat_histories = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    chat_histories[chat_id] = ""
    await update.message.reply_text(
        "Welcome to StorePilot (SQL Agent Edition)! How can I help you manage the store today?"
    )

async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    chat_id = update.message.chat_id
    
    if chat_id not in chat_histories:
        chat_histories[chat_id] = ""
        
    history = chat_histories[chat_id]

    try:

        agent_executor = get_agent_executor(str(chat_id))
        result = agent_executor.invoke({
            "input": user_message,
            "chat_history": history
        })
        
        response_text = result["output"]
        

        chat_histories[chat_id] += f"User: {user_message}\nAgent: {response_text}\n"
        

        words = response_text.split()
        for word in words:
            if word.startswith("artifacts/"):
                filepath = word.strip(".,!?")
                if os.path.exists(filepath):
                    await update.message.reply_document(document=open(filepath, 'rb'))
                    
        await update.message.reply_text(response_text)
        
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("Sorry, an error occurred while processing your request.")

if __name__ == '__main__':
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
    
    print("StorePilot is running...")
    app.run_polling()
