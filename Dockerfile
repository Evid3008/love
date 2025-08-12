# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    procps \
    libxss1 \
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatspi2.0-0 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers in a shared location
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache/ms-playwright
RUN playwright install chromium --with-deps

# Diagnostic: Check what was installed
RUN echo "=== After playwright install ===" && \
    ls -la /app/.cache/ms-playwright/ && \
    find /app/.cache/ms-playwright -name "chrome" -type f -exec ls -la {} \; && \
    echo "=== Environment variable ===" && \
    echo "PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app

# Ensure botuser can access the browser cache
RUN chown -R botuser:botuser /app/.cache

# Diagnostic: Check permissions after chown
RUN echo "=== After chown ===" && \
    ls -la /app/.cache/ms-playwright/ && \
    find /app/.cache/ms-playwright -name "chrome" -type f -exec ls -la {} \; && \
    echo "=== botuser can access ===" && \
    su botuser -c "ls -la /app/.cache/ms-playwright/" || echo "botuser cannot access"

# Switch to non-root user
USER botuser

# Diagnostic: Check as botuser
RUN echo "=== As botuser ===" && \
    ls -la /app/.cache/ms-playwright/ && \
    find /app/.cache/ms-playwright -name "chrome" -type f -exec ls -la {} \; && \
    echo "=== Environment variable as botuser ===" && \
    echo "PLAYWRIGHT_BROWSERS_PATH=$PLAYWRIGHT_BROWSERS_PATH"

# Verify browser installation and install if needed
RUN python verify_browser.py || python install_browser.py

# Diagnostic: Final check
RUN echo "=== Final check ===" && \
    ls -la /app/.cache/ms-playwright/ && \
    find /app/.cache/ms-playwright -name "chrome" -type f -exec ls -la {} \;

# Expose port (if needed for webhooks)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('https://api.telegram.org/bot${BOT_TOKEN}/getMe')" || exit 1

# Start the bot
CMD ["python", "bot.py"]
