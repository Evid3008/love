# 🎬 Netflix Cookie Bot - Unlimited Edition

A powerful Telegram bot for processing Netflix cookies and extracting account details with unlimited access.

## ✨ Features

- 🔄 **Auto-Process** - Instant cookie validation & details extraction
- 📁 **Multi-Format** - ZIP, TXT, JSON, Netscape formats supported  
- 🌍 **Auto-English** - Automatically changes account language to English
- 📊 **Complete Info** - Email, phone, plan, payment, viewing history
- 🚀 **No Limits** - Unlimited processing, no restrictions
- ⚡ **Fast Results** - Enhanced scraper with detailed account info

## 🚀 Quick Deploy

### Railway (Recommended)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/new?template=https://github.com/yourusername/NF-Filter)

### Render
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Heroku
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### Koyeb
[![Deploy to Koyeb](https://www.koyeb.com/static/images/deploy/button.svg)](https://app.koyeb.com/deploy?type=git&repository=github.com/Evid3008/love&branch=main&name=netflix-cookie-bot)

## 📋 Prerequisites

- Python 3.8+
- Telegram Bot Token (Get from [@BotFather](https://t.me/BotFather))
- Git

## 🔧 Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/NF-Filter.git
   cd NF-Filter
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Set up environment variables**
   ```bash
   # Create .env file
   echo "BOT_TOKEN=your_telegram_bot_token_here" > .env
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

## 🌐 Deployment Options

### Railway Deployment

1. Fork this repository
2. Go to [Railway](https://railway.app)
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your forked repository
5. Add environment variable: `BOT_TOKEN=your_bot_token`
6. Deploy!

### Render Deployment

1. Fork this repository
2. Go to [Render](https://render.com)
3. Click "New" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: netflix-cookie-bot
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt && playwright install chromium`
   - **Start Command**: `python bot.py`
6. Add environment variable: `BOT_TOKEN=your_bot_token`
7. Deploy!

### Heroku Deployment

1. Fork this repository
2. Go to [Heroku](https://heroku.com)
3. Create new app
4. Connect GitHub repository
5. Add environment variable: `BOT_TOKEN=your_bot_token`
6. Deploy!

### Koyeb Deployment

1. Fork this repository
2. Go to [Koyeb](https://app.koyeb.com)
3. Click "Create App" → "Deploy from GitHub"
4. Select your forked repository
5. Configure:
   - **Name**: netflix-cookie-bot
   - **Environment**: Docker
   - **Port**: 8080
6. Add environment variable: `BOT_TOKEN=your_bot_token`
7. Deploy!

### Docker Deployment

1. **Build and run locally**
   ```bash
   docker build -t netflix-cookie-bot .
   docker run -e BOT_TOKEN=your_bot_token netflix-cookie-bot
   ```

2. **Docker Compose**
   ```bash
   docker-compose up -d
   ```

### VPS/Server Deployment

1. **SSH into your server**
   ```bash
   ssh user@your-server-ip
   ```

2. **Clone and setup**
   ```bash
   git clone https://github.com/yourusername/NF-Filter.git
   cd NF-Filter
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Create systemd service**
   ```bash
   sudo nano /etc/systemd/system/netflix-bot.service
   ```

   Add this content:
   ```ini
   [Unit]
   Description=Netflix Cookie Bot
   After=network.target

   [Service]
   Type=simple
   User=your-username
   WorkingDirectory=/path/to/NF-Filter
   Environment=BOT_TOKEN=your_bot_token
   ExecStart=/usr/bin/python3 bot.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

4. **Start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable netflix-bot
   sudo systemctl start netflix-bot
   ```

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BOT_TOKEN` | Your Telegram bot token | ✅ Yes |
| `TELEGRAM_BOT_TOKEN` | Alternative name for bot token | ❌ No |
| `TOKEN` | Alternative name for bot token | ❌ No |

## 📁 Project Structure

```
NF-Filter/
├── bot.py              # Main bot file
├── config.py           # Configuration management
├── scraper.py          # Netflix scraping logic
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose setup
├── .env.example        # Environment variables example
├── .gitignore          # Git ignore rules
├── Procfile            # Heroku deployment
├── runtime.txt         # Python version for Heroku
├── nginx.conf          # Nginx configuration
├── start.sh            # Startup script
└── README.md           # This file
```

## 🤖 Bot Usage

1. **Start the bot**: Send `/start` to get welcome message
2. **Send cookies**: Upload ZIP/TXT files or paste cookie text
3. **Get results**: Receive detailed account information instantly

### Supported Formats:
- ZIP files containing cookie files
- TXT files with cookie data
- Direct cookie text/JSON
- Netscape format cookies

## 🔧 Configuration

### Customizing the Bot

Edit `config.py` to modify:
- Token validation rules
- Environment variable names
- Default settings

### Advanced Settings

In `bot.py`, you can modify:
- `BATCH_SIZE`: Number of cookies processed per batch
- `MAX_INVALID_TRIES`: Retry attempts for invalid cookies
- Timeout settings
- Logging levels

## 🛠️ Troubleshooting

### Common Issues

1. **Bot not responding**
   - Check if `BOT_TOKEN` is set correctly
   - Verify bot is not blocked by users
   - Check server logs for errors

2. **Playwright installation issues**
   ```bash
   # Reinstall Playwright
   pip uninstall playwright
   pip install playwright
   playwright install chromium
   ```

3. **Playwright browser not found error**
   ```bash
   # Run the fix script
   chmod +x fix_playwright.sh
   ./fix_playwright.sh
   
   # Or manually fix:
   rm -rf ~/.cache/ms-playwright
   playwright install chromium --with-deps
   ```

3. **Memory issues on small servers**
   - Reduce `BATCH_SIZE` in bot.py
   - Use headless mode (already enabled)
   - Monitor memory usage

4. **Docker issues**
   ```bash
   # Rebuild Docker image
   docker build --no-cache -t netflix-cookie-bot .
   ```

### Logs

Check logs for debugging:
```bash
# Systemd service logs
sudo journalctl -u netflix-bot -f

# Docker logs
docker logs netflix-cookie-bot

# Direct Python logs
python bot.py 2>&1 | tee bot.log
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This bot is for educational purposes only. Users are responsible for complying with Netflix's Terms of Service and applicable laws.

## 📞 Support

- Create an [Issue](https://github.com/yourusername/NF-Filter/issues)
- Contact: [@your_telegram](https://t.me/your_telegram)

---

**Made with ❤️ by Evid**
