#!/bin/bash

# Netflix Cookie Bot Deployment Script
# This script helps deploy the bot to various platforms

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if file exists
file_exists() {
    [ -f "$1" ]
}

# Function to check if directory exists
dir_exists() {
    [ -d "$1" ]
}

# Function to validate bot token
validate_token() {
    local token="$1"
    if [[ ! "$token" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]]; then
        print_error "Invalid bot token format. Expected: <digits>:<token>"
        return 1
    fi
    return 0
}

# Function to setup local environment
setup_local() {
    print_status "Setting up local environment..."
    
    # Check if Python is installed
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.8+ first."
        exit 1
    fi
    
    # Check Python version
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    print_status "Python version: $python_version"
    
    # Create virtual environment if it doesn't exist
    if ! dir_exists "venv"; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    print_status "Activating virtual environment..."
    source venv/bin/activate
    
    # Install dependencies
    print_status "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # Install Playwright browsers
    print_status "Installing Playwright browsers..."
    playwright install chromium --with-deps
    
    # Create .env file if it doesn't exist
    if ! file_exists ".env"; then
        print_status "Creating .env file..."
        cp env.example .env
        print_warning "Please edit .env file and add your BOT_TOKEN"
    fi
    
    print_success "Local environment setup complete!"
}

# Function to deploy to Railway
deploy_railway() {
    print_status "Deploying to Railway..."
    
    if ! command_exists railway; then
        print_error "Railway CLI is not installed. Please install it first:"
        echo "npm install -g @railway/cli"
        exit 1
    fi
    
    # Check if logged in
    if ! railway whoami >/dev/null 2>&1; then
        print_status "Please login to Railway..."
        railway login
    fi
    
    # Deploy
    railway up
    
    print_success "Railway deployment complete!"
}

# Function to deploy to Render
deploy_render() {
    print_status "Deploying to Render..."
    
    if ! file_exists "render.yaml"; then
        print_error "render.yaml not found. Please create it first."
        exit 1
    fi
    
    print_warning "Please deploy manually to Render:"
    echo "1. Go to https://render.com"
    echo "2. Click 'New' → 'Web Service'"
    echo "3. Connect your GitHub repository"
    echo "4. Configure with render.yaml settings"
    echo "5. Add BOT_TOKEN environment variable"
    echo "6. Deploy!"
}

# Function to deploy to Heroku
deploy_heroku() {
    print_status "Deploying to Heroku..."
    
    if ! command_exists heroku; then
        print_error "Heroku CLI is not installed. Please install it first:"
        echo "https://devcenter.heroku.com/articles/heroku-cli"
        exit 1
    fi
    
    # Check if logged in
    if ! heroku auth:whoami >/dev/null 2>&1; then
        print_status "Please login to Heroku..."
        heroku login
    fi
    
    # Create app if it doesn't exist
    if ! heroku apps:info >/dev/null 2>&1; then
        print_status "Creating Heroku app..."
        heroku create
    fi
    
    # Set environment variables
    if file_exists ".env"; then
        print_status "Setting environment variables..."
        export $(cat .env | xargs)
        heroku config:set BOT_TOKEN="$BOT_TOKEN"
    else
        print_warning "No .env file found. Please set BOT_TOKEN manually:"
        echo "heroku config:set BOT_TOKEN=your_bot_token"
    fi
    
    # Deploy
    git add .
    git commit -m "Deploy to Heroku" || true
    git push heroku main
    
    print_success "Heroku deployment complete!"
}

# Function to deploy with Docker
deploy_docker() {
    print_status "Deploying with Docker..."
    
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if .env exists
    if ! file_exists ".env"; then
        print_error ".env file not found. Please create it with your BOT_TOKEN"
        exit 1
    fi
    
    # Build Docker image
    print_status "Building Docker image..."
    docker build -t netflix-cookie-bot .
    
    # Run container
    print_status "Starting Docker container..."
    docker run -d \
        --name netflix-cookie-bot \
        --restart unless-stopped \
        --env-file .env \
        -p 8080:8080 \
        netflix-cookie-bot
    
    print_success "Docker deployment complete!"
    print_status "Container is running. Check logs with: docker logs netflix-cookie-bot"
}

# Function to deploy with Docker Compose
deploy_docker_compose() {
    print_status "Deploying with Docker Compose..."
    
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install it first."
        exit 1
    fi
    
    # Check if .env exists
    if ! file_exists ".env"; then
        print_error ".env file not found. Please create it with your BOT_TOKEN"
        exit 1
    fi
    
    # Start services
    docker-compose up -d
    
    print_success "Docker Compose deployment complete!"
    print_status "Services are running. Check logs with: docker-compose logs -f"
}

# Function to deploy to VPS
deploy_vps() {
    print_status "Setting up VPS deployment..."
    
    print_warning "Please follow these steps to deploy on your VPS:"
    echo ""
    echo "1. SSH into your VPS:"
    echo "   ssh user@your-server-ip"
    echo ""
    echo "2. Clone the repository:"
    echo "   git clone https://github.com/yourusername/NF-Filter.git"
    echo "   cd NF-Filter"
    echo ""
    echo "3. Run the setup script:"
    echo "   chmod +x deploy.sh"
    echo "   ./deploy.sh local"
    echo ""
    echo "4. Create systemd service:"
    echo "   sudo nano /etc/systemd/system/netflix-bot.service"
    echo ""
    echo "5. Add this content to the service file:"
    echo "   [Unit]"
    echo "   Description=Netflix Cookie Bot"
    echo "   After=network.target"
    echo ""
    echo "   [Service]"
    echo "   Type=simple"
    echo "   User=your-username"
    echo "   WorkingDirectory=/path/to/NF-Filter"
    echo "   Environment=BOT_TOKEN=your_bot_token"
    echo "   ExecStart=/usr/bin/python3 bot.py"
    echo "   Restart=always"
    echo "   RestartSec=10"
    echo ""
    echo "   [Install]"
    echo "   WantedBy=multi-user.target"
    echo ""
    echo "6. Start the service:"
    echo "   sudo systemctl daemon-reload"
    echo "   sudo systemctl enable netflix-bot"
    echo "   sudo systemctl start netflix-bot"
    echo ""
    echo "7. Check status:"
    echo "   sudo systemctl status netflix-bot"
}

# Function to show help
show_help() {
    echo "Netflix Cookie Bot Deployment Script"
    echo ""
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  local              Setup local development environment"
    echo "  railway            Deploy to Railway"
    echo "  render             Show Render deployment instructions"
    echo "  heroku             Deploy to Heroku"
    echo "  docker             Deploy with Docker"
    echo "  compose            Deploy with Docker Compose"
    echo "  vps                Show VPS deployment instructions"
    echo "  help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 local           # Setup local environment"
    echo "  $0 railway         # Deploy to Railway"
    echo "  $0 docker          # Deploy with Docker"
    echo ""
}

# Main script logic
case "${1:-help}" in
    "local")
        setup_local
        ;;
    "railway")
        deploy_railway
        ;;
    "render")
        deploy_render
        ;;
    "heroku")
        deploy_heroku
        ;;
    "docker")
        deploy_docker
        ;;
    "compose")
        deploy_docker_compose
        ;;
    "vps")
        deploy_vps
        ;;
    "help"|*)
        show_help
        ;;
esac
