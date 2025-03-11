"""
Metrics manager for handling collector registration and metric collection.
"""
import logging
from typing import Dict, List, Any, Optional
from uuid import UUID

from .collector import Collector
from .metrics_sdk import MetricsClient, default_client, Unit

logger = logging.getLogger(__name__)

class MetricsManager:
    """
    Manager for handling collector registration and metric collection.
    """
    
    def __init__(self, client: Optional[MetricsClient] = None):
        """
        Initialize the metrics manager.
        
        Args:
            client (MetricsClient, optional): The metrics client to use. Defaults to the default client.
        """
        self.collectors: List[Collector] = []
        
        # Check if we need to create a client
        if client is not None:
            self.client = client
        elif default_client is not None:
            self.client = default_client
        else:
            # Import ensure_default_client to avoid circular imports
            from .metrics_sdk import ensure_default_client
            ensure_default_client()
            from .metrics_sdk import default_client as fresh_client
            self.client = fresh_client
            
        # Now we can safely access the unit_manager
        self.unit_manager = self.client.unit_manager
    
    def register_collector(self, collector: Collector) -> None:
        """
        Register a collector with the manager.
        
        Args:
            collector (Collector): The collector to register
        """
        self.collectors.append(collector)
        logger.debug("Registered collector: %s", collector.name)
    
    def register_collectors(self, collectors: List[Collector]) -> None:
        """
        Register multiple collectors with the manager.
        
        Args:
            collectors (List[Collector]): The collectors to register
        """
        for collector in collectors:
            self.register_collector(collector)
    
    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all registered collectors.
        
        Returns:
            dict: The collected metrics
        """
        metrics = {}
        
        for collector in self.collectors:
            try:
                collector_name = collector.name
                metrics[collector_name] = collector.safe_collect()
            except Exception as e:
                logger.error("Error collecting metrics from %s: %s", collector_name, str(e))
                metrics[collector_name] = {'error': str(e)}
        
        return metrics
    
    def collect_and_send(self) -> bool:
        """
        Collect metrics from all registered collectors and send them to the server.
        
        Returns:
            bool: True if successful, False otherwise
        """
        metrics = self.collect_metrics()
        metrics_batch = self.client.create_metrics_batch(metrics)
        
        return self.client.send_metrics(metrics_batch)
    
    def get_buffered_count(self) -> int:
        """
        Get the number of buffered metrics.
        
        Returns:
            int: Number of buffered metrics
        """
        return self.client.get_buffered_count()


# Singleton instance for easy import - initialized as None and set up on first use
default_manager = None

# Helper function to ensure default manager exists
def ensure_default_manager():
    global default_manager
    if default_manager is None:
        from .metrics_sdk import default_client
        # Only create default_manager after SDK has been properly configured
        default_manager = MetricsManager(client=default_client)


# Convenience functions that use the default manager
def register_collector(collector: Collector) -> None:
    """
    Register a collector with the default manager.
    
    Args:
        collector (Collector): The collector to register
    """
    ensure_default_manager()
    default_manager.register_collector(collector)


def register_collectors(collectors: List[Collector]) -> None:
    """
    Register multiple collectors with the default manager.
    
    Args:
        collectors (List[Collector]): The collectors to register
    """
    ensure_default_manager()
    default_manager.register_collectors(collectors)


def collect_metrics() -> Dict[str, Any]:
    """
    Collect metrics from all registered collectors using the default manager.
    
    Returns:
        dict: The collected metrics
    """
    ensure_default_manager()
    return default_manager.collect_metrics()


def collect_and_send() -> bool:
    """
    Collect metrics from all registered collectors and send them to the server using the default manager.
    
    Returns:
        bool: True if successful, False otherwise
    """
    ensure_default_manager()
    return default_manager.collect_and_send()


def get_buffered_count() -> int:
    """
    Get the number of buffered metrics using the default manager.
    
    Returns:
        int: Number of buffered metrics
    """
    ensure_default_manager()
    return default_manager.get_buffered_count()


# Unit management convenience functions
def create_unit(name: str, symbol: str, description: Optional[str] = None) -> Unit:
    """
    Create a new unit using the default manager.
    
    Args:
        name (str): Name of the unit
        symbol (str): Symbol for the unit
        description (str, optional): Description of the unit
        
    Returns:
        Unit: The created unit
    """
    ensure_default_manager()
    return default_manager.unit_manager.create_unit(name, symbol, description)


def get_unit(unit_id: UUID) -> Unit:
    """
    Get a unit by ID using the default manager.
    
    Args:
        unit_id (UUID): ID of the unit
        
    Returns:
        Unit: The requested unit
    """
    ensure_default_manager()
    return default_manager.unit_manager.get_unit(unit_id)


def get_unit_by_symbol(symbol: str) -> Unit:
    """
    Get a unit by its symbol using the default manager.
    
    Args:
        symbol (str): Symbol of the unit
        
    Returns:
        Unit: The requested unit
    """
    ensure_default_manager()
    return default_manager.unit_manager.get_unit_by_symbol(symbol)


def list_units() -> List[Unit]:
    """
    List all available units using the default manager.
    
    Returns:
        List[Unit]: List of all units
    """
    ensure_default_manager()
    return default_manager.unit_manager.list_units()


def update_unit(unit_id: UUID, **kwargs) -> Unit:
    """
    Update a unit's properties using the default manager.
    
    Args:
        unit_id (UUID): ID of the unit to update
        **kwargs: Properties to update (name, symbol, description)
        
    Returns:
        Unit: The updated unit
    """
    ensure_default_manager()
    return default_manager.unit_manager.update_unit(unit_id, **kwargs)


def delete_unit(unit_id: UUID) -> bool:
    """
    Delete a unit if it's not referenced by any metric types using the default manager.
    
    Args:
        unit_id (UUID): ID of the unit to delete
        
    Returns:
        bool: True if deleted successfully
    """
    ensure_default_manager()
    return default_manager.unit_manager.delete_unit(unit_id)
