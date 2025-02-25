"""
Configuration settings for the metrics client.
"""
import os

# Server configuration
SERVER_URL = os.getenv('METRICS_SERVER_URL', 'https://your-metrics-server.com/api/metrics')
API_KEY = os.getenv('METRICS_API_KEY', '')

# Client configuration
CLIENT_ID = os.getenv('METRICS_CLIENT_ID', 'default-client')
COLLECTION_INTERVAL = int(os.getenv('METRICS_COLLECTION_INTERVAL', '30'))  # seconds

# HTTP client configuration
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Buffer configuration
BUFFER_SIZE = 1000  # maximum number of metrics to store
BUFFER_FILE = 'metrics_buffer.json'  # temporary storage for failed transmissions

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
