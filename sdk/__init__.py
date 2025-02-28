"""
Metrics SDK for sending data snapshots to the server.
"""
from .collector import Collector
from .metrics_sdk import (
    MetricsClient, 
    send_metrics, 
    create_metrics_batch, 
    health_check, 
    get_buffered_count as get_client_buffered_count
)
from .metrics_manager import (
    MetricsManager,
    register_collector,
    register_collectors,
    collect_metrics,
    collect_and_send,
    get_buffered_count as get_manager_buffered_count
)

# For backward compatibility and simplicity
get_buffered_count = get_manager_buffered_count

__all__ = [
    'Collector',
    'MetricsClient',
    'MetricsManager',
    'send_metrics',
    'create_metrics_batch',
    'health_check',
    'register_collector',
    'register_collectors',
    'collect_metrics',
    'collect_and_send',
    'get_buffered_count',
]
