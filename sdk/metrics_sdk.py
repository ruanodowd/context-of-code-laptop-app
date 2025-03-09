"""
Metrics SDK for sending data snapshots to the server.

This SDK is compatible with the following data model:
- MetricType: Defines types of metrics (e.g., 'cpu_usage', 'memory_usage')
- Source: Defines sources from which metrics are collected (e.g., 'server1', 'laptop1')
- Metric: Stores actual metric measurements with values and timestamps
- MetricMetadata: Stores additional metadata associated with metrics
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import UUID
import pytz
import requests
from retrying import retry
from dataclasses import dataclass

from . import config

logger = logging.getLogger(__name__)


@dataclass
class Unit:
    """Represents a measurement unit."""
    id: UUID
    name: str
    symbol: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None


class UnitManager:
    """Manager for handling unit operations."""
    
    def __init__(self, client: Optional['MetricsClient'] = None):
        """Initialize the unit manager.
        
        Args:
            client (MetricsClient, optional): The metrics client to use
        """
        self.client = client
        
    def register_unit(self, name: str, symbol: str, description: Optional[str] = None) -> Unit:
        """Register a new unit if it doesn't exist.
        Returns existing unit if name or symbol already registered.
        
        Args:
            name (str): Name of the unit
            symbol (str): Symbol for the unit
            description (str, optional): Description of the unit
            
        Returns:
            Unit: The created or existing unit
            
        Raises:
            ValueError: If name or symbol is invalid
            requests.RequestException: If server request fails
        """
        if not name or not symbol:
            raise ValueError("Name and symbol are required")
        
        # First try to find by symbol
        try:
            return self.get_unit_by_symbol(symbol)
        except requests.RequestException:
            # If not found, create new unit with UnitCreate schema
            try:
                response = self.client._make_request(
                    'post',
                    '',  # Base units endpoint
                    is_units_endpoint=True,
                    json={
                        'name': name,
                        'symbol': symbol,
                        'description': description
                    }
                )
                
                return Unit(**response)
            except requests.exceptions.RequestException as e:
                logger.error(f"Error creating unit with symbol '{symbol}': {str(e)}")
                # If we can't register, create a temporary unit object
                return Unit(
                    id=uuid.uuid4(),
                    name=name,
                    symbol=symbol,
                    description=description,
                    created_at=datetime.now(pytz.UTC)
                )
    
    # Alias for backward compatibility
    create_unit = register_unit
    
    def get_unit(self, unit_id: UUID) -> Unit:
        """Get a unit by ID.
        
        Args:
            unit_id (UUID): ID of the unit
            
        Returns:
            Unit: The requested unit
            
        Raises:
            requests.RequestException: If server request fails
        """
        response = self.client._make_request('get', str(unit_id), is_units_endpoint=True)
        return Unit(**response)
    
    def get_unit_by_symbol(self, symbol: str) -> Unit:
        """Get a unit by its symbol.
        
        Args:
            symbol (str): Symbol of the unit
            
        Returns:
            Unit: The requested unit
            
        Raises:
            requests.RequestException: If server request fails
        """
        # The API doesn't have a direct endpoint to get units by symbol
        # Instead, we'll get all units and filter by symbol
        try:
            units = self.list_units()
            for unit in units:
                if unit.symbol == symbol:
                    return unit
            
            # If we didn't find a matching unit, raise an exception
            raise requests.RequestException(f"Unit with symbol '{symbol}' not found")
        except requests.RequestException as e:
            logger.error(f"Error finding unit with symbol '{symbol}': {str(e)}")
            raise
    
    def list_units(self) -> List[Unit]:
        """List all available units.
        
        Returns:
            List[Unit]: List of all units
            
        Raises:
            requests.RequestException: If server request fails
        """
        response = self.client._make_request('get', '', is_units_endpoint=True)
        return [Unit(**unit_data) for unit_data in response]
    
    def update_unit(self, unit_id: UUID, **kwargs) -> Unit:
        """Update a unit's properties.
        
        Args:
            unit_id (UUID): ID of the unit to update
            **kwargs: Properties to update (name, symbol, description)
            
        Returns:
            Unit: The updated unit
            
        Raises:
            ValueError: If no valid properties are provided
            requests.RequestException: If server request fails
        """
        valid_fields = {'name', 'symbol', 'description'}
        update_data = {k: v for k, v in kwargs.items() if k in valid_fields}
        
        if not update_data:
            raise ValueError("No valid properties provided for update")
            
        response = self.client._make_request(
            'patch',
            str(unit_id),
            is_units_endpoint=True,
            json=update_data
        )
        
        return Unit(**response)
    
    def delete_unit(self, unit_id: UUID) -> bool:
        """Delete a unit if it's not referenced by any metric types.
        
        Args:
            unit_id (UUID): ID of the unit to delete
            
        Returns:
            bool: True if deleted successfully
            
        Raises:
            requests.RequestException: If server request fails or unit is in use
        """
        try:
            self.client._make_request('delete', str(unit_id), is_units_endpoint=True)
            return True
        except requests.RequestException as e:
            if e.response and e.response.status_code == 409:
                raise ValueError("Cannot delete unit: it is referenced by existing metric types")
            raise

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
        source_name: Optional[str] = None,
        source_description: Optional[str] = None,
        source_ip: Optional[str] = None,
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
            source_name (str, optional): Source name for metrics. Defaults to config.SOURCE_NAME.
            source_description (str, optional): Description of the source. Defaults to config.SOURCE_DESCRIPTION.
            source_ip (str, optional): IP address of the source. Defaults to config.SOURCE_IP.
            buffer_file (str, optional): Path to the buffer file. Defaults to config.BUFFER_FILE.
            max_retries (int, optional): Maximum number of retries. Defaults to config.MAX_RETRIES.
            retry_delay (int, optional): Delay between retries in seconds. Defaults to config.RETRY_DELAY.
            request_timeout (int, optional): Request timeout in seconds. Defaults to config.REQUEST_TIMEOUT.
        """
        self.server_url = server_url or config.SERVER_URL
        self.api_key = api_key or config.API_KEY
        self.source_name = source_name or config.SOURCE_NAME
        self.source_description = source_description or config.SOURCE_DESCRIPTION
        self.source_ip = source_ip or config.SOURCE_IP
        self.max_retries = max_retries or config.MAX_RETRIES
        self.retry_delay = retry_delay or config.RETRY_DELAY
        self.request_timeout = request_timeout or config.REQUEST_TIMEOUT
        
        self.buffer = MetricsBuffer(buffer_file)
        
        # Store metric type mappings (name -> id)
        self.metric_types = {}
        # Store source id
        self.source_id = None
        # Initialize unit manager
        self.unit_manager = UnitManager(self)
        
        # Load metric types and ensure source exists
        self._load_metric_types()
        self._ensure_source()
    
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
            response = self._make_request('get', '', is_metric_types_endpoint=True)
            
            # Map name to id for easy lookup
            self.metric_types = {mt['name']: mt['id'] for mt in response if mt.get('is_active', True)}
            logger.debug(f"Loaded {len(self.metric_types)} active metric types from server")
        except Exception as e:
            logger.warning(f"Failed to load metric types: {str(e)}")
    
    def _make_request(self, method: str, endpoint: str, is_units_endpoint: bool = False, is_metric_types_endpoint: bool = False, **kwargs) -> Any:
        """Make a request to the server.
        
        Args:
            method (str): HTTP method
            endpoint (str): API endpoint
            is_units_endpoint (bool): If True, use /api/units instead of /api/metrics
            is_metric_types_endpoint (bool): If True, use /api/metric-types instead of /api/metrics
            **kwargs: Additional request arguments
            
        Returns:
            Any: Response data
            
        Raises:
            requests.RequestException: If request fails
        """
        # Ensure proper API path structure based on endpoint type
        if is_units_endpoint:
            base_path = 'units'
        elif is_metric_types_endpoint:
            base_path = 'metric-types'
        else:
            base_path = 'metrics'
            
        # Construct URL with proper path
        url = f"{self.server_url.rstrip('/')}/api/{base_path}/{endpoint}"
        headers = {'X-API-Key': self.api_key}
        
        if 'headers' in kwargs:
            kwargs['headers'].update(headers)
        else:
            kwargs['headers'] = headers
            
        kwargs['timeout'] = self.request_timeout
        
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def _ensure_metric_type(self, name: str, description: str = None, unit_id: Optional[UUID] = None) -> str:
        """
        Ensure a metric type exists, creating it if necessary.
        
        Args:
            name (str): Name of the metric type
            description (str, optional): Description of the metric type
            unit_id (UUID, optional): ID of the associated unit
            
        Returns:
            str: UUID of the metric type
        """
        if name in self.metric_types:
            return self.metric_types[name]
        
        # Create new metric type
        try:
            response = self._make_request(
                'post',
                '',
                is_metric_types_endpoint=True,
                json={
                    'name': name,
                    'description': description or f"Metric type for {name}",
                    'unit_id': str(unit_id) if unit_id else None,
                    'is_active': True
                }
            )
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
            # Use the metrics endpoint as per the API schema
            response = requests.post(
                f"{self.server_url.rstrip('/')}/api/metrics/",
                json=metrics_data,
                headers=headers,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            return response.json()
        
        try:
            result = _send_request()
            logger.debug(f"Successfully sent metric: {result}")
            return True
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
        bulk_url = f"{self.server_url.rstrip('/')}/api/metrics/bulk"
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key
        }
        
        # Format for bulk endpoint according to API spec
        # The API expects a MetricBulkCreate object with a 'metrics' array of MetricCreate objects
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
    
    def _ensure_source(self) -> str:
        """
        Ensure a source exists, creating it if necessary.
        
        Returns:
            str: UUID of the source
        """
        if self.source_id:
            return self.source_id
            
        # First check if source already exists
        try:
            response = requests.get(
                f"{self.server_url.rstrip('/')}/api/sources/",
                headers={'X-API-Key': self.api_key},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            sources = response.json()
            
            # Check if our source exists
            for source in sources:
                if source.get('name') == self.source_name and source.get('is_active', True):
                    self.source_id = source['id']
                    logger.debug(f"Found existing source: {self.source_name} (ID: {self.source_id})")
                    return self.source_id
                    
            # Create new source if not found
            response = requests.post(
                f"{self.server_url.rstrip('/')}/api/sources/",
                json={
                    'name': self.source_name,
                    'description': self.source_description or f"Source for {self.source_name}",
                    'ip_address': self.source_ip,
                    'is_active': True
                },
                headers={'X-API-Key': self.api_key},
                timeout=self.request_timeout
            )
            response.raise_for_status()
            source = response.json()
            self.source_id = source['id']
            logger.info(f"Created new source: {self.source_name} (ID: {self.source_id})")
            return self.source_id
            
        except Exception as e:
            logger.error(f"Failed to ensure source {self.source_name}: {str(e)}")
            # Generate a temporary UUID for the source if we can't get it from the server
            if not self.source_id:
                self.source_id = str(uuid.uuid4())
                logger.warning(f"Using temporary source ID: {self.source_id}")
            return self.source_id
            
    def send_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """
        Send metrics to the server. If sending fails, add to buffer.
        
        Args:
            metrics_data (dict): The metrics data to send in format:
                {
                    'name': 'metric_name',
                    'value': 123.45,
                    'unit': '%',
                    'description': 'Description of the metric' (optional),
                    'timestamp': '2023-01-01T12:00:00Z' (optional),
                    'metadata': {'key1': 'value1', 'key2': 'value2'} (optional)
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
            # Handle unit if provided
            unit_id = None
            if unit_symbol := metrics_data.get('unit'):
                try:
                    # Use a more descriptive unit name
                    unit_name = unit_symbol
                    if unit_symbol == '%':
                        unit_name = 'Percentage'
                    elif unit_symbol == 'minutes':
                        unit_name = 'Minutes'
                    
                    unit = self.unit_manager.register_unit(
                        name=unit_name,
                        symbol=unit_symbol,
                        description=f"Unit for {unit_name} measurements"
                    )
                    unit_id = unit.id
                except Exception as e:
                    logger.warning(f"Failed to register unit for symbol '{unit_symbol}': {str(e)}")
                    # Create a temporary UUID for the unit so we can continue
                    unit_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"unit-{unit_symbol}"))
            
            # Ensure metric type and source exist
            try:
                metric_type_id = self._ensure_metric_type(
                    metric_name, 
                    description=metrics_data.get('description'),
                    unit_id=unit_id
                )
            except Exception as e:
                logger.warning(f"Failed to ensure metric type: {str(e)}")
                # Create a temporary UUID for the metric type
                metric_type_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, metric_name))
            
            try:
                source_id = self._ensure_source()
            except Exception as e:
                logger.warning(f"Failed to ensure source: {str(e)}")
                # Create a temporary UUID for the source
                source_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, self.source_name))
            
            # Format for web app according to new data model
            # The API expects a MetricCreate object with specific fields
            formatted_metric = {
                'metric_type_id': metric_type_id,
                'source_id': source_id,
                'value': float(metrics_data.get('value', 0)),
                'recorded_at': metrics_data.get('timestamp') or datetime.now(pytz.UTC).isoformat()
            }
            
            # Add metadata if provided
            metadata = metrics_data.get('metadata', {})
            if metadata:
                # Convert metadata to the expected format: list of MetadataCreate objects
                formatted_metric['metadata'] = [
                    {'key': key, 'value': str(value)} for key, value in metadata.items()
                ]
            
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
            # Even if we failed to format properly, try to buffer the metric with basic info
            try:
                self.buffer.add({
                    'metric_type_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, metric_name)),
                    'source_id': str(uuid.uuid5(uuid.NAMESPACE_DNS, self.source_name)),
                    'value': float(metrics_data.get('value', 0)),
                    'recorded_at': datetime.now(pytz.UTC).isoformat(),
                    'metadata': [{'key': k, 'value': str(v)} for k, v in metrics_data.get('metadata', {}).items()]
                })
                logger.warning(f"Added failed metric {metric_name} to buffer")
            except Exception as buffer_err:
                logger.error(f"Failed to buffer metric: {str(buffer_err)}")
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
            'description': metrics.get('description'),
            'timestamp': datetime.now(pytz.UTC).isoformat(),
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
                f"{self.server_url.rstrip('/')}/api/metric-types/",
                headers={'X-API-Key': self.api_key},
                timeout=self.request_timeout
            )
            # Also try to ensure our source is registered
            if response.status_code == 200:
                self._ensure_source()
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
