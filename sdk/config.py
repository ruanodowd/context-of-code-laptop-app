"""
Configuration settings for the Metrics SDK.
"""
import os
import socket

# Server configuration
SERVER_URL = os.getenv('METRICS_SERVER_URL', 'http://localhost:8000/')
API_KEY = os.getenv('METRICS_API_KEY', 'metrics-api-key-2025')

# Source configuration (replaces CLIENT_ID)
SOURCE_NAME = os.getenv('METRICS_SOURCE_NAME', socket.gethostname())
SOURCE_DESCRIPTION = os.getenv('METRICS_SOURCE_DESCRIPTION', f'Metrics from {socket.gethostname()}')
SOURCE_IP = os.getenv('METRICS_SOURCE_IP', None)  # Will be detected automatically by the server if not provided

# HTTP client configuration
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Buffer configuration
BUFFER_SIZE = 1000  # maximum number of metrics to store
BUFFER_FILE = os.getenv('METRICS_BUFFER_FILE', 'metrics_buffer.json')  # temporary storage for failed transmissions

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
