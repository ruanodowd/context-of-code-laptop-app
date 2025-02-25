"""
HTTP client for sending metrics to the server.
"""
import json
import logging
from datetime import datetime
import pytz
import requests
from retrying import retry
from . import config

logger = logging.getLogger(__name__)

def retry_if_connection_error(exception):
    """Return True if we should retry (in this case when it's a connection error)"""
    return isinstance(exception, (requests.ConnectionError, requests.Timeout))

@retry(retry_on_exception=retry_if_connection_error,
       stop_max_attempt_number=config.MAX_RETRIES,
       wait_fixed=config.RETRY_DELAY * 1000)  # milliseconds
def send_metrics(metrics_data):
    """
    Send metrics to the server with retry logic.
    
    Args:
        metrics_data (dict): The metrics data to send
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Add server-side reception timestamp
    metrics_data['received_at'] = datetime.now(pytz.UTC).isoformat()
    
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': config.API_KEY,
        'X-Client-ID': config.CLIENT_ID
    }
    
    try:
        response = requests.post(
            config.SERVER_URL,
            json=metrics_data,
            headers=headers,
            timeout=config.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send metrics: {str(e)}")
        raise  # Let the retry decorator handle it
    
def health_check():
    """
    Check if the metrics server is accessible.
    
    Returns:
        bool: True if server is accessible, False otherwise
    """
    try:
        response = requests.get(
            f"{config.SERVER_URL}/health",
            timeout=config.REQUEST_TIMEOUT
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False
