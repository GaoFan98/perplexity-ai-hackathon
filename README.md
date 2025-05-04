# Perplexity AI Telegram Bot

A powerful Telegram bot that integrates with Perplexity's Sonar API, providing AI-powered search, reasoning, and assistance to Telegram users. This project was inspired by Perplexity's official WhatsApp integration, but created for Telegram's massive global user base of over 800 million active users.

## Inspiration

After seeing Perplexity AI's integration with WhatsApp, I wanted to bring similar functionality to Telegram, which has a larger user base across many countries and offers more flexible bot capabilities. Telegram is particularly popular in regions where WhatsApp isn't the dominant messenger, giving this integration a wider potential reach. This project demonstrates how Perplexity's powerful AI search and reasoning capabilities can be leveraged on the Telegram platform.

## Features

- 🔍 **Real-time Web Search**: Get up-to-date information directly from the web
- 🧠 **Thinking Mode**: See the AI's step-by-step reasoning process with Sonar Reasoning models
- 🔔 **Smart Reminders**: Set one-time or recurring reminders with natural language
- 🖼️ **Image Analysis**: Send photos with questions to analyze images and get insights
- ⚙️ **Model Selection**: Choose from different Perplexity models for different use cases
- 💬 **Conversation History**: Maintains context through conversations for meaningful follow-ups
- 📚 **Reference Attribution**: Properly cites sources from web searches with clickable links
- 🌐 **Domain Filtering**: Focus searches on specific websites or domains
- 🕒 **Recency Filtering**: Filter search results by time period (day, week, month)

## Technology Stack

- **FastAPI**: Modern, high-performance asynchronous web framework
- **Python-Telegram-Bot**: Comprehensive Python wrapper for the Telegram Bot API
- **SQLAlchemy**: SQL toolkit and Object-Relational Mapper
- **PostgreSQL**: Powerful, open-source relational database
- **Docker & Docker Compose**: Containerization for easy deployment
- **Perplexity Sonar API**: AI models with real-time web search capabilities
- **APScheduler**: Advanced Python scheduler for reminders

## Setup Guide

### Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (obtained from BotFather)
- Perplexity API Key

### Step-by-Step Setup

1. **Create a Telegram Bot**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow instructions to create a bot
   - Save the API token provided

2. **Get a Perplexity API Key**:
   - Sign up at [Perplexity AI](https://www.perplexity.ai/)
   - Go to account settings and generate an API key

3. **Clone and Configure**:
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/perplexity-telegram-bot.git
   cd perplexity-telegram-bot
   
   # Create environment file
   cp .env.example .env
   
   # Edit .env file with your credentials
   nano .env
   ```

4. **Configure Environment Variables**:
   - `TELEGRAM_TOKEN`: Your Telegram Bot token
   - `PERPLEXITY_API_KEY`: Your Perplexity API key
   - `DATABASE_URL`: PostgreSQL connection string (default: postgres://user:password@db:5432/perplexity_bot)
   - `WEBHOOK_URL`: (Optional) If deploying with webhooks instead of polling
   - `ADMIN_USER_IDS`: Comma-separated list of admin Telegram user IDs

5. **Start the Bot**:
   ```bash
   # Build and start containers
   docker-compose up -d
   
   # Check logs
   docker-compose logs -f
   ```

### Testing the Bot

1. **Basic Tests**:
   - Open Telegram and search for your bot by username
   - Send `/start` to initialize the bot
   - Send a simple question like "What is the weather in New York?"

2. **Feature Testing**:
   - **Test thinking mode**: Send `/thinking` to toggle thinking mode, then ask a complex question
   - **Test image analysis**: Send a photo with a caption asking about the image
   - **Test reminders**: Say "Remind me to check email in 10 minutes"
   - **Test model selection**: Use `/model` to change the AI model

3. **Debugging**:
   - Check container logs for errors: `docker-compose logs -f`
   - Ensure PostgreSQL container is running properly
   - Verify environment variables are set correctly

## Using the Bot

### Basic Commands

- `/start` - Initialize the bot
- `/help` - Display help message with command list
- `/settings` - Access settings menu
- `/model` - Change AI model
- `/thinking` - Toggle reasoning visualization
- `/reminder` - Set a new reminder
- `/list_reminders` - Display all active reminders
- `/clear` - Reset conversation history

### Advanced Features

#### Thinking Mode

When thinking mode is enabled, the bot shows the step-by-step reasoning process before providing answers, which is especially useful for complex questions or math problems.

#### Setting Reminders

The bot understands natural language for setting reminders:

- **One-time reminders**:
  - "Remind me about the meeting tomorrow at 3 PM"
  - "Remind me to take out the trash in 30 minutes"

- **Recurring reminders**:
  - "Remind me to take vitamins every morning at 9 AM"
  - "Remind me to pay rent on the 1st of every month"
  - "Remind me to water plants every Monday and Thursday at 6 PM"

#### Image Analysis

Send a photo with a question as the caption to analyze images:
- "What's in this picture?"
- "Can you identify this plant?"
- "What does this error message mean?"

#### Available Models

Choose different models based on your needs:

- **Sonar Pro**: Fast general queries with web search
- **Sonar**: Lightweight, cost-effective search
- **Sonar Reasoning Pro**: Advanced reasoning with Chain of Thought capabilities
- **Sonar Reasoning**: Fast reasoning with search integration
- **Sonar Deep Research**: Comprehensive research with exhaustive search
- **R1-1776**: Optimized for uncensored, factual information

## Architecture

The application follows a modular structure:

- **app/**: Main application directory
  - **api/**: Perplexity API integration
  - **bot/**: Telegram handlers and utilities
  - **db/**: Database connection and session management
  - **models/**: SQLAlchemy models for data persistence
  - **scheduler/**: Reminder scheduling system
  - **main.py**: Application entry point

## Contribution

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Perplexity AI for their powerful Sonar API
- Telegram for their extensive Bot API
- All the open-source libraries that made this project possible 