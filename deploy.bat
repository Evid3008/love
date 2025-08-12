@echo off
setlocal enabledelayedexpansion

echo 🚀 Netflix Cookie Bot Deployment Script for Windows
echo.

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="local" goto local
if "%1"=="docker" goto docker
if "%1"=="railway" goto railway
if "%1"=="render" goto render
if "%1"=="heroku" goto heroku
goto help

:local
echo 📦 Setting up local environment...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed. Please install Python 3.8+ first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python found
python --version

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📦 Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt

REM Install Playwright browsers
echo 🌐 Installing Playwright browsers...
playwright install chromium --with-deps

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo 📝 Creating .env file...
    copy env.example .env
    echo ⚠️  Please edit .env file and add your BOT_TOKEN
    notepad .env
)

echo ✅ Local environment setup complete!
echo 🎬 To start the bot, run: python bot.py
pause
goto end

:docker
echo 🐳 Deploying with Docker...
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    echo Download from: https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

echo ✅ Docker found
docker --version

REM Check if .env exists
if not exist ".env" (
    echo ❌ .env file not found. Please create it with your BOT_TOKEN
    echo Copy env.example to .env and add your bot token
    pause
    exit /b 1
)

REM Build Docker image
echo 🔨 Building Docker image...
docker build -t netflix-cookie-bot .

REM Run container
echo 🚀 Starting Docker container...
docker run -d --name netflix-cookie-bot --restart unless-stopped --env-file .env -p 8080:8080 netflix-cookie-bot

echo ✅ Docker deployment complete!
echo 📊 Check logs with: docker logs netflix-cookie-bot
pause
goto end

:railway
echo 🚂 Deploying to Railway...
echo.

REM Check if Railway CLI is installed
railway --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Railway CLI is not installed. Please install it first:
    echo npm install -g @railway/cli
    pause
    exit /b 1
)

echo ✅ Railway CLI found
railway --version

REM Deploy
echo 🚀 Deploying to Railway...
railway up

echo ✅ Railway deployment complete!
pause
goto end

:render
echo 🌐 Render Deployment Instructions
echo.
echo Please deploy manually to Render:
echo 1. Go to https://render.com
echo 2. Click "New" → "Web Service"
echo 3. Connect your GitHub repository
echo 4. Configure with render.yaml settings
echo 5. Add BOT_TOKEN environment variable
echo 6. Deploy!
echo.
pause
goto end

:heroku
echo 🏗️  Deploying to Heroku...
echo.

REM Check if Heroku CLI is installed
heroku --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Heroku CLI is not installed. Please install it first:
    echo Download from: https://devcenter.heroku.com/articles/heroku-cli
    pause
    exit /b 1
)

echo ✅ Heroku CLI found
heroku --version

REM Check if logged in
heroku auth:whoami >nul 2>&1
if errorlevel 1 (
    echo 🔐 Please login to Heroku...
    heroku login
)

REM Create app if it doesn't exist
heroku apps:info >nul 2>&1
if errorlevel 1 (
    echo 🏗️  Creating Heroku app...
    heroku create
)

REM Set environment variables
if exist ".env" (
    echo 🔧 Setting environment variables...
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" (
            heroku config:set %%a=%%b
        )
    )
) else (
    echo ⚠️  No .env file found. Please set BOT_TOKEN manually:
    echo heroku config:set BOT_TOKEN=your_bot_token
)

REM Deploy
echo 🚀 Deploying to Heroku...
git add .
git commit -m "Deploy to Heroku" 2>nul || echo No changes to commit
git push heroku main

echo ✅ Heroku deployment complete!
pause
goto end

:help
echo Netflix Cookie Bot Deployment Script for Windows
echo.
echo Usage: %0 [OPTION]
echo.
echo Options:
echo   local              Setup local development environment
echo   docker             Deploy with Docker
echo   railway            Deploy to Railway
echo   render             Show Render deployment instructions
echo   heroku             Deploy to Heroku
echo   help               Show this help message
echo.
echo Examples:
echo   %0 local           # Setup local environment
echo   %0 docker          # Deploy with Docker
echo   %0 railway         # Deploy to Railway
echo.
pause
goto end

:end
endlocal
