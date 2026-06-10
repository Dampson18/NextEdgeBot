# 1. Clone or create project directory
mkdir nextedge-bot
cd nextedge-bot

# 2. Create virtual environment

source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file and add your tokens

# 5. Run the bot
python nextedge_bot.py

# 🤖 NextEdge Bot

<div align="center">

**Your AI-Powered Tech Assistant on Telegram**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%20AI-orange.svg)](https://deepmind.google/technologies/gemini/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

## 📌 Overview

NextEdge Bot is a feature-rich Telegram bot developed by **NextEdge Tech Studio**. It provides AI-powered assistance for developers and tech enthusiasts, offering tech tips, code templates, and conversational AI capabilities.

## ✨ Features

### 💬 NextEdge Chat
- Natural, context-aware conversations
- Remembers chat history (up to 10 exchanges)
- Warm and engaging responses
- Commands: `/chat`, `/endchat`, `/newchat`, `/chatstatus`

### 💡 Tech Tips Database
- **70+** programming tips across **8 categories**:
  - 🐍 Python
  - 📜 JavaScript
  - ⚛️ React
  - 🔧 Git
  - 💻 VS Code
  - 🐳 Docker
  - 🌐 Web Development
  - 🔒 Cybersecurity

### 📝 Code Templates
- **20+** production-ready templates including:
  - REST API (FastAPI)
  - Web Scraper (BeautifulSoup)
  - Flask Application
  - React Components
  - Express.js API
  - MongoDB Connection
  - Dockerfile
  - GitHub Actions CI/CD
  - And more!

### ⭐ Additional Features
- Interactive menu system
- User feedback collection (1-5 rating)
- Usage statistics tracking
- Rate limiting (15 requests/minute)
- Admin dashboard
- Error logging

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Google Gemini API Key (from [Google AI Studio](https://aistudio.google.com/))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Dampson18/NextEdgeBot.git
cd NextEdgeBot
