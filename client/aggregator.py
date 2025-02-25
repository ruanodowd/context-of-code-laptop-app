"""
Aggregates metrics from various collectors.
"""
import logging
from datetime import datetime
import pytz
from . import http_client
from . import metrics_buffer

logger = logging.getLogger(__name__)

class MetricsAggregator:
    def __init__(self):
        self.buffer = metrics_buffer.MetricsBuffer()
        self.collectors = []
    
    def register_collector(self, collector):
        """
        Register a new metrics collector.
        
        Args:
            collector: A collector object that implements a collect() method
        """
        self.collectors.append(collector)
    
    def collect_and_send(self):
        """
        Collect metrics from all registered collectors and send them to the server.
        """
        metrics_batch = {
            'timestamp': datetime.now(pytz.UTC).isoformat(),
            'metrics': {}
        }
        
        # Collect from all registered collectors
        for collector in self.collectors:
            try:
                collector_name = collector.__class__.__name__
                metrics_batch['metrics'][collector_name] = collector.collect()
            except Exception as e:
                logger.error(f"Error collecting metrics from {collector_name}: {str(e)}")
        
        # Try to send metrics
        try:
            # First try to send any buffered metrics
            if len(self.buffer) > 0:
                buffered_metrics = self.buffer.get_all()
                for metric in buffered_metrics:
                    if http_client.send_metrics(metric):
                        self.buffer.clear()
            
            # Send current metrics
            if http_client.send_metrics(metrics_batch):
                logger.info("Successfully sent metrics to server")
            else:
                self.buffer.add(metrics_batch)
                logger.warning("Failed to send metrics, added to buffer")
        except Exception as e:
            self.buffer.add(metrics_batch)
            logger.error(f"Error sending metrics: {str(e)}")
    
    def get_buffered_count(self):
        """
        Get the number of buffered metrics.
        
        Returns:
            int: Number of buffered metrics
        """
        return len(self.buffer)
