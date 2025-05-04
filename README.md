# Perplexity Telegram Bot

A Telegram bot integration with Perplexity's Sonar API, built for the Perplexity API hackathon.

## Features

- 🔍 **Real-time Web Search**: Ask any question to get up-to-date information from the web
- 🧠 **Thinking Mode**: See the AI's reasoning process with Sonar Reasoning models
- 🔔 **Reminders**: Set one-time or recurring reminders
- 🖼️ **Image Analysis**: Send photos with questions to get insights
- ⚙️ **Model Selection**: Choose from different Perplexity models for different use cases
- 💬 **Conversation History**: Maintains context through conversations

## Technology Stack

- **FastAPI**: Modern, high-performance web framework
- **Python-Telegram-Bot**: Telegram Bot API wrapper
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Reliable, open-source database
- **Docker & Docker Compose**: Easy containerization and deployment
- **Perplexity Sonar API**: Powerful AI models with real-time web search

## Setup

### Prerequisites

- Docker and Docker Compose
- Telegram Bot Token (from BotFather)
- Perplexity API Key

### Configuration

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/perplexity-telegram-bot.git
   cd perplexity-telegram-bot
   ```

2. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file and add your:
   - Telegram Bot Token
   - Perplexity API Key
   - (Optional) Webhook URL if you want to use webhook mode

### Running the Bot

Start the bot using Docker Compose:

```bash
docker-compose up -d
```

The bot will start and connect to Telegram. If no webhook URL is provided, it will run in polling mode.

## Usage

### Basic Commands

- `/start` - Start the bot
- `/help` - Show help message
- `/settings` - Open settings menu
- `/model` - Change AI model
- `/thinking` - Toggle thinking mode
- `/reminder` - Set a new reminder
- `/list_reminders` - List active reminders
- `/clear` - Clear conversation history

### Setting Reminders

You can set reminders using natural language:

- One-time reminders:
  - "Remind me to call mom tomorrow at 5:00 PM"
  - "Remind me to check email in 30 minutes"

- Recurring reminders:
  - "Remind me to take medicine every day at 9:00 AM"
  - "Remind me to pay bills on the 15th of every month"
  - "Remind me to water plants every Tuesday at 6:00 PM"

### Using Different Models

The bot supports all Perplexity Sonar models:

- **Sonar Pro**: Fast search with grounding
- **Sonar**: Lightweight search
- **Sonar Reasoning Pro**: Premier reasoning with Chain of Thought
- **Sonar Reasoning**: Fast reasoning with search
- **Sonar Deep Research**: Expert-level research
- **R1-1776**: Offline model for creative content

## Architecture

The application is structured as follows:

- **app/**: Main application directory
  - **api/**: API integration (Perplexity)
  - **bot/**: Telegram bot handlers
  - **db/**: Database connection and management
  - **models/**: Database models
  - **scheduler/**: Reminder scheduling system
  - **main.py**: Application entry point

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Perplexity for their powerful Sonar API
- Telegram for their Bot API
- All the open-source libraries used in this project 