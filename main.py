#!/usr/bin/env python3
"""
CLI application for collecting and sending metrics from various collectors.
This is a more customizable version of the custom_collectors_example.py script.
"""
import argparse
import logging
import sys
import time
from typing import List, Dict, Any, Optional

from collectors.battery_collector.battery_collector import BatteryCollector
from collectors.bus_collector.bus_collector import BusCollector
from sdk import metrics_sdk
from sdk import config
from command_relay import start_command_relay, stop_command_relay

# Setup logging
logger = logging.getLogger(__name__)


def setup_logging(log_level: str) -> None:
    """
    Setup logging with the specified log level.
    
    Args:
        log_level (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def configure_sdk(args: argparse.Namespace) -> None:
    """
    Configure the metrics SDK with command line arguments.
    
    Args:
        args (argparse.Namespace): Command line arguments
    """
    # Create a new client with the specified configuration
    metrics_sdk.default_client = metrics_sdk.MetricsClient(
        server_url=args.server_url,
        api_key=args.api_key,
        source_name=args.source_name,
        source_description=args.source_description,
        source_ip=args.source_ip,
        buffer_file=args.buffer_file,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        request_timeout=args.request_timeout
    )


def collect_battery_metrics(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """
    Collect battery metrics.
    
    Args:
        args (argparse.Namespace): Command line arguments
        
    Returns:
        dict: Battery metrics or None if collection failed
    """
    if not args.collect_battery:
        return None
        
    battery_collector = BatteryCollector()
    battery_metric = battery_collector.safe_collect()
    
    if 'error' in battery_metric:
        logger.error("Battery collection error: %s", battery_metric['error'])
        return None
        
    logger.info("Battery: %s%%", battery_metric['metric'])
    
    metrics_data = {
        'name': 'battery_percentage',
        'value': battery_metric['metric'],
        'unit': '%',
        'description': 'Battery charge percentage',
        'metadata': {
            'collector_type': 'battery',
            'collection_time': time.time()
        }
    }
    
    if args.dry_run:
        logger.info("DRY RUN: Would send battery metrics: %s", metrics_data)
    else:
        metrics_sdk.send_metrics(metrics_data)
        
    return battery_metric


def collect_bus_metrics(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """
    Collect bus metrics for all specified routes.
    
    Args:
        args (argparse.Namespace): Command line arguments
        
    Returns:
        list: List of collected bus metrics
    """
    if not args.bus_routes:
        return []
        
    results = []
    
    for route in args.bus_routes:
        try:
            from_stop, to_stop = route.split(':')
            
            bus_collector = BusCollector(
                from_stage_name=from_stop,
                to_stage_name=to_stop
            )
            
            bus_metrics = bus_collector.safe_collect()
            
            if 'error' in bus_metrics:
                logger.error("Bus collection error for %s to %s: %s", from_stop, to_stop, bus_metrics['error'])
                continue
                
            logger.info("Bus from %s to %s: %s minutes", from_stop, to_stop, bus_metrics['minutes_until_arrival'])
            
            # Create a unique name for this route
            route_name = f"{from_stop.replace(' ', '_')}_to_{to_stop.replace(' ', '_')}_bus_time"
            
            metrics_data = {
                'name': route_name,
                'value': bus_metrics['minutes_until_arrival'],
                'unit': 'minutes',
                'description': f'Minutes until next bus from {from_stop} to {to_stop}',
                'metadata': {
                    'from_stop': from_stop,
                    'to_stop': to_stop,
                    'status': bus_metrics.get('status', 'Unknown'),
                    'journey_id': bus_metrics.get('journey_id', 'Unknown'),
                    'collector_type': 'bus',
                    'collection_time': time.time()
                }
            }
            
            if args.dry_run:
                logger.info("DRY RUN: Would send bus metrics: %s", metrics_data)
            else:
                metrics_sdk.send_metrics(metrics_data)
                
            results.append(bus_metrics)
            
        except ValueError as e:
            logger.error("Invalid bus route format: %s. Use 'from_stop:to_stop'. Error: %s", route, e)
            
    return results


def collect_all_metrics(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Collect metrics from all configured collectors.
    
    Args:
        args (argparse.Namespace): Command line arguments
        
    Returns:
        dict: Dictionary with all collected metrics
    """
    results = {
        'battery': None,
        'bus': []
    }
    
    try:
        # Collect battery metrics
        results['battery'] = collect_battery_metrics(args)
        
        # Collect bus metrics
        results['bus'] = collect_bus_metrics(args)
        
    except Exception as e:
        logger.error("Error collecting metrics: %s", e)
        
    return results


def main():
    """Main function to parse arguments and run the collectors."""
    parser = argparse.ArgumentParser(
        description='Collect and send metrics from various collectors.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # General options
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Log level')
    parser.add_argument('--interval', type=int, default=60,
                        help='Interval between collections in seconds')
    parser.add_argument('--count', type=int, default=0,
                        help='Number of collection rounds (0 for infinite)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Do not send metrics to server, just log them')
    
    # Collector options
    parser.add_argument('--collect-battery', action='store_true',
                        help='Collect battery metrics')
    parser.add_argument('--bus-routes', type=str, nargs='*',
                        help='Bus routes to monitor in format "from_stop:to_stop"')
    
    # SDK configuration
    parser.add_argument('--server-url', type=str, default=config.SERVER_URL,
                        help='URL of the metrics server')
    parser.add_argument('--api-key', type=str, default=config.API_KEY,
                        help='API key for authentication')
    parser.add_argument('--source-name', type=str, default=config.SOURCE_NAME,
                        help='Source name for metrics')
    parser.add_argument('--source-description', type=str, default=config.SOURCE_DESCRIPTION,
                        help='Description of the source')
    parser.add_argument('--source-ip', type=str, default=config.SOURCE_IP,
                        help='IP address of the source')
    parser.add_argument('--buffer-file', type=str, default=config.BUFFER_FILE,
                        help='Path to the buffer file')
    parser.add_argument('--max-retries', type=int, default=config.MAX_RETRIES,
                        help='Maximum number of retries')
    parser.add_argument('--retry-delay', type=int, default=config.RETRY_DELAY,
                        help='Delay between retries in seconds')
    parser.add_argument('--request-timeout', type=int, default=config.REQUEST_TIMEOUT,
                        help='Request timeout in seconds')
    
    # Command relay options
    parser.add_argument('--enable-command-relay', action='store_true',
                        help='Enable command relay to receive commands from server')
    parser.add_argument('--command-server-url', type=str,
                        help='Base URL of the command server API')
    parser.add_argument('--poll-interval', type=int, default=30,
                        help='Interval between polling for commands in seconds')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Configure SDK
    configure_sdk(args)
    
    # Check if the server is accessible
    if not args.dry_run and not metrics_sdk.health_check():
        logger.warning("Metrics server is not accessible. Metrics will be buffered.")
    
    # Start command relay if enabled
    if args.enable_command_relay:
        logger.info("Starting command relay client...")
        start_command_relay(
            server_url=args.command_server_url,
            api_key=args.api_key,
            client_id=args.source_name,
            poll_interval=args.poll_interval
        )
    
    # Validate arguments
    if not args.collect_battery and not args.bus_routes:
        logger.error("No collectors specified. Use --collect-battery or --bus-routes.")
        sys.exit(1)
    
    # Run collection rounds
    round_count = 0
    try:
        while args.count == 0 or round_count < args.count:
            round_count += 1
            logger.info("Collection round %s%s", round_count, 
                        ("/%s" % args.count if args.count > 0 else ""))
            
            collect_all_metrics(args)
            
            if args.count == 0 or round_count < args.count:
                logger.info("Waiting %s seconds until next collection...", args.interval)
                time.sleep(args.interval)
    
    except KeyboardInterrupt:
        logger.info("Collection interrupted by user.")
    
    # Check if there are any buffered metrics
    buffered_count = metrics_sdk.get_buffered_count()
    if buffered_count > 0:
        logger.info("There are %s metrics in the buffer.", buffered_count)
    
    # Stop command relay if it was started
    if args.enable_command_relay:
        logger.info("Stopping command relay client...")
        stop_command_relay()
    
    logger.info("Collection completed.")


if __name__ == "__main__":
    main()
