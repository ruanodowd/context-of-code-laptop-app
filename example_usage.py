#!/usr/bin/env python3
"""
Example script demonstrating how to use the updated metrics SDK
with the web app.
"""
import time
import random
import psutil
from sdk import metrics_sdk

def collect_system_metrics():
    """Collect basic system metrics and send them to the server."""
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=1)
    metrics_sdk.send_metrics({
        'name': 'cpu_usage',
        'value': cpu_percent,
        'unit': '%',
        'description': 'CPU usage percentage'
    })
    print(f"Sent CPU usage: {cpu_percent}%")
    
    # Memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    metrics_sdk.send_metrics({
        'name': 'memory_usage',
        'value': memory_percent,
        'unit': '%',
        'description': 'Memory usage percentage'
    })
    print(f"Sent memory usage: {memory_percent}%")
    
    # Disk usage
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    metrics_sdk.send_metrics({
        'name': 'disk_usage',
        'value': disk_percent,
        'unit': '%',
        'description': 'Disk usage percentage'
    })
    print(f"Sent disk usage: {disk_percent}%")

def main():
    """Main function to run the example."""
    print("Starting metrics collection example...")
    
    # Check if the server is accessible
    if not metrics_sdk.health_check():
        print("Warning: Metrics server is not accessible. Metrics will be buffered.")
    
    # Collect metrics every 5 seconds for 1 minute
    for _ in range(12):
        try:
            collect_system_metrics()
        except Exception as e:
            print(f"Error collecting metrics: {e}")
        
        # Wait 5 seconds before next collection
        time.sleep(5)
    
    # Check if there are any buffered metrics
    buffered_count = metrics_sdk.get_buffered_count()
    if buffered_count > 0:
        print(f"There are {buffered_count} metrics in the buffer.")
    
    print("Metrics collection example completed.")

if __name__ == "__main__":
    main()
