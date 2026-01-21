# GitHub Account Generator Docker Image
# Uses Python 3.11 with Tor network support and Playwright browser automation

FROM python:3.11-slim

# Install system dependencies: Tor, netcat, and Playwright browser dependencies
RUN apt-get update && \
    apt-get install -y \
    tor \
    netcat-openbsd \
    wget \
    gnupg \
    # Playwright browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libxkbcommon0 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Configure pip with longer timeout and retries
ENV PIP_DEFAULT_TIMEOUT=100
ENV PIP_RETRIES=5

RUN pip install --no-cache-dir -r requirements.txt

# Install playwright-helper from private GitHub repo
ARG GITHUB_TOKEN
RUN pip install git+https://${GITHUB_TOKEN}@github.com/za-zo/python-package--playwright-helper.git

# Install Playwright browsers
RUN playwright install chrome

# Configure Tor
COPY torrc /etc/tor/torrc
RUN mkdir -p /var/lib/tor && \
    chown -R debian-tor:debian-tor /var/lib/tor && \
    chmod 700 /var/lib/tor

# Copy application files
COPY config.py .
COPY database.py .
COPY github_generator.py .
COPY github_username_manager.py .
COPY ip_manager.py .
COPY utils.py .
COPY TempMailServices/ ./TempMailServices/

# Copy startup script
COPY start.sh .
RUN chmod +x start.sh

# Default environment variables
ENV TOR_PORT=9150
ENV TOR_CONTROL_PORT=9151
ENV HEADLESS=true
ENV USE_TOR_IN_BROWSER=true
ENV USE_TOR_IN_MAILSERVICE=true

# Use start.sh as the entry point
CMD ["./start.sh"]
