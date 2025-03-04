#!/usr/bin/env python3
"""
Example script demonstrating how to use multiple collectors
including battery and bus information.
"""
import time
import logging
from collectors.battery_collector.battery_collector import BatteryCollector
from collectors.bus_collector.bus_collector import BusCollector
from sdk import metrics_sdk

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def collect_all_metrics():
    """Collect metrics from all collectors and send them to the server."""
    # Initialize collectors
    battery_collector = BatteryCollector()
    
    # Initialize bus collectors for specific routes
    ul_to_hazel = BusCollector(
        from_stage_name="T310 UL East Gate / An Geata Thoir",
        to_stage_name="T310 Hazel Hall Estate"
    )
    
    beechfield_to_ul = BusCollector(
        from_stage_name="T310 Beechfield",
        to_stage_name="T310 UL East Gate / An Geata Thoir"
    )
    
    try:
        # Collect battery metrics
        battery_metric = battery_collector.safe_collect()
        if 'error' not in battery_metric:
            logger.info(f"Battery: {battery_metric['metric']}%")
            metrics_sdk.send_metrics({
                'name': 'battery_percentage',
                'value': battery_metric['metric'],
                'unit': '%',
                'description': 'Battery charge percentage',
                'metadata': {
                    'collector_type': 'battery',
                    'collection_time': time.time()
                }
            })
        else:
            logger.error(f"Battery collection error: {battery_metric['error']}")
        
        # Collect UL to Hazel Hall bus metrics
        ul_hazel_metrics = ul_to_hazel.safe_collect()
        if 'error' not in ul_hazel_metrics:
            logger.info(f"UL to Hazel Hall bus: {ul_hazel_metrics['minutes_until_arrival']} minutes")
            metrics_sdk.send_metrics({
                'name': 'ul_to_hazel_bus_time',
                'value': ul_hazel_metrics['minutes_until_arrival'],
                'unit': 'minutes',
                'description': 'Minutes until next bus from UL East Gate to Hazel Hall',
                'metadata': {
                    'from_stop': ul_to_hazel.from_stage_name,
                    'to_stop': ul_to_hazel.to_stage_name,
                    'status': ul_hazel_metrics.get('status', 'Unknown'),
                    'journey_id': ul_hazel_metrics.get('journey_id', 'Unknown'),
                    'collector_type': 'bus',
                    'collection_time': time.time()
                }
            })
        else:
            logger.error(f"UL to Hazel Hall bus collection error: {ul_hazel_metrics['error']}")
        
        # Collect Beechfield to UL bus metrics
        beechfield_metrics = beechfield_to_ul.safe_collect()
        if 'error' not in beechfield_metrics:
            logger.info(f"Beechfield to UL bus: {beechfield_metrics['minutes_until_arrival']} minutes")
            metrics_sdk.send_metrics({
                'name': 'beechfield_to_ul_bus_time',
                'value': beechfield_metrics['minutes_until_arrival'],
                'unit': 'minutes',
                'description': 'Minutes until next bus from Beechfield to UL East Gate',
                'metadata': {
                    'from_stop': beechfield_to_ul.from_stage_name,
                    'to_stop': beechfield_to_ul.to_stage_name,
                    'status': beechfield_metrics.get('status', 'Unknown'),
                    'journey_id': beechfield_metrics.get('journey_id', 'Unknown'),
                    'collector_type': 'bus',
                    'collection_time': time.time()
                }
            })
        else:
            logger.error(f"Beechfield to UL bus collection error: {beechfield_metrics['error']}")
            
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")

def main():
    """Main function to run the collectors example."""
    logger.info("Starting collectors example...")
    
    # Check if the server is accessible
    if not metrics_sdk.health_check():
        logger.warning("Metrics server is not accessible. Metrics will be buffered.")
    
    # Collect metrics every minute for 10 minutes
    for i in range(1000):
        logger.info(f"Collection round {i + 1}/10")
        collect_all_metrics()
        time.sleep(60)  # Wait 1 minute between collections
    
    # Check if there are any buffered metrics
    buffered_count = metrics_sdk.get_buffered_count()
    if buffered_count > 0:
        logger.info(f"There are {buffered_count} metrics in the buffer.")
    
    logger.info("Collectors example completed.")

if __name__ == "__main__":
    main()
