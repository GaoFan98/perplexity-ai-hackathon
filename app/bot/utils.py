import logging
import json
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from models.user import User
from models.chat import ChatMessage
from api.perplexity import PerplexityAPI

logger = logging.getLogger(__name__)

# Regular expressions for parsing date/time strings
DATETIME_FORMATS = [
    # Date and time with 12h clock
    r'(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2}) at (\d{1,2}):(\d{2}) ([APap][Mm])',
    r'(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2}) (\d{1,2}):(\d{2}) ([APap][Mm])',
    
    # Date and time with 24h clock
    r'(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2}) at (\d{1,2}):(\d{2})',
    r'(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2}) (\d{1,2}):(\d{2})',
    
    # Just time with 12h clock
    r'at (\d{1,2}):(\d{2}) ([APap][Mm])',
    r'(\d{1,2}):(\d{2}) ([APap][Mm])',
    
    # Just time with 24h clock
    r'at (\d{1,2}):(\d{2})',
    r'(\d{1,2}):(\d{2})',
    
    # Relative time
    r'in (\d+) minutes?',
    r'in (\d+) hours?',
    r'in (\d+) days?',
    r'in (\d+) weeks?',
    
    # Natural language
    r'tomorrow',
    r'today',
    r'next week',
    r'next month',
]

# Regular expressions for parsing cron patterns
RECURRENCE_FORMATS = [
    # Daily at specific time
    r'every day at (\d{1,2}):(\d{2}) ?([APap][Mm])?',
    
    # Weekly on specific day
    r'every (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at (\d{1,2}):(\d{2}) ?([APap][Mm])?',
    
    # Monthly on specific day
    r'every (\d{1,2})(st|nd|rd|th)? of (each|every) month at (\d{1,2}):(\d{2}) ?([APap][Mm])?',
]

# Day of week mapping
DOW_MAP = {
    'monday': 1,
    'tuesday': 2,
    'wednesday': 3,
    'thursday': 4,
    'friday': 5,
    'saturday': 6,
    'sunday': 0,
}

async def get_or_create_user(session: AsyncSession, update: Update) -> User:
    """
    Get or create a user from a Telegram update.
    
    Args:
        session: Database session
        update: Telegram update object
        
    Returns:
        User object
    """
    # Get user info from telegram update
    tg_user = update.effective_user
    if not tg_user:
        raise ValueError("No user in update")
    
    # Look for existing user
    result = await session.execute(
        select(User).where(User.telegram_id == tg_user.id)
    )
    user = result.scalars().first()
    
    # Create new user if not found
    if not user:
        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Created new user: {user}")
    
    return user

async def save_message(
    session: AsyncSession, 
    user: User, 
    role: str, 
    content: str, 
    message_id: int = None,
    model_used: str = None,
    include_thinking: bool = False
) -> ChatMessage:
    """
    Save a message to the database.
    
    Args:
        session: Database session
        user: User object
        role: Message role ('user' or 'assistant')
        content: Message content
        message_id: Telegram message ID
        model_used: Which model was used (for assistant messages)
        include_thinking: Whether this message includes thinking
        
    Returns:
        ChatMessage object
    """
    message = ChatMessage(
        user_id=user.id,
        message_id=message_id,
        role=role,
        content=content,
        model_used=model_used,
        include_thinking=include_thinking
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    
    return message

def get_conversation_history(user: User, limit: int = 10) -> List[Dict[str, str]]:
    """
    Get conversation history for a user, ensuring it follows Perplexity API requirements:
    1. Optional system message(s) first
    2. Strictly alternating user/assistant messages
    
    Args:
        user: User object
        limit: Maximum number of messages to include
        
    Returns:
        List of message dictionaries for the API
    """
    try:
        # Parse conversation history from user.conversation_history JSON string
        if not user.conversation_history or user.conversation_history == "[]":
            # Start with a fresh history and add a system message
            return [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant powered by Perplexity's Sonar API."
                }
            ]
        
        # Parse the existing history
        history = json.loads(user.conversation_history)
        
        # Ensure it's a list
        if not isinstance(history, list):
            return [
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant powered by Perplexity's Sonar API."
                }
            ]
        
        # Start with a system message
        formatted_history = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant powered by Perplexity's Sonar API."
            }
        ]
        
        # Get last messages up to the limit
        history = history[-limit:]
        
        # Format the conversation history to ensure alternating roles
        user_messages = [msg for msg in history if msg.get("role") == "user"]
        assistant_messages = [msg for msg in history if msg.get("role") == "assistant"]
        
        # Pair user and assistant messages
        paired_messages = []
        for i in range(min(len(user_messages), len(assistant_messages))):
            paired_messages.append(user_messages[i])
            paired_messages.append(assistant_messages[i])
        
        # Add the last user message if there's one more user message than assistant messages
        if len(user_messages) > len(assistant_messages):
            paired_messages.append(user_messages[-1])
        
        # Add paired messages to formatted history
        formatted_history.extend(paired_messages)
        
        return formatted_history
        
    except Exception as e:
        logger.error(f"Error parsing conversation history: {str(e)}")
        # Return just a system message in case of error
        return [
            {
                "role": "system",
                "content": "You are a helpful AI assistant powered by Perplexity's Sonar API."
            }
        ]

def update_conversation_history(user: User, role: str, content: str) -> None:
    """
    Update conversation history for a user, ensuring proper role alternation.
    
    Args:
        user: User object
        role: Message role ('user' or 'assistant')
        content: Message content
    """
    try:
        # Parse current history
        if not user.conversation_history or user.conversation_history == "[]":
            history = []
        else:
            history = json.loads(user.conversation_history)
        
        # Ensure it's a list
        if not isinstance(history, list):
            history = []
        
        # Get last role if history exists
        last_role = history[-1]["role"] if history else None
        
        # Validate role alternation
        if last_role == role:
            # Replace the last message with same role instead of adding a new one
            history[-1]["content"] = content
        else:
            # Add new message
            history.append({
                "role": role,
                "content": content
            })
        
        # Keep only the last 20 messages
        if len(history) > 20:
            history = history[-20:]
        
        # Update user object
        user.conversation_history = json.dumps(history)
        
    except Exception as e:
        logger.error(f"Error updating conversation history: {str(e)}")
        user.conversation_history = "[]"

def create_model_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard markup for model selection.
    
    Returns:
        InlineKeyboardMarkup with model options
    """
    keyboard = [
        [
            InlineKeyboardButton("Sonar Pro 🔍", callback_data="model_sonar-pro"),
            InlineKeyboardButton("Sonar 🔎", callback_data="model_sonar")
        ],
        [
            InlineKeyboardButton("Sonar Reasoning Pro 🧠", callback_data="model_sonar-reasoning-pro"),
            InlineKeyboardButton("Sonar Reasoning 🤔", callback_data="model_sonar-reasoning")
        ],
        [
            InlineKeyboardButton("Deep Research 📚", callback_data="model_sonar-deep-research"),
            InlineKeyboardButton("R1-1776 🔒", callback_data="model_r1-1776")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def create_thinking_mode_keyboard(current_mode: bool) -> InlineKeyboardMarkup:
    """
    Create keyboard markup for thinking mode selection.
    
    Args:
        current_mode: Current thinking mode status
        
    Returns:
        InlineKeyboardMarkup with thinking mode options
    """
    mode_text = "ON ✅" if current_mode else "OFF ❌"
    
    keyboard = [
        [
            InlineKeyboardButton(f"Thinking Mode: {mode_text}", callback_data="thinking_toggle")
        ],
        [
            InlineKeyboardButton("Back to Settings ⬅️", callback_data="settings")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def create_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Create keyboard markup for settings menu.
    
    Returns:
        InlineKeyboardMarkup with settings options
    """
    keyboard = [
        [
            InlineKeyboardButton("Change Model 🔄", callback_data="change_model")
        ],
        [
            InlineKeyboardButton("Thinking Mode ⚙️", callback_data="thinking_settings")
        ],
        [
            InlineKeyboardButton("Manage Reminders 🔔", callback_data="manage_reminders")
        ],
        [
            InlineKeyboardButton("Clear Chat History 🗑️", callback_data="clear_history")
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)

def parse_reminder_time(text: str) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Parse a reminder time from text.
    
    Args:
        text: Text to parse
        
    Returns:
        Tuple of (scheduled_time, error_message)
    """
    # Current time as base
    now = datetime.now(timezone.utc)
    
    # Try each format
    for pattern in DATETIME_FORMATS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            # Date and time with 12h clock
            if pattern == DATETIME_FORMATS[0] or pattern == DATETIME_FORMATS[1]:
                day, month, year, hour, minute, ampm = groups
                year = int("20" + year if len(year) == 2 else year)
                hour = int(hour)
                if hour == 12 and ampm.lower().startswith('a'):
                    hour = 0
                elif hour < 12 and ampm.lower().startswith('p'):
                    hour += 12
                
                try:
                    return datetime(int(year), int(month), int(day), hour, int(minute), tzinfo=timezone.utc), None
                except ValueError:
                    return None, "Invalid date or time format. Please use DD/MM/YYYY at HH:MM AM/PM format."
            
            # Date and time with 24h clock
            elif pattern == DATETIME_FORMATS[2] or pattern == DATETIME_FORMATS[3]:
                day, month, year, hour, minute = groups
                year = int("20" + year if len(year) == 2 else year)
                
                try:
                    return datetime(int(year), int(month), int(day), int(hour), int(minute), tzinfo=timezone.utc), None
                except ValueError:
                    return None, "Invalid date or time format. Please use DD/MM/YYYY at HH:MM format."
            
            # Just time with 12h clock
            elif pattern == DATETIME_FORMATS[4] or pattern == DATETIME_FORMATS[5]:
                if pattern == DATETIME_FORMATS[4]:
                    hour, minute, ampm = groups
                else:
                    hour, minute, ampm = groups
                
                hour = int(hour)
                if hour == 12 and ampm.lower().startswith('a'):
                    hour = 0
                elif hour < 12 and ampm.lower().startswith('p'):
                    hour += 12
                
                time_today = now.replace(hour=hour, minute=int(minute), second=0, microsecond=0)
                
                # If the time is in the past, schedule for tomorrow
                if time_today < now:
                    time_today += timedelta(days=1)
                
                return time_today, None
            
            # Just time with 24h clock
            elif pattern == DATETIME_FORMATS[6] or pattern == DATETIME_FORMATS[7]:
                if pattern == DATETIME_FORMATS[6]:
                    hour, minute = groups
                else:
                    hour, minute = groups
                
                time_today = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
                
                # If the time is in the past, schedule for tomorrow
                if time_today < now:
                    time_today += timedelta(days=1)
                
                return time_today, None
            
            # Relative time: minutes
            elif pattern == DATETIME_FORMATS[8]:
                minutes = int(groups[0])
                return now + timedelta(minutes=minutes), None
            
            # Relative time: hours
            elif pattern == DATETIME_FORMATS[9]:
                hours = int(groups[0])
                return now + timedelta(hours=hours), None
            
            # Relative time: days
            elif pattern == DATETIME_FORMATS[10]:
                days = int(groups[0])
                return now + timedelta(days=days), None
            
            # Relative time: weeks
            elif pattern == DATETIME_FORMATS[11]:
                weeks = int(groups[0])
                return now + timedelta(weeks=weeks), None
            
            # Natural language: tomorrow
            elif pattern == DATETIME_FORMATS[12]:
                # Set time to 9:00 AM tomorrow
                tomorrow = now + timedelta(days=1)
                return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0), None
            
            # Natural language: today
            elif pattern == DATETIME_FORMATS[13]:
                # Set time to 1 hour from now
                return now + timedelta(hours=1), None
            
            # Natural language: next week
            elif pattern == DATETIME_FORMATS[14]:
                # Set time to 9:00 AM next Monday
                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0:
                    days_until_monday = 7
                next_monday = now + timedelta(days=days_until_monday)
                return next_monday.replace(hour=9, minute=0, second=0, microsecond=0), None
            
            # Natural language: next month
            elif pattern == DATETIME_FORMATS[15]:
                # Set time to 9:00 AM on the 1st of next month
                if now.month == 12:
                    next_month = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    next_month = now.replace(month=now.month + 1, day=1)
                return next_month.replace(hour=9, minute=0, second=0, microsecond=0), None
    
    # No match found
    return None, "I couldn't understand the time format. Please use a specific date/time (e.g., 'DD/MM/YYYY at HH:MM') or a relative time (e.g., 'in 30 minutes')."

def parse_recurrence_pattern(text: str) -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
    """
    Parse a recurrence pattern from text.
    
    Args:
        text: Text to parse
        
    Returns:
        Tuple of (cron_expression, first_occurrence, error_message)
    """
    # Current time as base
    now = datetime.now(timezone.utc)
    
    # Try each format
    for pattern in RECURRENCE_FORMATS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            # Daily at specific time
            if pattern == RECURRENCE_FORMATS[0]:
                hour, minute, ampm = groups
                hour = int(hour)
                minute = int(minute)
                
                if ampm:
                    if hour == 12 and ampm.lower().startswith('a'):
                        hour = 0
                    elif hour < 12 and ampm.lower().startswith('p'):
                        hour += 12
                
                # Create cron expression: minute hour * * *
                cron = f"{minute} {hour} * * *"
                
                # Calculate first occurrence
                first_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if first_time < now:
                    first_time += timedelta(days=1)
                
                return cron, first_time, None
            
            # Weekly on specific day
            elif pattern == RECURRENCE_FORMATS[1]:
                day_of_week, hour, minute, ampm = groups
                hour = int(hour)
                minute = int(minute)
                
                if ampm:
                    if hour == 12 and ampm.lower().startswith('a'):
                        hour = 0
                    elif hour < 12 and ampm.lower().startswith('p'):
                        hour += 12
                
                # Get day of week number (0=Sunday, 6=Saturday)
                dow = DOW_MAP[day_of_week.lower()]
                
                # Create cron expression: minute hour * * day
                cron = f"{minute} {hour} * * {dow}"
                
                # Calculate days until next occurrence
                days_until = (dow - now.weekday()) % 7
                if days_until == 0 and (now.hour > hour or (now.hour == hour and now.minute >= minute)):
                    days_until = 7
                
                first_time = now + timedelta(days=days_until)
                first_time = first_time.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                return cron, first_time, None
            
            # Monthly on specific day
            elif pattern == RECURRENCE_FORMATS[2]:
                day, _, _, hour, minute, ampm = groups
                day = int(day)
                hour = int(hour)
                minute = int(minute)
                
                if ampm:
                    if hour == 12 and ampm.lower().startswith('a'):
                        hour = 0
                    elif hour < 12 and ampm.lower().startswith('p'):
                        hour += 12
                
                # Create cron expression: minute hour day-of-month * *
                cron = f"{minute} {hour} {day} * *"
                
                # Calculate first occurrence
                first_time = now.replace(day=min(day, 28), hour=hour, minute=minute, second=0, microsecond=0)
                if first_time < now:
                    # Move to next month
                    if now.month == 12:
                        first_time = first_time.replace(year=now.year+1, month=1)
                    else:
                        first_time = first_time.replace(month=now.month+1)
                
                return cron, first_time, None
    
    # No match found
    return None, None, "I couldn't understand the recurrence pattern. Please use a format like 'every day at HH:MM', 'every Monday at HH:MM', or 'every 15th of each month at HH:MM'."

def is_image_request(text: str) -> bool:
    """
    Check if the text is requesting image generation.
    
    Args:
        text: Text to check
        
    Returns:
        True if it's an image generation request, False otherwise
    """
    # Look for common image generation phrases
    patterns = [
        r'(?i)generate (?:an?|some) images?',
        r'(?i)create (?:an?|some) images?',
        r'(?i)make (?:an?|some) images?',
        r'(?i)draw (?:an?|some)',
        r'(?i)show me (?:an?|some) images? of',
        r'(?i)can you (?:generate|create|make|draw) (?:an?|some) images?',
        r'(?i)^images? of',
        r'(?i)^generate ',
        r'(?i)^draw ',
    ]
    
    return any(re.search(pattern, text) for pattern in patterns)

def is_reminder_request(text: str) -> bool:
    """
    Check if the text is requesting to set a reminder.
    
    Args:
        text: Text to check
        
    Returns:
        True if it's a reminder request, False otherwise
    """
    # Look for common reminder phrases
    patterns = [
        r'(?i)remind me',
        r'(?i)set (?:a|an) reminder',
        r'(?i)create (?:a|an) reminder',
        r'(?i)add (?:a|an) reminder',
        r'(?i)schedule (?:a|an) reminder',
    ]
    
    return any(re.search(pattern, text) for pattern in patterns)

def extract_reminder_text(text: str) -> str:
    """
    Extract the actual reminder text from a reminder request.
    
    Args:
        text: Full reminder request
        
    Returns:
        The reminder text
    """
    # Remove 'remind me' and similar prefixes
    patterns = [
        r'(?i)remind me to ',
        r'(?i)remind me ',
        r'(?i)set (?:a|an) reminder to ',
        r'(?i)set (?:a|an) reminder for ',
        r'(?i)create (?:a|an) reminder to ',
        r'(?i)create (?:a|an) reminder for ',
        r'(?i)add (?:a|an) reminder to ',
        r'(?i)add (?:a|an) reminder for ',
        r'(?i)schedule (?:a|an) reminder to ',
        r'(?i)schedule (?:a|an) reminder for ',
    ]
    
    # Replace patterns that indicate timing
    timing_patterns = [
        r'(?i) at \d{1,2}:\d{2}(?: ?[APap][Mm])?',
        r'(?i) on \d{1,2}[./-]\d{1,2}[./-](?:\d{4}|\d{2})',
        r'(?i) in \d+ (?:minute|hour|day|week)s?',
        r'(?i) tomorrow',
        r'(?i) next week',
        r'(?i) every day',
        r'(?i) every (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
        r'(?i) every \d{1,2}(?:st|nd|rd|th)? of (?:each|every) month',
    ]
    
    # First, extract just the reminder text without the prefix
    cleaned_text = text
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            cleaned_text = re.sub(pattern, '', text, 1)
            break
    
    # Then remove timing information if it's at the end
    for pattern in timing_patterns:
        cleaned_text = re.sub(pattern + r'$', '', cleaned_text)
    
    # Clean up any extra spaces
    cleaned_text = cleaned_text.strip()
    
    return cleaned_text if cleaned_text else "Reminder" 