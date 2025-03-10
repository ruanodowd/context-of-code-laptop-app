"""
Base collector class for standardizing metric collection.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Collector(ABC):
    """
    Abstract base class for all metric collectors.
    
    All collectors should inherit from this class and implement the required methods:
    - collect(): Implement the specific data collection logic
    - format_metrics(): Format the raw metrics for the SDK
    """
    
    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        """
        Collect metrics.
        
        Returns:
            dict: The collected metrics
        """
        pass
    
    @property
    def name(self) -> str:
        """
        Get the name of the collector.
        
        Returns:
            str: The name of the collector (class name by default)
        """
        return self.__class__.__name__
        
    @property
    def metric_name(self) -> str:
        """
        Get the metric name to use when sending metrics.
        If a custom metric_name was set, use that, otherwise use a default.
        
        Returns:
            str: The metric name to use
        """
        # Return custom metric name if set, otherwise None
        # Subclasses should implement their own default metric name
        return getattr(self, '_metric_name', None)
    
    @metric_name.setter
    def metric_name(self, value: str) -> None:
        """
        Set a custom metric name to use when sending metrics.
        
        Args:
            value (str): The metric name to use
        """
        self._metric_name = value
    
    def safe_collect(self) -> Dict[str, Any]:
        """
        Safely collect metrics, catching any exceptions.
        
        Returns:
            dict: The collected metrics or an error dict if collection fails
        """
        try:
            return self.collect()
        except Exception as e:
            logger.error("Error collecting metrics from %s: %s", self.name, str(e))
            return {'error': str(e)}
    
    @abstractmethod
    def format_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the raw metrics for the metrics SDK.
        
        Args:
            raw_metrics (dict): Raw metrics from collect()
            
        Returns:
            dict: Formatted metrics ready for SDK
        """
        pass
    
    def collect_and_send(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Collect, format and send metrics.
        
        Args:
            dry_run (bool): If True, don't actually send metrics to server
            
        Returns:
            dict: Collected metrics or error information
        """
        metrics = self.safe_collect()
        
        if 'error' in metrics:
            logger.error("%s collection error: %s", self.name, metrics['error'])
            return metrics
        
        formatted_metrics = self.format_metrics(metrics)
        
        if dry_run:
            logger.info("DRY RUN: Would send %s metrics: %s", self.name, formatted_metrics)
        else:
            # Import here to avoid circular imports
            try:
                from sdk import metrics_sdk
                metrics_sdk.send_metrics(formatted_metrics)
            except (ImportError, AttributeError) as e:
                logger.warning("Cannot send metrics: %s", str(e))
        
        return metrics
