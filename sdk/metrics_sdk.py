"""
Metrics SDK for sending data snapshots to the server.
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
import pytz
import requests
from retrying import retry

from . import config

logger = logging.getLogger(__name__)

class MetricsBuffer:
    """Buffer for storing metrics when server is unavailable."""
    
    def __init__(self, buffer_file: Optional[str] = None):
        """
        Initialize the metrics buffer.
        
        Args:
            buffer_file (str, optional): Path to the buffer file. Defaults to config.BUFFER_FILE.
        """
        self.buffer_file = buffer_file or config.BUFFER_FILE
        self.buffer = []
        self.max_size = config.BUFFER_SIZE
        self._load_buffer()
    
    def add(self, metric: Dict[str, Any]) -> None:
        """
        Add a metric to the buffer.
        
        Args:
            metric (dict): The metric to buffer
        """
        if len(self.buffer) >= self.max_size:
            # Remove oldest entry if buffer is full
            self.buffer.pop(0)
        
        self.buffer.append(metric)
        self._save_buffer()
        
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all metrics from the buffer.
        
        Returns:
            list: All buffered metrics
        """
        return self.buffer
    
    def clear(self) -> None:
        """Clear all metrics from the buffer."""
        self.buffer.clear()
        self._save_buffer()
    
    def _save_buffer(self) -> None:
        """Save buffer to disk."""
        try:
            with open(self.buffer_file, 'w') as f:
                json.dump(self.buffer, f)
        except IOError as e:
            logger.error(f"Failed to save buffer: {str(e)}")
    
    def _load_buffer(self) -> None:
        """Load buffer from disk if it exists."""
        if os.path.exists(self.buffer_file):
            try:
                with open(self.buffer_file, 'r') as f:
                    data = json.load(f)
                    self.buffer = data
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load buffer: {str(e)}")
                
    def __len__(self) -> int:
        """
        Get the number of buffered metrics.
        
        Returns:
            int: Number of buffered metrics
        """
        return len(self.buffer)


class MetricsClient:
    """Client for sending metrics to the server."""
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        buffer_file: Optional[str] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[int] = None,
        request_timeout: Optional[int] = None
    ):
        """
        Initialize the metrics client.
        
        Args:
            server_url (str, optional): URL of the metrics server. Defaults to config.SERVER_URL.
            api_key (str, optional): API key for authentication. Defaults to config.API_KEY.
            client_id (str, optional): Client ID. Defaults to config.CLIENT_ID.
            buffer_file (str, optional): Path to the buffer file. Defaults to config.BUFFER_FILE.
            max_retries (int, optional): Maximum number of retries. Defaults to config.MAX_RETRIES.
            retry_delay (int, optional): Delay between retries in seconds. Defaults to config.RETRY_DELAY.
            request_timeout (int, optional): Request timeout in seconds. Defaults to config.REQUEST_TIMEOUT.
        """
        self.server_url = server_url or config.SERVER_URL
        self.api_key = api_key or config.API_KEY
        self.client_id = client_id or config.CLIENT_ID
        self.max_retries = max_retries or config.MAX_RETRIES
        self.retry_delay = retry_delay or config.RETRY_DELAY
        self.request_timeout = request_timeout or config.REQUEST_TIMEOUT
        
        self.buffer = MetricsBuffer(buffer_file)
        
        # Store metric type mappings (name -> id)
        self.metric_types = {}
        self._load_metric_types()
    
    def _retry_if_connection_error(self, exception: Exception) -> bool:
        """
        Return True if we should retry (in this case when it's a connection error).
        
        Args:
            exception (Exception): The exception to check
            
        Returns:
            bool: True if we should retry, False otherwise
        """
        return isinstance(exception, (requests.ConnectionError, requests.Timeout))
    
    def _load_metric_types(self) -> None:
        """Load available metric types from the server."""
        try:
            response = requests.get(
                f"{self.server_url.rstrip('/')}/metric-types/".replace('/metrics/metric-types/', '/metric-types/'),
                headers={'X-API-Key': self.api_key},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            metric_types = response.json()
            
            # Map name to id for easy lookup
            self.metric_types = {mt['name']: mt['id'] for mt in metric_types}
            logger.debug(f"Loaded {len(self.metric_types)} metric types from server")
        except Exception as e:
            logger.warning(f"Failed to load metric types: {str(e)}")
    
    def _ensure_metric_type(self, name: str, description: str = None, unit: str = None) -> int:
        """
        Ensure a metric type exists, creating it if necessary.
        
        Args:
            name (str): Name of the metric type
            description (str, optional): Description of the metric type
            unit (str, optional): Unit of measurement
            
        Returns:
            int: ID of the metric type
        """
        if name in self.metric_types:
            return self.metric_types[name]
        
        # Create new metric type
        try:
            response = requests.post(
                f"{self.server_url.rstrip('/')}/metric-types/".replace('/metrics/metric-types/', '/metric-types/'),
                json={
                    'name': name,
                    'description': description or f"Metric type for {name}",
                    'unit': unit
                },
                headers={'X-API-Key': self.api_key},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            metric_type = response.json()
            self.metric_types[name] = metric_type['id']
            logger.info(f"Created new metric type: {name} (ID: {metric_type['id']})")
            return metric_type['id']
        except Exception as e:
            logger.error(f"Failed to create metric type {name}: {str(e)}")
            raise
    
    def _send_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """
        Send metrics to the server with retry logic.
        
        Args:
            metrics_data (dict): The metrics data to send
        
        Returns:
            bool: True if successful, False otherwise
        """
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }
        
        @retry(
            retry_on_exception=self._retry_if_connection_error,
            stop_max_attempt_number=self.max_retries,
            wait_fixed=self.retry_delay * 1000  # milliseconds
        )
        def _send_request():
            response = requests.post(
                self.server_url,
                json=metrics_data,
                headers=headers,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            return True
        
        try:
            return _send_request()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send metrics after {self.max_retries} retries: {str(e)}")
            return False
    
    def _send_metrics_bulk(self, metrics_list: List[Dict[str, Any]]) -> bool:
        """
        Send multiple metrics to the server in bulk.
        
        Args:
            metrics_list (list): List of metrics to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        bulk_url = f"{self.server_url.rstrip('/')}/bulk"
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }
        
        # Format for bulk endpoint
        bulk_data = {
            'metrics': metrics_list
        }
        
        @retry(
            retry_on_exception=self._retry_if_connection_error,
            stop_max_attempt_number=self.max_retries,
            wait_fixed=self.retry_delay * 1000  # milliseconds
        )
        def _send_bulk_request():
            response = requests.post(
                bulk_url,
                json=bulk_data,
                headers=headers,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            return True
        
        try:
            return _send_bulk_request()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send bulk metrics after {self.max_retries} retries: {str(e)}")
            return False
    
    def send_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """
        Send metrics to the server. If sending fails, add to buffer.
        
        Args:
            metrics_data (dict): The metrics data to send in format:
                {
                    'name': 'metric_name',
                    'value': 123.45,
                    'unit': '%',
                    'timestamp': '2023-01-01T12:00:00Z' (optional)
                }
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Try to send any buffered metrics first
        if len(self.buffer) > 0:
            buffered_metrics = self.buffer.get_all()
            if self._send_metrics_bulk(buffered_metrics):
                self.buffer.clear()
                logger.info(f"Successfully sent {len(buffered_metrics)} buffered metrics")
        
        # Format for web app compatibility
        metric_name = metrics_data.get('name')
        if not metric_name:
            logger.error("Metric name is required")
            return False
        
        try:
            # Ensure metric type exists
            metric_type_id = self._ensure_metric_type(
                metric_name, 
                description=metrics_data.get('description'),
                unit=metrics_data.get('unit')
            )
            
            # Format for web app
            formatted_metric = {
                'metric_type_id': metric_type_id,
                'value': metrics_data.get('value'),
                'recorded_at': metrics_data.get('timestamp') or datetime.now(pytz.UTC).isoformat(),
                'source': metrics_data.get('source') or self.client_id,
                'metric_metadata': metrics_data.get('metadata', {})
            }
            
            # Send current metrics
            if self._send_metrics(formatted_metric):
                logger.info(f"Successfully sent metric: {metric_name}")
                return True
            else:
                self.buffer.add(formatted_metric)
                logger.warning(f"Failed to send metric: {metric_name}, added to buffer")
                return False
                
        except Exception as e:
            logger.error(f"Error sending metric {metric_name}: {str(e)}")
            return False
    
    def create_metrics_batch(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a metrics batch with timestamp.
        
        Args:
            metrics (dict): The metrics to include in the batch
        
        Returns:
            dict: The metrics batch
        """
        return {
            'name': metrics.get('name', 'unknown'),
            'value': metrics.get('value', 0),
            'unit': metrics.get('unit'),
            'timestamp': datetime.now(pytz.UTC).isoformat(),
            'source': metrics.get('source', self.client_id),
            'metadata': metrics.get('metadata', {})
        }
    
    def health_check(self) -> bool:
        """
        Check if the metrics server is accessible.
        
        Returns:
            bool: True if server is accessible, False otherwise
        """
        try:
            # Try to get metric types as a health check
            response = requests.get(
                f"{self.server_url.rstrip('/')}/metric-types/".replace('/metrics/metric-types/', '/metric-types/'),
                headers={'X-API-Key': self.api_key},
                timeout=self.request_timeout
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_buffered_count(self) -> int:
        """
        Get the number of buffered metrics.
        
        Returns:
            int: Number of buffered metrics
        """
        return len(self.buffer)


# Singleton instance for easy import
default_client = MetricsClient()


def send_metrics(metrics_data: Dict[str, Any]) -> bool:
    """
    Send metrics to the server using the default client.
    
    Args:
        metrics_data (dict): The metrics data to send
    
    Returns:
        bool: True if successful, False otherwise
    """
    return default_client.send_metrics(metrics_data)


def create_metrics_batch(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a metrics batch with timestamp using the default client.
    
    Args:
        metrics (dict): The metrics to include in the batch
    
    Returns:
        dict: The metrics batch
    """
    return default_client.create_metrics_batch(metrics)


def health_check() -> bool:
    """
    Check if the metrics server is accessible using the default client.
    
    Returns:
        bool: True if server is accessible, False otherwise
    """
    return default_client.health_check()


def get_buffered_count() -> int:
    """
    Get the number of buffered metrics using the default client.
    
    Returns:
        int: Number of buffered metrics
    """
    return default_client.get_buffered_count()
