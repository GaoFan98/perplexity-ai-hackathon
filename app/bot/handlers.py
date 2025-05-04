import logging
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
import asyncio
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from sqlalchemy import select, delete

from db.database import async_session
from models.user import User
from models.chat import ChatMessage
from models.reminder import Reminder
from api.perplexity import PerplexityAPI
from scheduler.reminder import ReminderScheduler
from bot.utils import (
    get_or_create_user, save_message, get_conversation_history, 
    update_conversation_history, create_model_selection_keyboard,
    create_thinking_mode_keyboard, create_settings_keyboard,
    parse_reminder_time, parse_recurrence_pattern, 
    is_image_request, is_reminder_request, extract_reminder_text,
    create_frequency_keyboard, create_subscription_keyboard
)
from services.news_service import NewsService
from models.topic_subscription import TopicSubscription

logger = logging.getLogger(__name__)

# Conversation states
(
    AWAITING_REMINDER_CONFIRMATION,
    AWAITING_PDF_QUESTION,
    AWAITING_TOPIC_FREQUENCY,
) = range(3)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        welcome_text = (
            "👋 Welcome to the Perplexity Telegram Bot!\n\n"
            "I'm powered by Perplexity's Sonar API and can help you with:\n"
            "🔍 Searching the web in real-time\n"
            "🧠 Answering questions with AI reasoning\n"
            "🔔 Setting reminders for important tasks\n"
            "🖼️ Analyzing images you send\n\n"
            "Just type your question or use one of these commands:\n"
            "/settings - Change model, toggle thinking mode, manage reminders\n"
            "/model - Change the AI model used for responses\n"
            "/thinking - Toggle thinking mode on/off\n"
            "/reminder - Set a new reminder\n"
            "/clear - Clear your conversation history\n"
            "/help - Show this message again"
        )
        
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
        
        # Log the conversation start
        await save_message(
            session, 
            user, 
            "system", 
            "Conversation started"
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    help_text = (
        "🤖 *Perplexity Telegram Bot Help*\n\n"
        "*Commands:*\n"
        "/start - Start the bot\n"
        "/settings - Open settings menu\n"
        "/model - Change the AI model\n"
        "/thinking - Toggle thinking mode\n"
        "/reminder - Set a new reminder\n"
        "/list_reminders - List your active reminders\n"
        "/subscribe TOPIC - Subscribe to news on a topic\n"
        "/mysubs - List your news subscriptions\n"
        "/clear - Clear conversation history\n"
        "/help - Show this help message\n\n"
        
        "*Features:*\n"
        "🔍 *Web Search* - Ask any question to search the web\n"
        "🧠 *Thinking Mode* - See the AI's reasoning process\n"
        "🔔 *Reminders* - Set one-time or recurring reminders\n"
        "📰 *News Updates* - Get regular updates on your topics of interest\n"
        "🖼️ *Image Analysis* - Send an image with a question\n\n"
        
        "*Setting Reminders:*\n"
        "- One-time: 'Remind me to call mom tomorrow at 5:00 PM'\n"
        "- Recurring: 'Remind me to check email every day at 9:00 AM'\n\n"
        
        "*News Subscriptions:*\n"
        "- Use `/subscribe AI` to follow a topic (replace AI with any topic)\n"
        "- Choose hourly, daily, or weekly updates\n"
        "- Get breaking news delivered automatically\n\n"
        
        "*Models:*\n"
        "- Sonar Pro - Fast search with grounding\n"
        "- Sonar Reasoning - See step-by-step thinking\n"
        "- Deep Research - Comprehensive answers for complex questions"
    )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /settings command."""
    await update.message.reply_text(
        "⚙️ *Settings*\n\nWhat would you like to configure?",
        reply_markup=create_settings_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /model command."""
    await update.message.reply_text(
        "🤖 *Select Model*\n\nChoose which Perplexity model to use:",
        reply_markup=create_model_selection_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def thinking_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /thinking command."""
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        # Toggle thinking mode
        user.thinking_mode = not user.thinking_mode
        await session.commit()
        
        mode_text = "enabled ✅" if user.thinking_mode else "disabled ❌"
        
        await update.message.reply_text(
            f"🧠 Thinking mode is now {mode_text}\n\n"
            f"{'I will now show my reasoning process when answering questions using reasoning models.' if user.thinking_mode else 'I will now provide direct answers without showing my reasoning process.'}",
            parse_mode=ParseMode.MARKDOWN
        )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /clear command."""
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        # Clear conversation history
        user.conversation_history = "[]"
        await session.commit()
        
        # Delete chat messages from database
        await session.execute(
            delete(ChatMessage).where(ChatMessage.user_id == user.id)
        )
        await session.commit()
        
        await update.message.reply_text(
            "🗑️ Your conversation history has been cleared.",
            parse_mode=ParseMode.MARKDOWN
        )

async def reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /reminder command."""
    await update.message.reply_text(
        "🔔 *New Reminder*\n\n"
        "Please tell me what to remind you about and when.\n\n"
        "*Examples:*\n"
        "- Remind me to call mom tomorrow at 5:00 PM\n"
        "- Remind me to check email in 30 minutes\n"
        "- Remind me to take medicine every day at 9:00 AM\n"
        "- Remind me to pay bills on the 15th of every month\n",
        parse_mode=ParseMode.MARKDOWN
    )

async def list_reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /list_reminders command."""
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        # Get active reminders
        result = await session.execute(
            select(Reminder).where(
                Reminder.user_id == user.id,
                Reminder.is_active == True
            ).order_by(Reminder.scheduled_at)
        )
        reminders = result.scalars().all()
        
        # Determine if this is from a callback query or direct command
        is_callback = update.callback_query is not None
        
        if not reminders:
            message_text = "You don't have any active reminders."
            if is_callback:
                await update.callback_query.message.edit_text(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            return
        
        # Format reminders list
        now = datetime.now(timezone.utc)
        reminder_text = "🔔 *Your Active Reminders:*\n\n"
        
        # Create keyboard buttons for each reminder
        keyboard = []
        
        for i, reminder in enumerate(reminders, 1):
            # Format scheduled time
            if reminder.is_recurring:
                time_str = f"Recurring: {reminder.recurrence_pattern}"
            else:
                # Format relative time
                delta = reminder.scheduled_at - now
                if delta.days < 0:
                    time_str = "Overdue"
                elif delta.days == 0:
                    hours = delta.seconds // 3600
                    minutes = (delta.seconds % 3600) // 60
                    if hours > 0:
                        time_str = f"In {hours}h {minutes}m"
                    else:
                        time_str = f"In {minutes}m"
                elif delta.days == 1:
                    time_str = f"Tomorrow at {reminder.scheduled_at.strftime('%H:%M')}"
                else:
                    time_str = reminder.scheduled_at.strftime("%d %b at %H:%M")
            
            # Add to list
            reminder_text += f"{i}. *{reminder.text}*\n   📅 {time_str}\n\n"
            
            # Add delete button for this reminder
            keyboard.append([InlineKeyboardButton(f"Delete Reminder #{i}", callback_data=f"delete_reminder_{reminder.id}")])
        
        # Add back button to settings
        keyboard.append([InlineKeyboardButton("Back to Settings ⬅️", callback_data="settings")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the message based on update type
        if is_callback:
            await update.callback_query.message.edit_text(
                reminder_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                reminder_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Handle callback queries from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    # Extract the callback data
    data = query.data
    
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        # Handle model selection
        if data.startswith("model_"):
            model = data.replace("model_", "")
            user.preferred_model = model
            await session.commit()
            
            # Get model name
            perplexity_api = context.bot_data.get("perplexity_api")
            models = await perplexity_api.get_available_models()
            model_info = next((m for m in models if m["id"] == model), None)
            model_name = model_info["name"] if model_info else model
            
            await query.edit_message_text(
                f"✅ Model changed to *{model_name}*\n\n{model_info['description'] if model_info else ''}",
                parse_mode=ParseMode.MARKDOWN
            )
            return None
            
        # Handle thinking mode toggle
        elif data == "thinking_toggle":
            user.thinking_mode = not user.thinking_mode
            await session.commit()
            
            await query.edit_message_text(
                f"🧠 *Thinking Mode Settings*\n\n{'When using reasoning models, I will show my step-by-step thought process before giving you the final answer.' if user.thinking_mode else 'I will provide direct answers without showing my thought process.'}",
                reply_markup=create_thinking_mode_keyboard(user.thinking_mode),
                parse_mode=ParseMode.MARKDOWN
            )
            return None
            
        # Handle settings menu
        elif data == "settings":
            await query.edit_message_text(
                "⚙️ *Settings*\n\nWhat would you like to configure?",
                reply_markup=create_settings_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return None
            
        # Handle change model from settings
        elif data == "change_model":
            await query.edit_message_text(
                "🤖 *Select Model*\n\nChoose which Perplexity model to use:",
                reply_markup=create_model_selection_keyboard(),
                parse_mode=ParseMode.MARKDOWN
            )
            return None
            
        # Handle thinking settings from settings
        elif data == "thinking_settings":
            await query.edit_message_text(
                f"🧠 *Thinking Mode Settings*\n\n{'When using reasoning models, I will show my step-by-step thought process before giving you the final answer.' if user.thinking_mode else 'I will provide direct answers without showing my thought process.'}",
                reply_markup=create_thinking_mode_keyboard(user.thinking_mode),
                parse_mode=ParseMode.MARKDOWN
            )
            return None
            
        # Handle manage reminders from settings
        elif data == "manage_reminders":
            # Trigger the list_reminders_command
            await query.edit_message_text(
                "Loading your reminders..."
            )
            
            # Simulate the /list_reminders command
            await list_reminders_command(update, context)
            return None
            
        # Handle delete reminder
        elif data.startswith("delete_reminder_"):
            try:
                # Extract reminder ID
                reminder_id = int(data.replace("delete_reminder_", ""))
                
                # Get reminder scheduler
                scheduler = context.bot_data.get("reminder_scheduler")
                if not scheduler:
                    await query.edit_message_text(
                        "❌ Error: Reminder scheduler not found. Please restart the bot."
                    )
                    return None
                
                # Delete the reminder
                success = await scheduler.delete_reminder(reminder_id)
                
                if success:
                    await query.edit_message_text(
                        "✅ Reminder deleted successfully."
                    )
                    # Wait a moment then reload the reminders list
                    await asyncio.sleep(1)
                    await query.edit_message_text("Refreshing reminder list...")
                    await list_reminders_command(update, context)
                else:
                    await query.edit_message_text(
                        "❌ Reminder not found or already deleted."
                    )
            except ValueError:
                await query.edit_message_text(
                    "❌ Invalid reminder ID format."
                )
            return None
            
        # Handle clear history from settings
        elif data == "clear_history":
            # Clear conversation history
            user.conversation_history = "[]"
            await session.commit()
            
            # Delete chat messages from database
            await session.execute(
                delete(ChatMessage).where(ChatMessage.user_id == user.id)
            )
            await session.commit()
            
            await query.edit_message_text(
                "🗑️ Your conversation history has been cleared.",
                parse_mode=ParseMode.MARKDOWN
            )
            return None
            
        # Handle reminder confirmation
        elif data == "reminder_confirm":
            # Get stored reminder data
            reminder_data = context.user_data.get("pending_reminder")
            if not reminder_data:
                await query.edit_message_text(
                    "❌ Error: Reminder data not found. Please try setting a new reminder."
                )
                return ConversationHandler.END
            
            # Extract data
            text = reminder_data.get("text")
            scheduled_at = reminder_data.get("scheduled_at")
            is_recurring = reminder_data.get("is_recurring", False)
            recurrence_pattern = reminder_data.get("recurrence_pattern")
            
            # Create reminder
            scheduler = context.bot_data.get("reminder_scheduler")
            if not scheduler:
                logger.error("Reminder scheduler not found in bot_data")
                await query.edit_message_text(
                    "❌ Error: Reminder scheduler not found. Please restart the bot."
                )
                return ConversationHandler.END
                
            reminder = await scheduler.create_reminder(
                user_id=user.id,
                telegram_id=user.telegram_id,
                text=text,
                scheduled_at=scheduled_at,
                is_recurring=is_recurring,
                recurrence_pattern=recurrence_pattern
            )
            
            # Confirmation message
            if is_recurring:
                await query.edit_message_text(
                    f"✅ Recurring reminder set: *{text}*\n\n"
                    f"📅 Pattern: {recurrence_pattern}\n"
                    f"⏰ First occurrence: {scheduled_at.strftime('%d %b %Y at %H:%M')}",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    f"✅ Reminder set: *{text}*\n\n"
                    f"⏰ Scheduled for: {scheduled_at.strftime('%d %b %Y at %H:%M')}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Clean up
            context.user_data.pop("pending_reminder", None)
            return ConversationHandler.END
            
        # Handle reminder cancellation
        elif data == "reminder_cancel":
            # Clean up
            context.user_data.pop("pending_reminder", None)
            
            await query.edit_message_text(
                "❌ Reminder cancelled."
            )
            return ConversationHandler.END
            
        # Handle frequency selection
        elif data.startswith("freq_"):
            frequency = data.replace("freq_", "")
            
            if frequency == "cancel":
                await query.edit_message_text(
                    "❌ Subscription cancelled."
                )
                return ConversationHandler.END
            
            # Get the stored topic
            topic = context.user_data.get("pending_topic")
            if not topic:
                await query.edit_message_text(
                    "❌ Topic not found. Please try subscribing again."
                )
                return ConversationHandler.END
            
            # Get news service
            news_service = context.bot_data.get("news_service")
            if not news_service:
                perplexity_api = context.bot_data.get("perplexity_api")
                news_service = NewsService(perplexity_api)
            
            # Subscribe to topic
            subscription = await news_service.subscribe_to_topic(
                session=session,
                user_id=user.id,
                topic=topic,
                frequency=frequency
            )
            
            # Confirmation message
            frequency_text = {
                "hourly": "every hour",
                "daily": "once a day",
                "weekly": "once a week"
            }.get(frequency, frequency)
            
            await query.edit_message_text(
                f"✅ You are now subscribed to news updates about *{topic}*.\n\n"
                f"You will receive updates {frequency_text}.",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Clean up
            context.user_data.pop("pending_topic", None)
            
            return ConversationHandler.END
            
        # Handle unsubscribe
        elif data.startswith("unsub_"):
            try:
                # Extract subscription ID
                sub_id = int(data.replace("unsub_", ""))
                
                # Get news service
                news_service = context.bot_data.get("news_service")
                if not news_service:
                    perplexity_api = context.bot_data.get("perplexity_api")
                    news_service = NewsService(perplexity_api)
                
                # Unsubscribe
                success = await news_service.unsubscribe_from_topic(
                    session=session,
                    user_id=user.id,
                    topic_id=sub_id
                )
                
                if success:
                    await query.edit_message_text(
                        "✅ You have unsubscribed from this topic."
                    )
                    # Wait a moment then reload the subscriptions list
                    await asyncio.sleep(1)
                    await query.edit_message_text("Refreshing subscriptions...")
                    
                    # Simulate the command
                    await list_subscriptions_command(update, context)
                else:
                    await query.edit_message_text(
                        "❌ Subscription not found or already deleted."
                    )
            except ValueError:
                await query.edit_message_text(
                    "❌ Invalid subscription ID format."
                )
            return None
            
        # Handle manage subscriptions from settings
        elif data == "manage_subscriptions":
            # Trigger the list_subscriptions_command
            await query.edit_message_text(
                "Loading your subscriptions..."
            )
            
            # Simulate the command
            await list_subscriptions_command(update, context)
            return None
    
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Handle user messages."""
    # Get the user message
    message = update.message
    if not message or not message.text:
        return None
    
    text = message.text.strip()
    
    # Check for special command patterns
    if text.startswith("/delete_reminder_"):
        # Extract reminder ID
        try:
            reminder_id = int(text.replace("/delete_reminder_", ""))
            return await handle_delete_reminder(update, context, reminder_id)
        except (ValueError, IndexError):
            await message.reply_text("Invalid reminder ID format.")
            return None
    
    # Check if it's a reminder request
    if is_reminder_request(text):
        return await handle_reminder_request(update, context, text)
    
    # Check if it's an image generation request
    if is_image_request(text):
        return await handle_image_generation(update, context, text)
    
    # Process as a regular question
    return await handle_regular_message(update, context, text)

async def handle_delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE, reminder_id: int) -> None:
    """Handle deleting a reminder."""
    scheduler = context.bot_data.get("reminder_scheduler")
    
    # Delete the reminder
    success = await scheduler.delete_reminder(reminder_id)
    
    if success:
        await update.message.reply_text(
            "✅ Reminder deleted successfully.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "❌ Reminder not found or already deleted.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return None

async def handle_reminder_request(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> int:
    """Handle a request to set a reminder."""
    from bot.utils import parse_reminder_time, parse_recurrence_pattern, extract_reminder_text
    
    # Extract reminder text
    reminder_text = extract_reminder_text(text)
    
    # Try to parse as recurring reminder first
    recurrence_pattern, first_occurrence, recurrence_error = parse_recurrence_pattern(text)
    
    if recurrence_pattern and first_occurrence:
        # It's a recurring reminder
        keyboard = [
            [
                InlineKeyboardButton("Confirm ✅", callback_data="reminder_confirm"),
                InlineKeyboardButton("Cancel ❌", callback_data="reminder_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store reminder data
        context.user_data["pending_reminder"] = {
            "text": reminder_text,
            "scheduled_at": first_occurrence,
            "is_recurring": True,
            "recurrence_pattern": recurrence_pattern
        }
        
        await update.message.reply_text(
            f"🔔 *Recurring Reminder*\n\n"
            f"*Text:* {reminder_text}\n"
            f"*Pattern:* {recurrence_pattern}\n"
            f"*First occurrence:* {first_occurrence.strftime('%d %b %Y at %H:%M')}\n\n"
            f"Is this correct?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AWAITING_REMINDER_CONFIRMATION
    
    # Try to parse as one-time reminder
    scheduled_time, error = parse_reminder_time(text)
    
    if scheduled_time:
        # It's a one-time reminder
        keyboard = [
            [
                InlineKeyboardButton("Confirm ✅", callback_data="reminder_confirm"),
                InlineKeyboardButton("Cancel ❌", callback_data="reminder_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Store reminder data
        context.user_data["pending_reminder"] = {
            "text": reminder_text,
            "scheduled_at": scheduled_time,
            "is_recurring": False
        }
        
        await update.message.reply_text(
            f"🔔 *New Reminder*\n\n"
            f"*Text:* {reminder_text}\n"
            f"*Time:* {scheduled_time.strftime('%d %b %Y at %H:%M')}\n\n"
            f"Is this correct?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AWAITING_REMINDER_CONFIRMATION
    
    # Couldn't parse the time/pattern
    error_message = error or recurrence_error or "I couldn't understand when to set the reminder."
    
    await update.message.reply_text(
        f"❌ {error_message}\n\n"
        f"Please try again with a clearer time format, like:\n"
        f"- Remind me to call mom tomorrow at 5:00 PM\n"
        f"- Remind me to check email in 30 minutes\n"
        f"- Remind me to take medicine every day at 9:00 AM",
        parse_mode=ParseMode.MARKDOWN
    )
    
    return None

async def handle_image_generation(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle an image generation request."""
    # Get Perplexity API
    perplexity_api = context.bot_data.get("perplexity_api")
    
    # Send typing action
    await update.message.chat.send_action(action="typing")
    
    # Generate image
    response = await perplexity_api.generate_image(text)
    
    if not response.get("success"):
        await update.message.reply_text(
            "🖼️ I'm not able to generate images directly.\n\n"
            "However, you can use dedicated image generation services like DALL-E, Midjourney, or Stable Diffusion to create images based on text prompts.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # This part would handle a successful response if Perplexity had image generation
        pass
    
    return None

async def split_and_send_long_message(update: Update, text: str, parse_mode=None):
    """
    Split a long message into multiple chunks and send them.
    
    Args:
        update: Telegram update
        text: The text to send
        parse_mode: Parse mode for the message
    """
    # Telegram message length limit is 4096 characters
    MAX_MESSAGE_LENGTH = 4000  # Use a bit less than 4096 to be safe
    
    # Split by newlines to keep paragraphs together when possible
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed limit, start a new chunk
        if len(current_chunk) + len(paragraph) + 2 > MAX_MESSAGE_LENGTH:
            if current_chunk:
                chunks.append(current_chunk)
            
            # If the paragraph itself is too long, split it further
            if len(paragraph) > MAX_MESSAGE_LENGTH:
                # Split into smaller pieces (may break mid-sentence)
                words = paragraph.split(' ')
                paragraph_chunk = ""
                
                for word in words:
                    if len(paragraph_chunk) + len(word) + 1 > MAX_MESSAGE_LENGTH:
                        chunks.append(paragraph_chunk)
                        paragraph_chunk = word
                    else:
                        if paragraph_chunk:
                            paragraph_chunk += " " + word
                        else:
                            paragraph_chunk = word
                
                if paragraph_chunk:
                    current_chunk = paragraph_chunk
                else:
                    current_chunk = ""
            else:
                current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    # Delete the loading message
    try:
        await context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=loading_message.message_id
        )
    except Exception as e:
        logger.error(f"Error deleting loading message: {str(e)}")
    
    # Send each chunk as a separate message
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            logger.error(f"Error sending message chunk: {str(e)}")
            try:
                clean_text = ''.join(c for c in chunk if c.isalnum() or c.isspace() or c in ',.?!:;()[]{}')
                await update.message.reply_text(clean_text)
            except Exception as inner_e:
                logger.error(f"Error sending plain message chunk: {str(inner_e)}")

def sanitize_text(text):
    """
    Remove or escape characters that might cause issues with Telegram message formatting.
    
    Args:
        text: The text to sanitize
        
    Returns:
        Sanitized text safe for sending via Telegram
    """
    # Replace problematic characters
    replacements = {
        '<': '&lt;', 
        '>': '&gt;',
        '&': '&amp;',
        '*': '',
        '_': '',
        '`': '',
        '[': '(',
        ']': ')',
        '||': '',
        '|': '',
        '~': '',
        '#': '',
        '+': '',
        '=': '',
        '{': '(',
        '}': ')'
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text

def extract_references(text: str, search_results: List[Dict[str, Any]] = None) -> Tuple[str, str]:
    """
    Extract reference links from text and return cleaned text and references.
    
    Args:
        text: The text to process
        search_results: Optional search results with sources
        
    Returns:
        Tuple of (cleaned_text, reference_links)
    """
    # If no search results, return original text
    if not search_results:
        return text, ""
    
    # Look for references in numbered format like (1)(2)(3)
    reference_pattern = r'\(\d+\)'
    has_references = bool(re.search(reference_pattern, text))
    
    if has_references and search_results:
        # Format the references
        references = "Source links:\n"
        for i, result in enumerate(search_results[:10], 1):  # Limit to top 10 sources
            title = result.get("title", "Source")
            url = result.get("url", "#")
            references += f"{i}. {title}: {url}\n"
        
        return text, references
    
    # No references found or no search results
    return text, ""

async def handle_regular_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """Handle a regular message (question/query)."""
    await update.message.chat.send_action(action="typing")
    
    loading_message = await update.message.reply_text("🧠 Processing your request... This might take a moment.")
    
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        await save_message(
            session,
            user,
            "user",
            text,
            message_id=update.message.message_id
        )
        
        model = user.preferred_model
        thinking_mode = user.thinking_mode
        
        conversation_history = get_conversation_history(user)
        
        perplexity_api = context.bot_data.get("perplexity_api")
        
        typing_task = asyncio.create_task(keep_typing_indicator(update))
        
        try:
            response = await perplexity_api.ask_question(
                query=text,
                model=model,
                conversation_history=conversation_history,
                show_thinking=thinking_mode
            )
            
            typing_task.cancel()
            
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=loading_message.message_id
                )
            except Exception as e:
                logger.error(f"Error deleting loading message: {str(e)}")
            
            if response.get("success"):
                update_conversation_history(user, "user", text)
                
                if thinking_mode and "thinking" in response:
                    thinking_text = sanitize_text(response['thinking'])
                    
                    await update.message.reply_text("🧠 Thinking Process:", reply_to_message_id=update.message.message_id)
                    
                    if len(thinking_text) > 4000:
                        chunks = [thinking_text[i:i+4000] for i in range(0, len(thinking_text), 4000)]
                        for chunk in chunks:
                            await update.message.reply_text(chunk)
                    else:
                        await update.message.reply_text(thinking_text)
                    
                    answer = sanitize_text(response["answer"])
                    
                    cleaned_answer, references = extract_references(answer, response.get("search_results"))
                    
                    await update.message.reply_text("📝 Answer:")
                    await split_and_send_long_message(update, cleaned_answer)
                    
                    if references:
                        await update.message.reply_text(f"📚 *Sources*:\n{references}")
                    
                    await save_message(
                        session,
                        user,
                        "assistant",
                        f"[Thinking]: {response['thinking']}\n\n[Answer]: {answer}",
                        model_used=model,
                        include_thinking=True
                    )
                    
                    update_conversation_history(user, "assistant", answer)
                else:
                    answer = sanitize_text(response["answer"])
                    
                    cleaned_answer, references = extract_references(answer, response.get("search_results"))
                    
                    await split_and_send_long_message(update, cleaned_answer)
                    
                    if references:
                        await update.message.reply_text(f"📚 *Sources*:\n{references}")
                    
                    await save_message(
                        session,
                        user,
                        "assistant",
                        answer,
                        model_used=model
                    )
                    
                    update_conversation_history(user, "assistant", answer)
            else:
                # Handle error
                error_message = response.get("error", "An error occurred while processing your request.")
                await update.message.reply_text(
                    f"❌ {sanitize_text(error_message)}"
                )
                
                # Save error message
                await save_message(
                    session,
                    user,
                    "assistant",
                    f"[Error]: {error_message}",
                    model_used=model
                )
        except Exception as e:
            # Cancel the typing indicator
            typing_task.cancel()
            
            # Delete the loading message
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=loading_message.message_id
                )
            except Exception as delete_error:
                logger.error(f"Error deleting loading message: {str(delete_error)}")
            
            # Log and send error message
            logger.error(f"Error processing message: {str(e)}")
            await update.message.reply_text(
                f"❌ An error occurred while processing your request: {sanitize_text(str(e))}"
            )
        
        # Save updated conversation history
        await session.commit()
    
    return None

async def keep_typing_indicator(update: Update):
    """Keep the typing indicator active with periodic updates."""
    try:
        while True:
            await update.message.chat.send_action(action="typing")
            await asyncio.sleep(4)  # Telegram's typing indicator lasts about 5 seconds
    except asyncio.CancelledError:
        # Task was cancelled - that's expected
        pass
    except Exception as e:
        logger.error(f"Error in typing indicator: {str(e)}")

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages with photos."""
    await update.message.chat.send_action(action="typing")
    
    loading_message = await update.message.reply_text("🧠 Processing your image... This might take a moment.")
    
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        model = user.preferred_model
        thinking_mode = user.thinking_mode
        
        conversation_history = get_conversation_history(user)
        
        photo = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)
        photo_bytes = await photo_file.download_as_bytearray()
        
        caption = update.message.caption or "What's in this image?"
        
        await save_message(
            session,
            user,
            "user",
            f"[Image] {caption}",
            message_id=update.message.message_id,
            has_image=True
        )
        
        perplexity_api = context.bot_data.get("perplexity_api")
        
        typing_task = asyncio.create_task(keep_typing_indicator(update))
        
        try:
            response = await perplexity_api.ask_question(
                query=caption,
                model=model,
                conversation_history=conversation_history,
                show_thinking=thinking_mode,
                image_data=photo_bytes
            )
            
            typing_task.cancel()
            
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=loading_message.message_id
                )
            except Exception as e:
                logger.error(f"Error deleting loading message: {str(e)}")
            
            if response.get("success"):
                update_conversation_history(user, "user", caption)
                
                if thinking_mode and "thinking" in response:
                    thinking_text = sanitize_text(response['thinking'])
                    
                    await update.message.reply_text("🧠 Thinking Process:", reply_to_message_id=update.message.message_id)
                    
                    if len(thinking_text) > 4000:
                        chunks = [thinking_text[i:i+4000] for i in range(0, len(thinking_text), 4000)]
                        for chunk in chunks:
                            await update.message.reply_text(chunk)
                    else:
                        await update.message.reply_text(thinking_text)
                    
                    answer = sanitize_text(response["answer"])
                    
                    cleaned_answer, references = extract_references(answer, response.get("search_results"))
                    
                    await update.message.reply_text("📝 Answer:")
                    await split_and_send_long_message(update, cleaned_answer)
                    
                    if references:
                        await update.message.reply_text(f"📚 *Sources*:\n{references}")
                    
                    await save_message(
                        session,
                        user,
                        "assistant",
                        f"[Thinking]: {response['thinking']}\n\n[Answer]: {answer}",
                        model_used=model,
                        include_thinking=True
                    )
                    
                    update_conversation_history(user, "assistant", answer)
                else:
                    answer = sanitize_text(response["answer"])
                    
                    cleaned_answer, references = extract_references(answer, response.get("search_results"))
                    
                    await split_and_send_long_message(update, cleaned_answer)
                    
                    if references:
                        await update.message.reply_text(f"📚 *Sources*:\n{references}")
                    
                    await save_message(
                        session,
                        user,
                        "assistant",
                        answer,
                        model_used=model
                    )
                    
                    update_conversation_history(user, "assistant", answer)
            else:
                # Handle error
                error_message = response.get("error", "An error occurred while processing your request.")
                await update.message.reply_text(
                    f"❌ {sanitize_text(error_message)}"
                )
                
                # Save error message
                await save_message(
                    session,
                    user,
                    "assistant",
                    f"[Error]: {error_message}",
                    model_used=model
                )
        except Exception as e:
            # Cancel the typing indicator
            typing_task.cancel()
            
            # Delete the loading message
            try:
                await context.bot.delete_message(
                    chat_id=update.message.chat_id,
                    message_id=loading_message.message_id
                )
            except Exception as delete_error:
                logger.error(f"Error deleting loading message: {str(delete_error)}")
            
            # Log and send error message
            logger.error(f"Error processing photo message: {str(e)}")
            await update.message.reply_text(
                f"❌ An error occurred while processing your image: {sanitize_text(str(e))}"
            )
        
        # Save updated conversation history
        await session.commit()

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /subscribe command to subscribe to news topics."""
    # Check if a topic was provided in the command
    if context.args and len(context.args) > 0:
        # Join all args to form the topic
        topic = " ".join(context.args)
        
        # Store the topic in user data
        context.user_data["pending_topic"] = topic
        
        # Ask for frequency directly
        await update.message.reply_text(
            f"📊 How often would you like to receive updates about *{topic}*?",
            reply_markup=create_frequency_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AWAITING_TOPIC_FREQUENCY
    else:
        # No topic provided, show usage instructions
        await update.message.reply_text(
            "📰 *Subscribe to News Updates*\n\n"
            "Please use the format: `/subscribe TOPIC`\n\n"
            "Examples:\n"
            "- `/subscribe AI`\n"
            "- `/subscribe climate change`\n"
            "- `/subscribe space exploration`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END

async def handle_news_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the topic for news subscription."""
    topic = update.message.text.strip()
    
    # Store the topic in user data
    context.user_data["pending_topic"] = topic
    
    await update.message.reply_text(
        f"📊 How often would you like to receive updates about *{topic}*?",
        reply_markup=create_frequency_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return AWAITING_TOPIC_FREQUENCY

async def list_subscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /mysubs command to list user's news subscriptions."""
    async with async_session() as session:
        user = await get_or_create_user(session, update)
        
        # Get news service
        news_service = context.bot_data.get("news_service")
        if not news_service:
            perplexity_api = context.bot_data.get("perplexity_api")
            news_service = NewsService(perplexity_api)
        
        # Get subscriptions
        subscriptions = await news_service.get_user_subscriptions(session, user.id)
        
        # Determine if this is from a callback query or direct command
        is_callback = update.callback_query is not None
        
        if not subscriptions:
            message_text = "You don't have any active news subscriptions."
            if is_callback:
                await update.callback_query.message.edit_text(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    message_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            return
        
        # Format subscriptions list
        subs_text = "📰 *Your News Subscriptions:*\n\n"
        
        for i, sub in enumerate(subscriptions, 1):
            subs_text += f"{i}. *{sub.topic}*\n   📊 Frequency: {sub.frequency}\n\n"
        
        subs_text += "Click on a subscription to unsubscribe."
        
        # Create keyboard
        reply_markup = create_subscription_keyboard(subscriptions)
        
        # Send the message based on update type
        if is_callback:
            await update.callback_query.message.edit_text(
                subs_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                subs_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )

def setup_handlers(bot_app: Application, perplexity_api: PerplexityAPI) -> None:
    """Set up all handlers for the bot."""
    bot_app.bot_data["perplexity_api"] = perplexity_api
    
    # Initialize news service
    news_service = NewsService(perplexity_api)
    bot_app.bot_data["news_service"] = news_service
    
    bot_app.add_handler(CommandHandler("start", start_command))
    bot_app.add_handler(CommandHandler("help", help_command))
    bot_app.add_handler(CommandHandler("settings", settings_command))
    bot_app.add_handler(CommandHandler("model", model_command))
    bot_app.add_handler(CommandHandler("thinking", thinking_command))
    bot_app.add_handler(CommandHandler("clear", clear_command))
    bot_app.add_handler(CommandHandler("reminder", reminder_command))
    bot_app.add_handler(CommandHandler("list_reminders", list_reminders_command))
    bot_app.add_handler(CommandHandler("subscribe", subscribe_command))
    bot_app.add_handler(CommandHandler("mysubs", list_subscriptions_command))
    
    bot_app.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # Add conversation handler for reminders
    reminder_handler = ConversationHandler(
        entry_points=[],
        states={
            AWAITING_REMINDER_CONFIRMATION: [
                CallbackQueryHandler(callback_query_handler, pattern=r"^reminder_")
            ],
        },
        fallbacks=[]
    )
    bot_app.add_handler(reminder_handler)
    
    # Add conversation handler for news subscriptions
    news_subscription_handler = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe_command)],
        states={
            AWAITING_TOPIC_FREQUENCY: [
                CallbackQueryHandler(callback_query_handler, pattern=r"^freq_")
            ],
        },
        fallbacks=[],
        name="news_subscription_conversation"
    )
    bot_app.add_handler(news_subscription_handler)
    
    # Add other message handlers last
    bot_app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    asyncio.create_task(bot_app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("settings", "Open settings menu"),
        BotCommand("model", "Change AI model"),
        BotCommand("thinking", "Toggle thinking mode"),
        BotCommand("reminder", "Set a new reminder"),
        BotCommand("list_reminders", "List active reminders"),
        BotCommand("subscribe", "Subscribe to news updates"),
        BotCommand("mysubs", "List news subscriptions"),
        BotCommand("clear", "Clear conversation history"),
        BotCommand("help", "Show help message")
    ]))
    
    logger.info("Bot handlers set up successfully") 