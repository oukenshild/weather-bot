#!/bin/bash
# Startup script for Telegram Weather Bot
# This script ensures the bot runs continuously

cd "$(dirname "$0")"

# Create logs directory if it doesn't exist
mkdir -p logs

# Load environment variables from .env if it exists
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Run the bot
exec python3 main.py
