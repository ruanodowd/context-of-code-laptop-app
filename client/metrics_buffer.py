"""
Buffer for storing metrics when server is unavailable.
"""
import json
import logging
import os
from collections import deque
from . import config

logger = logging.getLogger(__name__)

class MetricsBuffer:
    def __init__(self):
        self.buffer = deque(maxlen=config.BUFFER_SIZE)
        self._load_buffer()
    
    def add(self, metric):
        """
        Add a metric to the buffer.
        
        Args:
            metric (dict): The metric to buffer
        """
        self.buffer.append(metric)
        self._save_buffer()
        
    def get_all(self):
        """
        Get all metrics from the buffer.
        
        Returns:
            list: All buffered metrics
        """
        return list(self.buffer)
    
    def clear(self):
        """Clear all metrics from the buffer."""
        self.buffer.clear()
        self._save_buffer()
    
    def _save_buffer(self):
        """Save buffer to disk."""
        try:
            with open(config.BUFFER_FILE, 'w') as f:
                json.dump(list(self.buffer), f)
        except IOError as e:
            logger.error(f"Failed to save buffer: {str(e)}")
    
    def _load_buffer(self):
        """Load buffer from disk if it exists."""
        if os.path.exists(config.BUFFER_FILE):
            try:
                with open(config.BUFFER_FILE, 'r') as f:
                    data = json.load(f)
                    self.buffer.extend(data)
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load buffer: {str(e)}")
                
    def __len__(self):
        return len(self.buffer)
