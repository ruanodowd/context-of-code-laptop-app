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
    
    All collectors should inherit from this class and implement the collect() method.
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
    
    def safe_collect(self) -> Dict[str, Any]:
        """
        Safely collect metrics, catching any exceptions.
        
        Returns:
            dict: The collected metrics or an error dict if collection fails
        """
        try:
            return self.collect()
        except Exception as e:
            logger.error(f"Error collecting metrics from {self.name}: {str(e)}")
            return {'error': str(e)}
