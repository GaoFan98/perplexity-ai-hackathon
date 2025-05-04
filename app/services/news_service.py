import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.perplexity import PerplexityAPI
from models.user import User
from models.topic_subscription import TopicSubscription

logger = logging.getLogger(__name__)

class NewsService:
    def __init__(self, perplexity_api: PerplexityAPI):
        self.perplexity_api = perplexity_api
        
    async def subscribe_to_topic(
        self, 
        session: AsyncSession, 
        user_id: int, 
        topic: str, 
        frequency: str = "daily"
    ) -> TopicSubscription:
        """Subscribe a user to a topic."""
        # Check if subscription already exists
        result = await session.execute(
            select(TopicSubscription).where(
                TopicSubscription.user_id == user_id,
                TopicSubscription.topic == topic
            )
        )
        existing = result.scalars().first()
        
        if existing:
            if not existing.is_active:
                # Reactivate existing subscription
                existing.is_active = True
                existing.frequency = frequency
                existing.next_run = self._calculate_next_run(frequency)
                await session.commit()
                return existing
            else:
                # Update frequency if changed
                if existing.frequency != frequency:
                    existing.frequency = frequency
                    existing.next_run = self._calculate_next_run(frequency)
                    await session.commit()
                return existing
                
        # Create new subscription
        next_run = self._calculate_next_run(frequency)
        
        subscription = TopicSubscription(
            user_id=user_id,
            topic=topic,
            frequency=frequency,
            next_run=next_run,
            is_active=True
        )
        
        session.add(subscription)
        await session.commit()
        await session.refresh(subscription)
        
        return subscription
        
    async def unsubscribe_from_topic(
        self,
        session: AsyncSession,
        user_id: int,
        topic_id: int
    ) -> bool:
        """Unsubscribe a user from a topic."""
        result = await session.execute(
            select(TopicSubscription).where(
                TopicSubscription.id == topic_id,
                TopicSubscription.user_id == user_id
            )
        )
        subscription = result.scalars().first()
        
        if not subscription:
            return False
            
        subscription.is_active = False
        await session.commit()
        
        return True
        
    async def get_user_subscriptions(
        self,
        session: AsyncSession,
        user_id: int
    ) -> List[TopicSubscription]:
        """Get all active subscriptions for a user."""
        result = await session.execute(
            select(TopicSubscription).where(
                TopicSubscription.user_id == user_id,
                TopicSubscription.is_active == True
            ).order_by(TopicSubscription.created_at.desc())
        )
        
        return result.scalars().all()
        
    async def get_due_subscriptions(
        self,
        session: AsyncSession
    ) -> List[TopicSubscription]:
        """Get all subscriptions that are due to run."""
        now = datetime.now(timezone.utc)
        
        result = await session.execute(
            select(TopicSubscription).where(
                TopicSubscription.is_active == True,
                TopicSubscription.next_run <= now
            )
        )
        
        return result.scalars().all()
        
    async def process_subscription(
        self,
        session: AsyncSession,
        subscription: TopicSubscription,
        bot
    ) -> bool:
        """Process a single subscription by fetching news and sending to user."""
        try:
            # Get user
            user_result = await session.execute(
                select(User).where(User.id == subscription.user_id)
            )
            user = user_result.scalars().first()
            
            if not user or not user.telegram_id:
                logger.error(f"User not found for subscription {subscription.id}")
                return False
                
            # Get breaking news for topic
            news = await self._get_breaking_news(subscription.topic)
            
            if not news.get("success"):
                logger.error(f"Failed to get news for topic {subscription.topic}: {news.get('error')}")
                return False
                
            # Send message to user
            await bot.send_message(
                chat_id=user.telegram_id,
                text=f"📰 *Breaking News Update: {subscription.topic}*\n\n{news.get('answer')}",
                parse_mode="Markdown"
            )
            
            # Update subscription
            subscription.last_run = datetime.now(timezone.utc)
            subscription.next_run = self._calculate_next_run(subscription.frequency)
            await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing subscription {subscription.id}: {str(e)}")
            return False
            
    async def _get_breaking_news(self, topic: str) -> Dict[str, Any]:
        """Get breaking news for a topic using Perplexity API."""
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        query = (
            f"What are the latest breaking news or developments about '{topic}' as of {current_date}? "
            f"Please provide a concise summary of the 2-3 most significant recent developments, "
            f"including only factual information. Focus on events from the last 24 hours if available."
        )
        
        response = await self.perplexity_api.ask_question(
            query=query,
            model="sonar-pro",  # Using the model with real-time search capability
        )
        
        return response
        
    def _calculate_next_run(self, frequency: str) -> datetime:
        """Calculate the next run time based on frequency."""
        now = datetime.now(timezone.utc)
        
        if frequency == "hourly":
            return now + timedelta(hours=1)
        elif frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        else:
            # Default to daily
            return now + timedelta(days=1) 