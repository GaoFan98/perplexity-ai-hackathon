# Perplexity Telegram Bot
A Telegram bot integration with Perplexity's Sonar API, built for the Perplexity API hackathon.

## Features
- 🔍 **Real-time Web Search**: Ask any question to get up-to-date information from the web
- 🧠 **Thinking Mode**: See the AI's reasoning process with Sonar Reasoning models
- 🔔 **Reminders**: Set one-time or recurring reminders
- 📰 **Breaking News Updates**: Subscribe to topics and receive automatic updates at chosen intervals
- 💻 **Code Analysis & Enhancement**: Send code snippets for analysis, optimization, and bug fixing
- ⚙️ **Model Selection**: Choose from different Perplexity models for different use cases
- 💬 **Conversation History**: Maintains context through conversations
- 📚 **Reference Attribution**: Properly cites sources from web searches with clickable links
- 🌐 **Domain Filtering**: Focus searches on specific websites or domains
- 🕒 **Recency Filtering**: Filter search results by time period (day, week, month)

## Technology Stack
- **FastAPI**: Modern, high-performance web framework
- **Python-Telegram-Bot**: Telegram Bot API wrapper
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Reliable, open-source database
- **Docker & Docker Compose**: Easy containerization and deployment
- **Perplexity Sonar API**: Powerful AI models with real-time web search
- **APScheduler**: Advanced Python scheduler for reminders and news updates

## Judging Criteria Addressed

### Technological Implementation
- **Quality Software Development**: The project follows clean architecture principles with separation of concerns (services, models, bot handlers), robust error handling, and comprehensive logging.
- **Tool Leverage**: We thoroughly leverage Perplexity's Sonar API, utilizing multiple models (Pro, Reasoning, Deep Research) and features (web search, code analysis).
- **Code Quality**: The codebase maintains consistency in coding style, uses typed hints for better IDE support, employs async/await patterns for efficient I/O operations, and includes comprehensive documentation.

### Design
- **User Experience**: The bot provides an intuitive conversational interface with clear command documentation, interactive buttons for settings, formatted responses with proper citations, and easy-to-use natural language inputs.
- **Frontend/Backend Balance**: While Telegram provides the frontend UI, we've enhanced it with custom inline keyboards, specially formatted responses, and an intelligent conversational flow. The backend is robust with a database-driven persistence layer, scheduled background tasks, and efficient API integration.

### Potential Impact
- **Target Community**: For researchers, students, developers, and professionals, this bot provides immediate access to AI-powered research and analysis tools without requiring additional apps.
- **Beyond Target Community**: The bot could serve as an educational tool in regions with limited internet access but good Telegram connectivity, as a real-time news curator for journalists, or as a code assistant for development teams.

### Quality of the Idea
- **Creativity**: The integration of scheduled breaking news, intelligent code analysis, and natural language reminders creates a unique AI assistant experience specific to Telegram.
- **Improvement Over Existing Solutions**: While Perplexity offers a WhatsApp integration, our solution adds Telegram support with expanded features (recurring reminders, news subscriptions, code analysis) and enhanced user interaction patterns.

## Setup
### Prerequisites
- Docker and Docker Compose
- Telegram Bot Token (from BotFather)
- Perplexity API Key

### Configuration
Clone this repository:
```bash
git clone https://github.com/yourusername/perplexity-telegram-bot.git
cd perplexity-telegram-bot
```

Create a .env file based on .env.example:
```bash
cp .env.example .env
```

Edit the .env file and add your:
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
- `/subscribe TOPIC` - Subscribe to news updates on a topic
- `/mysubs` - List your news subscriptions
- `/clear` - Clear conversation history

### Setting Reminders
You can set reminders using natural language:

**One-time reminders**:
- "Remind me to call mom tomorrow at 5:00 PM"
- "Remind me to check email in 30 minutes"

**Recurring reminders**:
- "Remind me to take medicine every day at 9:00 AM"
- "Remind me to pay bills on the 15th of every month"
- "Remind me to water plants every Tuesday at 6:00 PM"

### Breaking News Subscriptions
Get regular updates on topics of interest:
- Use `/subscribe AI` to follow AI news (replace with any topic)
- Choose hourly, daily, or weekly updates
- View and manage subscriptions with `/mysubs`

### Code Analysis & Enhancement
Send code to analyze, debug, or enhance:
- Send code wrapped in triple backticks (```code here```)
- Add your question or request before/after the code block
- Example: "Fix this bug: ```function example() {...}```"
- Get detailed analysis, optimization suggestions, and bug fixes

### Using Different Models
The bot supports all Perplexity Sonar models:
- **Sonar Pro**: Fast search with grounding
- **Sonar**: Lightweight search
- **Sonar Reasoning Pro**: Premier reasoning with Chain of Thought
- **Sonar Reasoning**: Fast reasoning with search
- **Sonar Deep Research**: Expert-level research
- **R1-1776**: Offline model for creative content

## Future Improvements

### PDF Document Analysis
We plan to implement PDF document analysis by:
1. Adding a PDF upload handler that accepts PDF files via Telegram
2. Dividing the PDF into individual pages or sections for more effective analysis
3. Processing each section with Perplexity's text analysis capabilities
4. Creating a searchable index of document content
5. Allowing users to ask questions about the document content using natural language
6. Providing responses with page references and exact citations

This feature will be particularly valuable for researchers, students, and professionals who need to quickly extract insights from research papers, reports, and other documents without reading them completely.

### Voice Assistant Integration
We're working on adding voice message analysis through:
1. Utilizing Telegram's voice message API to receive user voice recordings
2. Implementing speech-to-text processing to transcribe voice messages
3. Analyzing the transcribed text using Perplexity's text analysis capabilities
4. Generating relevant, concise voice responses
5. Supporting voice-based follow-up questions and continued conversations

This feature will make the bot more accessible for users who prefer voice interaction and useful in situations where typing is impractical, such as while driving or when users have their hands full.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

### Demo photos

![image](https://github.com/user-attachments/assets/65dca347-ecb1-4949-85b5-f396b5f8008a)

![image](https://github.com/user-attachments/assets/c5fceece-8d47-42e6-b3cf-eb1924e34289)

![image](https://github.com/user-attachments/assets/e688311e-edfe-4a42-a537-7d1a6dd312c0)

![image](https://github.com/user-attachments/assets/10ffce53-d3e6-4fad-9a5c-5e3fca0a107a)

![image](https://github.com/user-attachments/assets/eabb350e-2578-4b30-bcf6-fdf2e23a7f59)





