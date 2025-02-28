"""
Main entry point for the metrics collection client.
"""
import logging
import signal
import sys
from apscheduler.schedulers.blocking import BlockingScheduler
from sdk import register_collector, collect_and_send
from client import config

# Import your collectors here
from collectors.battery_collector.battery_collector import BatteryCollector
# Import other collectors as needed
from collectors.bus_collector.bus_collector import BusCollector
# Configure logging
logging.basicConfig(
    level=config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_collectors():
    """
    Register all collectors with the SDK.
    """
    # Register your collectors here
    register_collector(BatteryCollector())
    register_collector(BusCollector())
    # Add other collectors as needed

def graceful_shutdown(signum, frame):
    """
    Handle graceful shutdown of the application.
    """
    logger.info("Received shutdown signal, stopping scheduler...")
    scheduler.shutdown()
    sys.exit(0)

if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    # Initialize the collectors
    setup_collectors()
    
    # Setup the scheduler
    scheduler = BlockingScheduler()
    scheduler.add_job(
        collect_and_send,
        'interval',
        seconds=config.COLLECTION_INTERVAL
    )
    
    try:
        logger.info("Starting metrics collection...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        logger.error(f"Error in main loop: {str(e)}")
        sys.exit(1)
