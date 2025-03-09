#!/usr/bin/env python3
"""
CLI application for collecting and sending metrics from various collectors.
This is a more customizable version of the custom_collectors_example.py script.
"""
import argparse
import importlib
import inspect
import logging
import pkgutil
import sys
import time
from typing import List, Dict, Any, Optional, Type, Tuple

from sdk.collector import Collector
from sdk import metrics_sdk
from sdk import config
from command_relay import start_command_relay, stop_command_relay

# Setup logging
logger = logging.getLogger(__name__)


class CollectorRegistry:
    """
    Registry for dynamically discovering and instantiating collectors.
    This eliminates the need for main.py to have specific knowledge of collectors.
    """
    
    def __init__(self):
        self.collectors = {}
    
    def discover_collectors(self):
        """
        Discover all collector classes that inherit from the base Collector class.
        """
        import collectors
        logger.debug("Starting collector discovery...")
        
        # First, try to directly import known collector modules
        known_modules = [
            'collectors.battery_collector.battery_collector',
            'collectors.bus_collector.bus_collector'
        ]
        
        for module_name in known_modules:
            try:
                logger.debug("Attempting to import known module: %s", module_name)
                module = importlib.import_module(module_name)
                self._register_collectors_from_module(module)
            except ImportError as e:
                logger.warning("Could not import known collector module %s: %s", module_name, e)
        
        # Then fall back to automatic discovery
        collector_modules = self._find_collector_modules(collectors)
        logger.debug("Found collector modules: %s", collector_modules)
        
        for module_name in collector_modules:
            try:
                logger.debug("Attempting to import module: %s", module_name)
                module = importlib.import_module(module_name)
                self._register_collectors_from_module(module)
            except ImportError as e:
                logger.warning("Could not import collector module %s: %s", module_name, e)
    
    def _find_collector_modules(self, package) -> List[str]:
        """
        Find all modules in the collectors package that might contain collectors.
        """
        modules = []
        prefix = package.__name__ + "."
        
        for _, name, is_pkg in pkgutil.iter_modules(package.__path__, prefix):
            if is_pkg:
                try:
                    subpackage = importlib.import_module(name)
                    modules.extend(self._find_collector_modules(subpackage))
                except ImportError as e:
                    logger.warning("Could not import collector package %s: %s", name, e)
            else:
                modules.append(name)
        
        return modules
    
    def _register_collectors_from_module(self, module):
        """
        Register all collector classes from a module.
        """
        found_collectors = False
        logger.debug("Examining module %s for collectors", module.__name__)
        
        for name, obj in inspect.getmembers(module):
            try:
                if (inspect.isclass(obj) and 
                    issubclass(obj, Collector) and 
                    obj != Collector and 
                    not inspect.isabstract(obj)):
                    
                    # Extract collector type from class name or attributes
                    collector_type = obj.__name__.replace('Collector', '').lower()
                    self.collectors[collector_type] = obj
                    logger.info("Registered collector: %s from class %s", collector_type, obj.__name__)
                    found_collectors = True
            except TypeError:
                # This can happen when inspecting objects that can't be checked with issubclass
                pass
                
        if not found_collectors:
            logger.debug("No collectors found in module %s", module.__name__)
    
    def get_collector_class(self, collector_type: str) -> Optional[Type[Collector]]:
        """
        Get the collector class for a given collector type.
        
        Args:
            collector_type (str): The type of collector to get
            
        Returns:
            Type[Collector]: The collector class or None if not found
        """
        return self.collectors.get(collector_type.lower())
    
    def get_available_collectors(self) -> List[str]:
        """
        Get a list of available collector types.
        
        Returns:
            list: List of available collector types
        """
        return list(self.collectors.keys())


# Initialize collector registry
collector_registry = CollectorRegistry()


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


def instantiate_collector(collector_type: str, collector_args: Dict[str, Any], dry_run: bool) -> Optional[Collector]:
    """
    Instantiate a collector of the specified type with the provided arguments.
    
    Args:
        collector_type (str): Type of collector to instantiate
        collector_args (dict): Arguments to pass to the collector constructor
        dry_run (bool): Whether to run in dry-run mode
        
    Returns:
        Collector: An instance of the requested collector or None if not found
    """
    # Handle common variations in collector type names
    collector_type = collector_type.lower()
    if collector_type.endswith('collector'):
        collector_type = collector_type[:-9]  # Remove 'collector' suffix
    
    # Get the collector class
    collector_class = collector_registry.get_collector_class(collector_type)
    
    if not collector_class:
        available = collector_registry.get_available_collectors()
        logger.error("Collector type not found: %s. Available collectors: %s", 
                    collector_type, available if available else "None discovered")
        return None
    
    try:
        # Add dry_run to constructor arguments if the collector accepts it
        constructor_params = inspect.signature(collector_class.__init__).parameters
        if 'dry_run' in constructor_params:
            collector_args['dry_run'] = dry_run
            
        # Instantiate the collector
        return collector_class(**collector_args)
        
    except Exception as e:
        logger.error("Error instantiating collector %s: %s", collector_type, e)
        return None


def collect_with_collector(collector: Collector, dry_run: bool = False) -> Optional[Dict[str, Any]]:
    """
    Collect metrics using the provided collector.
    
    Args:
        collector (Collector): The collector to use
        dry_run (bool): Whether to run in dry-run mode
        
    Returns:
        dict: Collected metrics or None if collection failed
    """
    try:
        # Check if the collector's collect_and_send method accepts dry_run parameter
        collect_and_send_params = inspect.signature(collector.collect_and_send).parameters
        
        if 'dry_run' in collect_and_send_params:
            # If it accepts dry_run, pass it
            return collector.collect_and_send(dry_run=dry_run)
        else:
            # If it doesn't accept dry_run, call without the parameter
            logger.debug("%s.collect_and_send() doesn't accept dry_run parameter", collector.__class__.__name__)
            return collector.collect_and_send()
            
    except Exception as e:
        logger.error("Error collecting metrics with %s: %s", collector.name, e)
        return None


def parse_collector_spec(spec: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parse a collector specification string into a collector type and parameters.
    
    Args:
        spec (str): Collector specification in format "type:param1=value1,param2=value2"
        
    Returns:
        tuple: (collector_type, parameters_dict)
    """
    parts = spec.split(':', 1)
    collector_type = parts[0].strip().lower()
    
    params = {}
    if len(parts) > 1 and parts[1].strip():
        param_parts = parts[1].strip().split(',')
        for param in param_parts:
            if '=' in param:
                key, value = param.split('=', 1)
                params[key.strip()] = value.strip()
    
    return collector_type, params


def collect_all_metrics(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Collect metrics from all configured collectors based on command line arguments.
    
    Args:
        args (argparse.Namespace): Command line arguments
        
    Returns:
        dict: Dictionary with all collected metrics
    """
    results = {}
    
    try:
        # Process collectors
        for collector_spec in args.collectors:
            try:
                collector_type, params = parse_collector_spec(collector_spec)
                
                # Create the collector and collect metrics
                collector = instantiate_collector(collector_type, params, args.dry_run)
                if collector:
                    collector_results = collect_with_collector(collector, args.dry_run)
                    
                    # Store results (either as a single item or in a list depending on collector type)
                    if collector_type not in results:
                        if collector_type == 'bus':  # Bus collector results should be in a list
                            results[collector_type] = []
                        else:
                            results[collector_type] = None
                        
                    if collector_type == 'bus' and isinstance(results[collector_type], list):
                        if collector_results and 'error' not in collector_results:
                            results[collector_type].append(collector_results)
                    else:
                        results[collector_type] = collector_results
                        
            except ValueError as e:
                logger.error("Invalid collector specification: %s. Error: %s", collector_spec, e)
    
    except Exception as e:
        logger.error("Error collecting metrics: %s", e)
    
    return results


def main():
    """Main function to parse arguments and run the collectors."""
    # Parse arguments first to get log level
    parser = argparse.ArgumentParser(
        description='Collect and send metrics from various collectors.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Add log level argument early
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Log level')
    
    # Parse just the log level first
    args, _ = parser.parse_known_args()
    
    # Setup logging with the specified log level
    setup_logging(args.log_level)
    
    # Now discover collectors
    logger.info("Discovering collectors...")
    collector_registry.discover_collectors()
    available_collectors = collector_registry.get_available_collectors()
    logger.info("Available collectors: %s", available_collectors)
    
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
    
    # Generic collector option for any collector type
    parser.add_argument('--collectors', type=str, nargs='*', required=True,
                        help='List of collectors to run in format "type:param1=value1,param2=value2"')
    
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
    if not args.collectors:
        logger.error("No collectors specified. Use --collectors to specify the collectors to run.")
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
