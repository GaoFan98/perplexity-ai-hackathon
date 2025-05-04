from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
import os
import logging
import json
from dotenv import load_dotenv

from db.database import get_db, init_db
from api.perplexity import PerplexityAPI
from models.user import User
from scheduler.reminder import setup_scheduler
from scheduler.news_scheduler import setup_news_scheduler
from bot.handlers import setup_handlers

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Perplexity Telegram Bot")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# Initialize telegram bot application
bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Initialize Perplexity API
perplexity_api = PerplexityAPI(PERPLEXITY_API_KEY)

# Setup scheduler for reminders
reminder_scheduler = setup_scheduler(bot_app)
# Store scheduler in bot_data so it can be accessed by handlers
bot_app.bot_data["reminder_scheduler"] = reminder_scheduler

# Setup scheduler for news updates
news_scheduler = setup_news_scheduler(bot_app.bot, perplexity_api)
# Store news scheduler in bot_data
bot_app.bot_data["news_scheduler"] = news_scheduler

# Setup handlers
setup_handlers(bot_app, perplexity_api)

@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on startup."""
    await init_db()
    reminder_scheduler.start()
    news_scheduler.start()
    
    # Set webhook for telegram bot if WEBHOOK_URL is provided
    if WEBHOOK_URL:
        await bot_app.bot.set_webhook(url=f"{WEBHOOK_URL}/telegram/webhook")
        logger.info(f"Webhook set to {WEBHOOK_URL}/telegram/webhook")
    else:
        logger.warning("WEBHOOK_URL not provided, running in polling mode")
        # Start polling in background
        from telegram.ext import ExtBot, Updater
        
        async def start_polling():
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling()
            
        import asyncio
        asyncio.create_task(start_polling())

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown scheduler on application shutdown."""
    reminder_scheduler.shutdown()
    news_scheduler.shutdown()
    if WEBHOOK_URL:
        await bot_app.bot.delete_webhook()
    else:
        await bot_app.stop()

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle telegram webhook requests."""
    data = await request.json()
    logger.info(f"Received webhook: {data}")
    
    # Process update in background
    background_tasks.add_task(process_update, data)
    
    return {"status": "ok"}

async def process_update(data: dict):
    """Process telegram update."""
    update = Update.de_json(data=data, bot=bot_app.bot)
    await bot_app.process_update(update)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 