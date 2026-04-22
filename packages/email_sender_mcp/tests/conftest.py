"""Unit tests configuration — force test env vars before nx-loaded .env values take effect."""

import os

# Force test values regardless of what nx loaded from root .env
os.environ["SES_SENDER_EMAIL"] = "sender@example.com"
