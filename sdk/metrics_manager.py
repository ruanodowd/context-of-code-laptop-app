"""
Metrics manager for handling collector registration and metric collection.
"""
import logging
from typing import Dict, List, Any, Optional

from .collector import Collector
from .metrics_sdk import MetricsClient, default_client

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
        self.client = client or default_client
    
    def register_collector(self, collector: Collector) -> None:
        """
        Register a collector with the manager.
        
        Args:
            collector (Collector): The collector to register
        """
        self.collectors.append(collector)
        logger.debug(f"Registered collector: {collector.name}")
    
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
                logger.error(f"Error collecting metrics from {collector_name}: {str(e)}")
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


# Singleton instance for easy import
default_manager = MetricsManager()


# Convenience functions that use the default manager
def register_collector(collector: Collector) -> None:
    """
    Register a collector with the default manager.
    
    Args:
        collector (Collector): The collector to register
    """
    default_manager.register_collector(collector)


def register_collectors(collectors: List[Collector]) -> None:
    """
    Register multiple collectors with the default manager.
    
    Args:
        collectors (List[Collector]): The collectors to register
    """
    default_manager.register_collectors(collectors)


def collect_metrics() -> Dict[str, Any]:
    """
    Collect metrics from all registered collectors using the default manager.
    
    Returns:
        dict: The collected metrics
    """
    return default_manager.collect_metrics()


def collect_and_send() -> bool:
    """
    Collect metrics from all registered collectors and send them to the server using the default manager.
    
    Returns:
        bool: True if successful, False otherwise
    """
    return default_manager.collect_and_send()


def get_buffered_count() -> int:
    """
    Get the number of buffered metrics using the default manager.
    
    Returns:
        int: Number of buffered metrics
    """
    return default_manager.get_buffered_count()
