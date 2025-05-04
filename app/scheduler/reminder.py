import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.reminder import Reminder
from models.user import User
from db.database import async_session
from telegram.ext import Application
from telegram import Bot

logger = logging.getLogger(__name__)

class ReminderScheduler:
    """Class to schedule and manage reminders."""
    
    def __init__(self, bot_app: Application):
        """
        Initialize the scheduler.
        
        Args:
            bot_app: Telegram bot application
        """
        self.bot_app = bot_app
        self.bot = bot_app.bot
        self.scheduler = AsyncIOScheduler()
        
    async def schedule_reminders_from_db(self):
        """Load and schedule all active reminders from the database."""
        async with async_session() as session:
            # Get all active reminders
            result = await session.execute(
                select(Reminder).where(Reminder.is_active == True)
            )
            reminders = result.scalars().all()
            
            for reminder in reminders:
                await self.schedule_reminder(reminder)
    
    async def schedule_reminder(self, reminder: Reminder):
        """
        Schedule a reminder.
        
        Args:
            reminder: Reminder object to schedule
        """
        # Get user from database
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.id == reminder.user_id)
            )
            user = result.scalars().first()
            
            if not user:
                logger.error(f"User not found for reminder {reminder.id}")
                return
            
            # Check if reminder is in the past
            # Get current time as timezone-aware datetime
            now = datetime.now(timezone.utc)
            
            if reminder.scheduled_at < now and not reminder.is_recurring:
                logger.warning(f"Reminder {reminder.id} is in the past, marking as inactive")
                reminder.is_active = False
                await session.commit()
                return
            
            # Schedule the reminder
            if reminder.is_recurring:
                # Schedule recurring reminder with cron expression
                self.scheduler.add_job(
                    self.send_reminder,
                    CronTrigger.from_crontab(reminder.recurrence_pattern),
                    id=f"reminder_{reminder.id}",
                    replace_existing=True,
                    kwargs={"reminder_id": reminder.id, "user_id": user.id, "telegram_id": user.telegram_id, "text": reminder.text}
                )
                logger.info(f"Scheduled recurring reminder {reminder.id} with pattern {reminder.recurrence_pattern}")
            else:
                # Schedule one-time reminder
                self.scheduler.add_job(
                    self.send_reminder,
                    DateTrigger(run_date=reminder.scheduled_at),
                    id=f"reminder_{reminder.id}",
                    replace_existing=True,
                    kwargs={"reminder_id": reminder.id, "user_id": user.id, "telegram_id": user.telegram_id, "text": reminder.text}
                )
                logger.info(f"Scheduled one-time reminder {reminder.id} for {reminder.scheduled_at}")
    
    async def send_reminder(self, reminder_id: int, user_id: int, telegram_id: int, text: str):
        """
        Send a reminder to the user.
        
        Args:
            reminder_id: Reminder ID
            user_id: User ID
            telegram_id: Telegram user ID
            text: Reminder text
        """
        try:
            # Send the reminder
            await self.bot.send_message(
                chat_id=telegram_id,
                text=f"🔔 Reminder: {text}",
                parse_mode="Markdown"
            )
            logger.info(f"Sent reminder {reminder_id} to user {user_id}")
            
            # If this is a one-time reminder, mark it as inactive
            async with async_session() as session:
                result = await session.execute(
                    select(Reminder).where(Reminder.id == reminder_id)
                )
                reminder = result.scalars().first()
                
                if reminder and not reminder.is_recurring:
                    reminder.is_active = False
                    await session.commit()
                    
                    # Remove the job from the scheduler
                    self.scheduler.remove_job(f"reminder_{reminder_id}")
                    logger.info(f"Marked one-time reminder {reminder_id} as inactive")
                    
        except Exception as e:
            logger.error(f"Error sending reminder {reminder_id}: {str(e)}")
    
    async def create_reminder(
        self,
        user_id: int,
        telegram_id: int,
        text: str, 
        scheduled_at: datetime,
        is_recurring: bool = False,
        recurrence_pattern: Optional[str] = None
    ) -> Reminder:
        """
        Create a new reminder and schedule it.
        
        Args:
            user_id: User ID
            telegram_id: Telegram user ID
            text: Reminder text
            scheduled_at: When to send the reminder
            is_recurring: Whether this is a recurring reminder
            recurrence_pattern: Cron expression for recurring reminders
            
        Returns:
            Created reminder object
        """
        async with async_session() as session:
            # Make sure scheduled_at is timezone-aware
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
                
            # Create reminder
            reminder = Reminder(
                user_id=user_id,
                text=text,
                scheduled_at=scheduled_at,
                is_recurring=is_recurring,
                recurrence_pattern=recurrence_pattern,
                is_active=True
            )
            
            # Add to database
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)
            
            # Schedule the reminder
            await self.schedule_reminder(reminder)
            
            # Update user's reminders count
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalars().first()
            
            if user:
                user.reminders_count += 1
                await session.commit()
            
            return reminder
    
    async def delete_reminder(self, reminder_id: int) -> bool:
        """
        Delete a reminder.
        
        Args:
            reminder_id: Reminder ID
            
        Returns:
            True if reminder was deleted, False otherwise
        """
        async with async_session() as session:
            # Get reminder
            result = await session.execute(
                select(Reminder).where(Reminder.id == reminder_id)
            )
            reminder = result.scalars().first()
            
            if not reminder:
                return False
            
            # Update user's reminders count
            result = await session.execute(
                select(User).where(User.id == reminder.user_id)
            )
            user = result.scalars().first()
            
            if user and user.reminders_count > 0:
                user.reminders_count -= 1
            
            # Delete reminder
            await session.delete(reminder)
            await session.commit()
            
            # Remove job from scheduler
            try:
                self.scheduler.remove_job(f"reminder_{reminder_id}")
            except Exception as e:
                logger.error(f"Error removing job for reminder {reminder_id}: {str(e)}")
            
            return True
    
    def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        
        # Schedule loading of reminders from database
        asyncio.create_task(self.schedule_reminders_from_db())
        
        logger.info("Reminder scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown()
        logger.info("Reminder scheduler shutdown")

def setup_scheduler(bot_app: Application) -> ReminderScheduler:
    """
    Set up the reminder scheduler.
    
    Args:
        bot_app: Telegram bot application
        
    Returns:
        Configured ReminderScheduler
    """
    return ReminderScheduler(bot_app) 