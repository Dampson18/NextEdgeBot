import logging
import os
import re
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

# Correct imports for the new Google GenAI SDK
from google import genai
from google.genai import types

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler, ConversationHandler
)
from telegram.constants import ChatAction
from telegram.error import TimedOut, NetworkError

# --- Configuration ---
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Handle ADMIN_USER_ID properly
admin_user_id_str = os.getenv("ADMIN_USER_ID", "0")
try:
    ADMIN_USER_ID = int(admin_user_id_str) if admin_user_id_str and admin_user_id_str.isdigit() else 0
except ValueError:
    ADMIN_USER_ID = 0
    print(f"⚠️ Warning: Invalid ADMIN_USER_ID value '{admin_user_id_str}'. Set to 0 (disabled).")

# Company Configuration
COMPANY_NAME = "NextEdge Tech Studio"
COMPANY_TAGLINE = "Pushing the Boundaries of Technology"
COMPANY_WEBSITE = "https://nextedge-lime.vercel.app"
COMPANY_EMAIL = "kelvinfaraday15@gmail.com"
COMPANY_SOCIAL = {
    "github": "https://github.com/Dampson18",
    "linkedin": "https://linkedin.com/company/nextedge",
    "twitter": "https://twitter.com/nextedge"
}

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler('nextedge_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Database Setup ---
class Database:
    def __init__(self, filename='bot_data.json'):
        self.filename = filename
        self.data = self.load()
    
    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {
            'users': {},
            'feedback': [],
            'stats': {
                'total_messages': 0,
                'total_commands': 0,
                'start_date': datetime.now().isoformat()
            }
        }
    
    def save(self):
        with open(self.filename, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def add_user(self, user_id, user_data):
        if str(user_id) not in self.data['users']:
            self.data['users'][str(user_id)] = user_data
            self.save()
            return True
        return False
    
    def update_user_stats(self, user_id, field, value):
        if str(user_id) in self.data['users']:
            self.data['users'][str(user_id)][field] = value
            self.save()
    
    def add_feedback(self, user_id, username, feedback, rating):
        self.data['feedback'].append({
            'user_id': user_id,
            'username': username,
            'feedback': feedback,
            'rating': rating,
            'timestamp': datetime.now().isoformat()
        })
        self.save()
    
    def increment_stat(self, stat_name):
        self.data['stats'][stat_name] = self.data['stats'].get(stat_name, 0) + 1
        self.save()

db = Database()

# --- Rate Limiting ---
class RateLimiter:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
    
    def is_allowed(self, user_id):
        now = datetime.now()
        user_requests = self.requests[user_id]
        user_requests = [req_time for req_time in user_requests 
                        if now - req_time < timedelta(seconds=self.time_window)]
        self.requests[user_id] = user_requests
        
        if len(user_requests) >= self.max_requests:
            return False
        
        self.requests[user_id].append(now)
        return True

rate_limiter = RateLimiter(max_requests=15, time_window=60)

# --- Tech Tips Database ---
TECH_TIPS = {
    "python": [
        "💡 *Python Tip*: Use `@dataclass` for classes that primarily store data.",
        "💡 *Python Tip*: Use `functools.lru_cache` to cache expensive function calls.",
        "💡 *Python Tip*: List comprehensions make code cleaner and often faster.",
        "💡 *Python Tip*: Use `enumerate()` when you need both index and value in a loop.",
        "💡 *Python Tip*: Use `zip()` to iterate through multiple lists simultaneously.",
        "💡 *Python Tip*: Use f-strings for readable string formatting: `f'Hello {name}'`.",
        "💡 *Python Tip*: Use virtual environments (`venv`) to manage project dependencies.",
        "💡 *Python Tip*: Use `pathlib` instead of `os.path` for cleaner file handling.",
        "💡 *Python Tip*: Use `collections.Counter` to count items efficiently.",
        "💡 *Python Tip*: Use context managers (`with`) when working with files."
    ],

    "javascript": [
        "💡 *JavaScript Tip*: Use optional chaining (`?.`) to avoid undefined errors.",
        "💡 *JavaScript Tip*: Use destructuring for cleaner object and array access.",
        "💡 *JavaScript Tip*: Use template literals: `` `Hello ${name}` ``.",
        "💡 *JavaScript Tip*: Prefer `const` by default and use `let` only when needed.",
        "💡 *JavaScript Tip*: Use array methods like `map()`, `filter()`, and `reduce()`.",
        "💡 *JavaScript Tip*: Use `===` instead of `==` for strict comparisons.",
        "💡 *JavaScript Tip*: Use async/await instead of deeply nested promises.",
        "💡 *JavaScript Tip*: Use default parameters: `function greet(name='Guest')`.",
        "💡 *JavaScript Tip*: Use the spread operator (`...`) for cloning arrays and objects.",
        "💡 *JavaScript Tip*: Use `Array.from()` to convert iterable objects into arrays."
    ],

    "react": [
        "💡 *React Tip*: Use `React.memo()` to prevent unnecessary re-renders.",
        "💡 *React Tip*: Create custom hooks to reuse stateful logic.",
        "💡 *React Tip*: Keep components small and focused on a single responsibility.",
        "💡 *React Tip*: Use keys properly when rendering lists.",
        "💡 *React Tip*: Avoid unnecessary state; derive values when possible.",
        "💡 *React Tip*: Use `useCallback()` for stable function references.",
        "💡 *React Tip*: Use `useMemo()` for expensive calculations.",
        "💡 *React Tip*: Organize components into reusable UI modules.",
        "💡 *React Tip*: Lift state up when multiple components need shared data.",
        "💡 *React Tip*: Use error boundaries to handle UI crashes gracefully."
    ],

    "git": [
        "💡 *Git Tip*: Use `git add -p` for interactive staging.",
        "💡 *Git Tip*: Visualize history with `git log --graph --oneline --decorate`.",
        "💡 *Git Tip*: Write meaningful commit messages.",
        "💡 *Git Tip*: Create branches for new features instead of working directly on main.",
        "💡 *Git Tip*: Use `git stash` to temporarily save uncommitted work.",
        "💡 *Git Tip*: Use `.gitignore` to exclude unnecessary files.",
        "💡 *Git Tip*: Use `git diff` before committing changes.",
        "💡 *Git Tip*: Pull regularly to avoid merge conflicts.",
        "💡 *Git Tip*: Use tags for important releases.",
        "💡 *Git Tip*: Learn `git rebase` for a cleaner commit history."
    ],

    "vscode": [
        "💡 *VS Code Tip*: Use multi-cursor editing with `Alt+Click`.",
        "💡 *VS Code Tip*: Open the Command Palette with `Ctrl+Shift+P`.",
        "💡 *VS Code Tip*: Use `Ctrl+P` to quickly find files.",
        "💡 *VS Code Tip*: Install extensions only when necessary.",
        "💡 *VS Code Tip*: Use code snippets to speed up development.",
        "💡 *VS Code Tip*: Use the integrated terminal (`Ctrl+``).",
        "💡 *VS Code Tip*: Enable Auto Save for faster workflows.",
        "💡 *VS Code Tip*: Use `F2` to rename variables across files.",
        "💡 *VS Code Tip*: Use `Ctrl+Shift+F` for global search.",
        "💡 *VS Code Tip*: Learn keyboard shortcuts to boost productivity."
    ],

    "docker": [
        "💡 *Docker Tip*: Use multi-stage builds to reduce image size.",
        "💡 *Docker Tip*: Add a `.dockerignore` file to exclude unnecessary files.",
        "💡 *Docker Tip*: Use official base images whenever possible.",
        "💡 *Docker Tip*: Keep containers stateless when practical.",
        "💡 *Docker Tip*: Use environment variables for configuration.",
        "💡 *Docker Tip*: Tag images with versions instead of `latest`.",
        "💡 *Docker Tip*: Use Docker Compose for multi-container applications.",
        "💡 *Docker Tip*: Minimize the number of layers in Dockerfiles.",
        "💡 *Docker Tip*: Scan images regularly for vulnerabilities.",
        "💡 *Docker Tip*: Use volumes to persist data outside containers."
    ],

    "web": [
        "💡 *Web Dev Tip*: Optimize images before uploading them.",
        "💡 *Web Dev Tip*: Use semantic HTML for accessibility and SEO.",
        "💡 *Web Dev Tip*: Minify CSS and JavaScript in production.",
        "💡 *Web Dev Tip*: Always test your website on mobile devices.",
        "💡 *Web Dev Tip*: Use lazy loading for images.",
        "💡 *Web Dev Tip*: Compress assets with Gzip or Brotli.",
        "💡 *Web Dev Tip*: Use HTTPS for all websites.",
        "💡 *Web Dev Tip*: Reduce HTTP requests to improve performance.",
        "💡 *Web Dev Tip*: Validate forms on both client and server sides.",
        "💡 *Web Dev Tip*: Use browser developer tools for debugging."
    ],

    "cybersecurity": [
        "🔒 *Security Tip*: Use strong, unique passwords for every account.",
        "🔒 *Security Tip*: Enable Two-Factor Authentication (2FA) whenever possible.",
        "🔒 *Security Tip*: Keep software and operating systems updated.",
        "🔒 *Security Tip*: Never click suspicious links from unknown sources.",
        "🔒 *Security Tip*: Back up important data regularly.",
        "🔒 *Security Tip*: Use a password manager.",
        "🔒 *Security Tip*: Verify email senders before downloading attachments.",
        "🔒 *Security Tip*: Avoid using public Wi-Fi without protection.",
        "🔒 *Security Tip*: Lock your devices when not in use.",
        "🔒 *Security Tip*: Review app permissions regularly."
    ]
}


# --- Code Templates Database ---
CODE_TEMPLATES = {
    "rest_api": {
        "title": "REST API with FastAPI",
        "code": "FastAPI CRUD API template..."
    },

    "web_scraper": {
        "title": "Web Scraper with BeautifulSoup",
        "code": "BeautifulSoup scraper template..."
    },

    "flask_app": {
        "title": "Flask Starter App",
        "code": """```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'message': 'Hello World'})

if __name__ == '__main__':
    app.run(debug=True)
```"""
    },

    "django_model": {
        "title": "Django Model",
        "code": """```python
from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name
```"""
    },

    "react_component": {
        "title": "React Functional Component",
        "code": """```javascript
import React from 'react';

function Welcome({ name }) {
  return <h1>Hello, {name}!</h1>;
}

export default Welcome;
```"""
    },

    "react_hook": {
        "title": "Custom React Hook",
        "code": """```javascript
import { useState } from 'react';

export default function useCounter() {
  const [count, setCount] = useState(0);

  const increment = () => setCount(c => c + 1);

  return { count, increment };
}
```"""
    },

    "node_api": {
        "title": "Express.js API",
        "code": """```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.get('/', (req, res) => {
  res.json({ message: 'API Running' });
});

app.listen(3000);
```"""
    },

    "mongodb_connection": {
        "title": "MongoDB Connection",
        "code": """```javascript
const mongoose = require('mongoose');

mongoose.connect('mongodb://localhost:27017/mydb')
  .then(() => console.log('Connected'))
  .catch(err => console.error(err));
```"""
    },

    "sql_query": {
        "title": "SQL Create Table",
        "code": """```sql
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```"""
    },

    "html_page": {
        "title": "Basic HTML5 Template",
        "code": """```html
<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>My Website</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>
```"""
    },

    "css_card": {
        "title": "Responsive CSS Card",
        "code": """```css
.card {
    max-width: 350px;
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,.1);
}
```"""
    },

    "javascript_fetch": {
        "title": "Fetch API Example",
        "code": """```javascript
async function getUsers() {
    const response = await fetch('/api/users');
    const data = await response.json();
    console.log(data);
}
```"""
    },

    "python_gui": {
        "title": "Tkinter GUI",
        "code": """```python
import tkinter as tk

root = tk.Tk()
root.title('My App')

label = tk.Label(root, text='Hello World')
label.pack()

root.mainloop()
```"""
    },

    "discord_bot": {
        "title": "Discord Bot",
        "code": """```python
import discord

client = discord.Client(
    intents=discord.Intents.default()
)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

client.run('TOKEN')
```"""
    },

    "telegram_bot": {
        "title": "Telegram Bot",
        "code": """```python
from telegram.ext import Application, CommandHandler

async def start(update, context):
    await update.message.reply_text('Hello!')

app = Application.builder().token('TOKEN').build()
app.add_handler(CommandHandler('start', start))

app.run_polling()
```"""
    },

    "streamlit_app": {
        "title": "Streamlit Dashboard",
        "code": """```python
import streamlit as st

st.title('My Dashboard')
st.write('Welcome to Streamlit!')
```"""
    },

    "websocket_server": {
        "title": "Python WebSocket Server",
        "code": """```python
import asyncio
import websockets

async def handler(ws):
    async for message in ws:
        await ws.send(f'Echo: {message}')

asyncio.run(
    websockets.serve(handler, 'localhost', 8765)
)
```"""
    },

    "jwt_auth": {
        "title": "JWT Authentication",
        "code": """```python
import jwt

payload = {'user_id': 1}
token = jwt.encode(payload, 'secret', algorithm='HS256')

print(token)
```"""
    },

    "dockerfile": {
        "title": "Dockerfile Template",
        "code": """```dockerfile
FROM python:3.12

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```"""
    },

    "github_action": {
        "title": "GitHub Actions CI",
        "code": """```yaml
name: Python CI

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - run: pip install -r requirements.txt
      - run: pytest
```"""
    }
}

# --- Initialize Google GenAI SDK ---
if not GOOGLE_API_KEY:
    logger.error("GOOGLE_API_KEY not found")
    print("❌ ERROR: GOOGLE_API_KEY not found in .env file")
    print("Please add your Google API key to the .env file")
    exit(1)

try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    logger.info("Google GenAI client initialized successfully")
    print("✅ Google GenAI client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Google GenAI: {e}")
    print(f"❌ Failed to initialize Google GenAI: {e}")
    exit(1)

# --- Helper Functions ---
def get_tech_tip(category: str = None) -> str:
    import random
    if category and category in TECH_TIPS:
        tips = TECH_TIPS[category]
    else:
        all_tips = []
        for tips_list in TECH_TIPS.values():
            all_tips.extend(tips_list)
        tips = all_tips
    return random.choice(tips) if tips else "Keep coding! 💻"

def create_main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("💡 Tech Tips", callback_data='menu_tips'),
            InlineKeyboardButton("📝 Code Templates", callback_data='menu_templates')
        ],
        [
            InlineKeyboardButton("💬 NextEdge Chat", callback_data='menu_chat'),
            InlineKeyboardButton("ℹ️ About Us", callback_data='menu_about')
        ],
        [
            InlineKeyboardButton("📞 Contact", callback_data='menu_contact'),
            InlineKeyboardButton("⭐ Feedback", callback_data='menu_feedback')
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data='menu_stats'),
            InlineKeyboardButton("🆘 Help", callback_data='menu_help')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_tips_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🐍 Python", callback_data='tip_python'),
            InlineKeyboardButton("📜 JavaScript", callback_data='tip_javascript')
        ],
        [
            InlineKeyboardButton("⚛️ React", callback_data='tip_react'),
            InlineKeyboardButton("🐳 Docker", callback_data='tip_docker')
        ],
        [
            InlineKeyboardButton("🔧 Git", callback_data='tip_git'),
            InlineKeyboardButton("💻 VS Code", callback_data='tip_vscode')
        ],
        [
            InlineKeyboardButton("🎲 Random", callback_data='tip_random'),
            InlineKeyboardButton("⬅️ Back", callback_data='back_main')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_templates_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🌐 REST API", callback_data='template_rest_api'),
            InlineKeyboardButton("🕷️ Web Scraper", callback_data='template_web_scraper')
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data='back_main')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_chat_menu() -> InlineKeyboardMarkup:
    """Create chat mode selection menu"""
    keyboard = [
        [
            InlineKeyboardButton("🤖 Start Chat", callback_data='chat_start'),
            InlineKeyboardButton("🔄 New Conversation", callback_data='chat_new')
        ],
        [
            InlineKeyboardButton("📜 Chat History", callback_data='chat_history'),
            InlineKeyboardButton("⚙️ Chat Settings", callback_data='chat_settings')
        ],
        [
            InlineKeyboardButton("❌ End Chat", callback_data='chat_end'),
            InlineKeyboardButton("⬅️ Back", callback_data='back_main')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Conversation States ---
FEEDBACK_STATE, RATING_STATE = range(2)
CHAT_MODE_STATE = range(1)  # For chat mode tracking

# --- NextEdge Chat Feature ---
async def chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start NextEdge Chat feature"""
    user_id = update.effective_user.id
    
    # Initialize chat mode for user
    context.user_data['chat_mode'] = True
    context.user_data['chat_history'] = []
    
    await update.message.reply_text(
        "💬 *NextEdge Chat Activated!* 💬\n\n"
        "I'm now in conversation mode! You can chat with me naturally.\n\n"
        "*Features:*\n"
        "• Ask any questions freely\n"
        "• I remember our conversation context\n"
        "• Get detailed, conversational responses\n"
        "• Use /endchat to exit chat mode\n"
        "• Use /newchat to start fresh conversation\n\n"
        "*Let's start chatting! What would you like to talk about?* 🗣️",
        parse_mode='Markdown',
        reply_markup=create_chat_menu()
    )
    
    logger.info(f"User {update.effective_user.first_name} started NextEdge Chat")

async def endchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End NextEdge Chat mode"""
    if 'chat_mode' in context.user_data:
        context.user_data['chat_mode'] = False
        context.user_data['chat_history'] = []
        
        await update.message.reply_text(
            "👋 *Chat Mode Ended*\n\n"
            "Thanks for chatting! You can start a new chat anytime with /chat\n\n"
            "Other features are still available:\n"
            "/tip - Get tech tips\n"
            "/code - Browse templates\n"
            "/menu - Main menu",
            parse_mode='Markdown',
            reply_markup=create_main_menu()
        )
    else:
        await update.message.reply_text(
            "You're not in chat mode. Use /chat to start chatting! 💬"
        )

async def newchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new conversation (clear history)"""
    if 'chat_history' in context.user_data:
        context.user_data['chat_history'] = []
        await update.message.reply_text(
            "🔄 *New Conversation Started!*\n\n"
            "I've cleared our chat history. Let's start fresh!\n"
            "What would you like to discuss?",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "Use /chat first to start a conversation! 💬"
        )

async def chat_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check chat mode status"""
    if context.user_data.get('chat_mode', False):
        history_count = len(context.user_data.get('chat_history', [])) // 2
        await update.message.reply_text(
            f"✅ *Chat Mode Active*\n\n"
            f"📝 Messages exchanged: {history_count}\n"
            f"💾 Context memory: {'Enabled' if history_count > 0 else 'Fresh chat'}\n\n"
            f"Commands: /endchat (exit) | /newchat (reset)",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ *Chat Mode Inactive*\n\n"
            "Use /chat to start an interactive conversation with me!",
            parse_mode='Markdown'
        )

# --- Enhanced AI Message Handler with Chat Mode ---
async def gemini_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process user messages - either as chat or general queries"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    if not user_message:
        return
    
    # Rate limiting check
    if not rate_limiter.is_allowed(user_id):
        await update.message.reply_text(
            "⏰ *Rate Limit Exceeded*\n\nPlease wait a moment before sending more messages.",
            parse_mode='Markdown'
        )
        return
    
    # Update user stats
    user_id_str = str(user_id)
    if user_id_str in db.data['users']:
        db.data['users'][user_id_str]['messages_count'] = \
            db.data['users'][user_id_str].get('messages_count', 0) + 1
        db.save()
    db.increment_stat('total_messages')
    
    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )
    
    # Check if user is in chat mode
    is_chat_mode = context.user_data.get('chat_mode', False)
    
    # Build system prompt based on mode
    if is_chat_mode:
        # Get conversation history for context
        chat_history = context.user_data.get('chat_history', [])
        
        # Build conversation context string
        history_context = ""
        if chat_history:
            history_context = "\nPrevious conversation:\n" + "\n".join(chat_history[-10:])  # Last 5 exchanges
        
        system_prompt = f"""You are NextEdge Chat, the conversational AI assistant for {COMPANY_NAME}. 
        You are having a natural conversation with a user.
        
        Characteristics:
        - Be warm, engaging, and conversational
        - Respond naturally like you're chatting with a friend
        - Ask follow-up questions to keep the conversation going
        - Provide detailed, thoughtful responses
        - Show personality while remaining professional
        - Remember context from our conversation
        {history_context}
        
        Current user message: {user_message}
        
        Respond naturally as NextEdge Chat:"""
    else:
        # Regular mode - focused on tech help
        system_prompt = f"""You are NextEdge Bot, the official AI assistant for {COMPANY_NAME}. 
        You specialize in providing high-quality tech tips, code examples, and programming help.

        Guidelines:
        1. Be helpful, concise, and professional
        2. Include code examples when relevant with proper markdown formatting
        3. Focus on practical, actionable advice
        4. Keep responses clear and well-structured
        5. Never provide malicious code or security vulnerabilities

        User question: {user_message}

        Provide a helpful response as NextEdge Bot:"""
    
    try:
        # Get response from Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=system_prompt
        )
        
        if response and response.text:
            ai_reply = response.text
            
            # Store in chat history if in chat mode
            if is_chat_mode:
                if 'chat_history' not in context.user_data:
                    context.user_data['chat_history'] = []
                context.user_data['chat_history'].append(f"User: {user_message[:200]}")
                context.user_data['chat_history'].append(f"Bot: {ai_reply[:200]}")
                # Keep only last 20 messages (10 exchanges)
                if len(context.user_data['chat_history']) > 20:
                    context.user_data['chat_history'] = context.user_data['chat_history'][-20:]
            
            # Handle long responses
            if len(ai_reply) > 4000:
                chunks = [ai_reply[i:i+4000] for i in range(0, len(ai_reply), 4000)]
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        await asyncio.sleep(0.5)
                    await update.message.reply_text(chunk, parse_mode='Markdown')
            else:
                await update.message.reply_text(ai_reply, parse_mode='Markdown')
            
            logger.info(f"Replied to user {update.effective_user.first_name} (Chat mode: {is_chat_mode})")
        else:
            await update.message.reply_text(
                "❌ I couldn't generate a response. Please try rephrasing your question."
            )
            
    except TimedOut:
        await update.message.reply_text(
            "⏰ *Timeout Error*\n\nPlease try again in a moment.",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in gemini_response: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ *Error*\n\nSomething went wrong. Please try again later.",
            parse_mode='Markdown'
        )

# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    user_data = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'username': user.username,
        'language_code': user.language_code,
        'is_premium': user.is_premium if hasattr(user, 'is_premium') else False,
        'joined_date': datetime.now().isoformat(),
        'messages_count': 0,
        'commands_used': 0
    }
    db.add_user(user.id, user_data)
    db.increment_stat('total_commands')
    
    welcome_text = f"""
🚀 *Welcome to {COMPANY_NAME}!* 🚀

*{COMPANY_TAGLINE}*

Hello {user.first_name}! I'm NextEdge Bot, your AI-powered tech assistant.

*What I can help you with:*
💬 *NextEdge Chat* - Natural conversations and Q&A
💻 *Code Solutions* - Python, JavaScript, React, and more
🔧 *Tech Tips* - Daily programming tips
📚 *Code Templates* - Ready-to-use templates
🤖 *AI Assistance* - Powered by Google Gemini

*Quick Commands:*
/start - Show this menu
/menu - Open interactive menu
/chat - Start conversational chat mode
/tip - Get a tech tip
/help - Detailed help
/stats - Your usage stats

*Just type your question or /chat to start a conversation!* 🎯
"""
    
    await update.message.reply_text(
        welcome_text, 
        parse_mode='Markdown',
        reply_markup=create_main_menu()
    )
    logger.info(f"User {user.first_name} ({user.id}) started the bot")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📱 *NextEdge Bot Menu*\n\nChoose an option:",
        parse_mode='Markdown',
        reply_markup=create_main_menu()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = f"""
📖 *NextEdge Bot Help Guide*

*💬 NextEdge Chat Feature:*
/chat - Start conversational AI chat mode
/endchat - Exit chat mode
/newchat - Start fresh conversation
/chatstatus - Check chat mode status

*💬 Natural Language Queries:*
Just type your question! Examples:
• "Write a Python function to sort a list"
• "How do I use async/await in JavaScript?"
• "Show me a React component example"

*🎮 Interactive Commands:*
/tip - Get a random tech tip
/code - Browse code templates
/menu - Open interactive menu
/stats - View your usage statistics
/feedback - Send feedback about the bot
/about - About NextEdge Tech Studio
/contact - Contact information

*📞 Need Professional Services?*
Contact us: {COMPANY_EMAIL}

*Rate Limit:* 15 requests per minute
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def tip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    category = args[0].lower() if args else None
    
    if category and category in TECH_TIPS:
        tip = get_tech_tip(category)
    else:
        tip = get_tech_tip()
    
    await update.message.reply_text(tip, parse_mode='Markdown')
    
    if not category:
        await update.message.reply_text(
            "Want more? Choose a category:",
            reply_markup=create_tips_menu()
        )

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📁 *Code Templates*\n\nChoose a template:",
        parse_mode='Markdown',
        reply_markup=create_templates_menu()
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    user_data = db.data['users'].get(user_id, {})
    
    stats_text = f"""
📊 *Your Statistics*

👤 *User:* {update.effective_user.first_name}
📅 *Joined:* {user_data.get('joined_date', 'Unknown')[:10]}
💬 *Messages:* {user_data.get('messages_count', 0)}
🎮 *Commands:* {user_data.get('commands_used', 0)}

*Global Stats:*
👥 *Total Users:* {len(db.data['users'])}
💬 *Total Messages:* {db.data['stats'].get('total_messages', 0)}

Keep using the bot to unlock more features! 🚀
"""
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⭐ *Share Your Feedback*\n\n"
        "Please rate your experience (1-5):\n"
        "1 - Very Poor | 2 - Poor | 3 - Average | 4 - Good | 5 - Excellent\n\n"
        "Send a number (1-5):",
        parse_mode='Markdown'
    )
    return RATING_STATE

async def feedback_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        rating = int(update.message.text)
        if 1 <= rating <= 5:
            context.user_data['feedback_rating'] = rating
            await update.message.reply_text(
                "Great! Now please share your feedback or suggestions:"
            )
            return FEEDBACK_STATE
        else:
            await update.message.reply_text("Please send a number between 1 and 5.")
            return RATING_STATE
    except ValueError:
        await update.message.reply_text("Please send a valid number (1-5).")
        return RATING_STATE

async def feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rating = context.user_data.get('feedback_rating')
    feedback = update.message.text
    
    db.add_feedback(
        update.effective_user.id,
        update.effective_user.username,
        feedback,
        rating
    )
    
    await update.message.reply_text(
        f"✅ *Thank you for your feedback!*\n\n"
        f"Rating: {'⭐' * rating}\n"
        "We truly appreciate your time!",
        parse_mode='Markdown'
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Feedback cancelled. Use /feedback anytime to share your thoughts!"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    about_text = f"""
🏢 *About {COMPANY_NAME}*

{COMPANY_NAME} is a cutting-edge technology studio delivering innovative software solutions.

*Our Services:*
• 🌐 *Web Development* - React, Vue, Angular, Node.js
• 📱 *Mobile Development* - React Native, Flutter
• 🤖 *AI & ML* - Machine Learning, Computer Vision
• ☁️ *Cloud Solutions* - AWS, GCP, Azure
• 💬 *AI Chat Solutions* - Custom chatbot development

*Contact:*
📧 {COMPANY_EMAIL}
🌐 {COMPANY_WEBSITE}
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact_text = f"""
📞 *Contact {COMPANY_NAME}*

📧 *Email:* {COMPANY_EMAIL}
🌐 *Website:* {COMPANY_WEBSITE}
🐙 *GitHub:* {COMPANY_SOCIAL['github']}

*Business Hours:*
Monday - Friday: 9:00 AM - 6:00 PM (UTC)

*Response Time:* Within 24 hours

*For custom development or AI solutions, reach out to us!*
"""
    keyboard = [[InlineKeyboardButton("Visit Website", url=COMPANY_WEBSITE)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(contact_text, parse_mode='Markdown', reply_markup=reply_markup)

# --- Callback Query Handler ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'menu_tips':
        await query.edit_message_text(
            "💡 *Tech Tips*\n\nChoose a category:",
            parse_mode='Markdown',
            reply_markup=create_tips_menu()
        )
    elif query.data == 'menu_templates':
        await query.edit_message_text(
            "📝 *Code Templates*\n\nChoose a template:",
            parse_mode='Markdown',
            reply_markup=create_templates_menu()
        )
    elif query.data == 'menu_chat':
        await query.edit_message_text(
            "💬 *NextEdge Chat*\n\n"
            "Have natural conversations with our AI assistant!\n\n"
            "*Features:*\n"
            "• Context-aware responses\n"
            "• Natural conversations\n"
            "• Remember chat history\n"
            "• Ask anything!\n\n"
            "Use /chat to start or choose an option:",
            parse_mode='Markdown',
            reply_markup=create_chat_menu()
        )
    elif query.data == 'chat_start':
        # Start chat mode
        context.user_data['chat_mode'] = True
        context.user_data['chat_history'] = []
        await query.edit_message_text(
            "💬 *Chat Mode Activated!*\n\n"
            "I'm ready to chat! Ask me anything or just have a conversation.\n\n"
            "Type /endchat when you want to exit chat mode.",
            parse_mode='Markdown'
        )
    elif query.data == 'chat_new':
        # Clear chat history
        if 'chat_history' in context.user_data:
            context.user_data['chat_history'] = []
        await query.edit_message_text(
            "🔄 *New Conversation Started!*\n\n"
            "I've cleared our chat history. Let's start fresh!",
            parse_mode='Markdown'
        )
    elif query.data == 'chat_history':
        # Show chat history
        history = context.user_data.get('chat_history', [])
        if history:
            history_text = "📜 *Recent Chat History*\n\n"
            for i, msg in enumerate(history[-6:], 1):  # Last 6 messages
                history_text += f"{i}. {msg[:100]}...\n"
            await query.edit_message_text(history_text, parse_mode='Markdown')
        else:
            await query.edit_message_text(
                "No chat history yet. Start a conversation first!",
                parse_mode='Markdown'
            )
    elif query.data == 'chat_settings':
        await query.edit_message_text(
            "⚙️ *Chat Settings*\n\n"
            "• Current mode: Conversational AI\n"
            "• Memory: Context-aware\n"
            "• Response style: Natural\n\n"
            "Use commands to control:\n"
            "/newchat - Reset conversation\n"
            "/endchat - Exit chat mode\n"
            "/chatstatus - Check status",
            parse_mode='Markdown'
        )
    elif query.data == 'chat_end':
        # End chat mode
        context.user_data['chat_mode'] = False
        context.user_data['chat_history'] = []
        await query.edit_message_text(
            "👋 *Chat Mode Ended*\n\n"
            "Thanks for chatting! Use /chat anytime to start again.",
            parse_mode='Markdown'
        )
    elif query.data == 'menu_about':
        await query.edit_message_text(
            f"🏢 *About {COMPANY_NAME}*\n\nUse /about for more details.",
            parse_mode='Markdown'
        )
    elif query.data == 'menu_contact':
        await query.edit_message_text(
            f"📞 *Contact*\n\n📧 {COMPANY_EMAIL}\n🌐 {COMPANY_WEBSITE}\nUse /contact for details",
            parse_mode='Markdown'
        )
    elif query.data == 'menu_feedback':
        await query.edit_message_text(
            "⭐ *Feedback*\n\nUse /feedback command to share your thoughts!\n\nYour feedback helps us improve."
        )
    elif query.data == 'menu_stats':
        await query.edit_message_text(
            "📊 *Statistics*\n\nUse /stats command to view your personal statistics!"
        )
    elif query.data == 'menu_help':
        await query.edit_message_text(
            "📖 *Help*\n\nUse /help command for detailed documentation!\n\n"
            "Quick tips:\n"
            "• Use /chat for conversations\n"
            "• Ask coding questions directly\n"
            "• Use /tip for daily tips\n"
            "• Use /code for templates"
        )
    elif query.data.startswith('tip_'):
        category = query.data.replace('tip_', '')
        if category == 'random':
            tip = get_tech_tip()
        else:
            tip = get_tech_tip(category)
        await query.edit_message_text(tip, parse_mode='Markdown')
        await query.message.reply_text(
            "Want another tip? Choose a category:",
            reply_markup=create_tips_menu()
        )
    elif query.data.startswith('template_'):
        template_key = query.data.replace('template_', '')
        if template_key in CODE_TEMPLATES:
            template = CODE_TEMPLATES[template_key]
            await query.edit_message_text(
                f"📁 *{template['title']}*\n\n{template['code']}",
                parse_mode='Markdown'
            )
    elif query.data == 'back_main':
        await query.edit_message_text(
            "📱 *NextEdge Bot Menu*\n\nChoose an option:",
            parse_mode='Markdown',
            reply_markup=create_main_menu()
        )

# --- Admin Commands ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ADMIN_USER_ID == 0 or update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ Unauthorized access.")
        return
    
    stats = db.data['stats']
    users = db.data['users']
    feedback = db.data['feedback']
    
    stats_text = f"""
📊 *Bot Statistics*

👥 Total Users: {len(users)}
💬 Total Messages: {stats.get('total_messages', 0)}
🎮 Total Commands: {stats.get('total_commands', 0)}
⭐ Total Feedback: {len(feedback)}

📅 Started: {stats.get('start_date', 'Unknown')[:10]}
"""
    await update.message.reply_text(stats_text, parse_mode='Markdown')

# --- Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ *An error occurred*\n\nPlease try again later.",
            parse_mode='Markdown'
        )

# --- Main Function ---
def main() -> None:
    """Start the bot"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found")
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not found in .env file")
        print("Please add your Telegram bot token to the .env file")
        exit(1)
    
    print(f"🤖 Starting {COMPANY_NAME} Bot...")
    print(f"📊 Admin ID: {ADMIN_USER_ID if ADMIN_USER_ID > 0 else 'Not configured'}")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tip", tip_command))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(CommandHandler("admin_stats", admin_stats))
    
    # NextEdge Chat commands
    application.add_handler(CommandHandler("chat", chat_command))
    application.add_handler(CommandHandler("endchat", endchat_command))
    application.add_handler(CommandHandler("newchat", newchat_command))
    application.add_handler(CommandHandler("chatstatus", chat_status_command))
    
    # Feedback conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("feedback", feedback_command)],
        states={
            RATING_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_rating)],
            FEEDBACK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_feedback)],
    )
    application.add_handler(conv_handler)
    
    # Message handler for AI responses
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gemini_response))
    
    # Callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    print(f"✅ {COMPANY_NAME} Bot is running! Press Ctrl+C to stop.")
    print("💬 NextEdge Chat feature is active! Users can use /chat to start conversations.")
    logger.info(f"{COMPANY_NAME} Bot is starting...")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()