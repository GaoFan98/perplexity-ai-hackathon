import logging
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session
from api.perplexity import PerplexityAPI
from services.news_service import NewsService

logger = logging.getLogger(__name__)

class NewsScheduler:
    def __init__(self, bot, perplexity_api: PerplexityAPI):
        self.scheduler = AsyncIOScheduler()
        self.bot = bot
        self.news_service = NewsService(perplexity_api)
        
    def start(self):
        """Start the news scheduler."""
        # Run every 5 minutes to check for subscriptions
        self.scheduler.add_job(
            self._process_due_subscriptions,
            IntervalTrigger(minutes=5),
            id="process_news_subscriptions",
            replace_existing=True
        )
        
        # Add a job to check hourly subscriptions
        self.scheduler.add_job(
            self._process_hourly_subscriptions,
            IntervalTrigger(hours=1),
            id="process_hourly_subscriptions",
            replace_existing=True
        )
        
        # Add a job to check daily subscriptions
        self.scheduler.add_job(
            self._process_daily_subscriptions,
            IntervalTrigger(days=1),
            id="process_daily_subscriptions",
            replace_existing=True
        )
        
        # Add a job to check weekly subscriptions
        self.scheduler.add_job(
            self._process_weekly_subscriptions,
            IntervalTrigger(weeks=1),
            id="process_weekly_subscriptions",
            replace_existing=True
        )
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("News scheduler started")
        
    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("News scheduler shut down")
    
    async def _process_due_subscriptions(self):
        """Process all due subscriptions."""
        try:
            async with async_session() as session:
                subscriptions = await self.news_service.get_due_subscriptions(session)
                
                for subscription in subscriptions:
                    await self.news_service.process_subscription(
                        session=session,
                        subscription=subscription,
                        bot=self.bot
                    )
        except Exception as e:
            logger.error(f"Error processing due subscriptions: {str(e)}")
    
    async def _process_hourly_subscriptions(self):
        """Process hourly subscriptions."""
        try:
            async with async_session() as session:
                await self._process_subscriptions_by_frequency(session, "hourly")
        except Exception as e:
            logger.error(f"Error processing hourly subscriptions: {str(e)}")
    
    async def _process_daily_subscriptions(self):
        """Process daily subscriptions."""
        try:
            async with async_session() as session:
                await self._process_subscriptions_by_frequency(session, "daily")
        except Exception as e:
            logger.error(f"Error processing daily subscriptions: {str(e)}")
    
    async def _process_weekly_subscriptions(self):
        """Process weekly subscriptions."""
        try:
            async with async_session() as session:
                await self._process_subscriptions_by_frequency(session, "weekly")
        except Exception as e:
            logger.error(f"Error processing weekly subscriptions: {str(e)}")
    
    async def _process_subscriptions_by_frequency(self, session: AsyncSession, frequency: str):
        """Process subscriptions by frequency."""
        from sqlalchemy import select
        from models.topic_subscription import TopicSubscription
        
        result = await session.execute(
            select(TopicSubscription).where(
                TopicSubscription.is_active == True,
                TopicSubscription.frequency == frequency
            )
        )
        
        subscriptions = result.scalars().all()
        
        for subscription in subscriptions:
            await self.news_service.process_subscription(
                session=session,
                subscription=subscription,
                bot=self.bot
            )

def setup_news_scheduler(bot, perplexity_api: PerplexityAPI) -> NewsScheduler:
    """Set up and start the news scheduler."""
    scheduler = NewsScheduler(bot, perplexity_api)
    return scheduler 