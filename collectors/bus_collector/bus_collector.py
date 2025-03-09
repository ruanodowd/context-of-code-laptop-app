import json
import logging
import requests
import time
from requests.exceptions import RequestException
from typing import Dict, Any
from sdk.collector import Collector

logger = logging.getLogger(__name__)

class BusCollector(Collector):
    """Collector for bus arrival metrics."""
    
    def __init__(self, from_stage_name: str, to_stage_name: str, dry_run: bool = False):
        """
        Initialize the bus collector for a specific route.
        
        Args:
            from_stage_name (str): Full name of the origin bus stop
            to_stage_name (str): Full name of the destination bus stop
            dry_run (bool): If True, don't actually send metrics to server
        """
        self.base_url = "https://ticketbooking.dublincoach.ie/MobileAPI/MobileBooking/GetJourneyList"
        self.from_stage_name = from_stage_name
        self.to_stage_name = to_stage_name
        self.dry_run = dry_run
        
    def _string_time_to_minutes(self, time: str) -> int:
        """Convert string time format to minutes
        
        Args:
            time (str): Time string like "1 hr 29 min" or "Arrived"
            
        Returns:
            int: Number of minutes
            
        Raises:
            ValueError: If time string format is invalid
        """
        if time == "Arrived":
            return 0
            
        time_parts = time.split()
        try:
            if len(time_parts) == 4:  # Format: "1 hr 29 min"
                return int(time_parts[0]) * 60 + int(time_parts[2])
            return int(time_parts[0])  # Format: "29 min"
        except (IndexError, ValueError) as e:
            logger.error("Error parsing time string '%s': %s", time, str(e))
            raise ValueError(f"Invalid time format: {time}")
    
    def _get_journey_info(self, origin: str, destination: str) -> Dict:
        """Get journey information for a specific route.
        
        Args:
            origin (str): Origin stop name
            destination (str): Destination stop name
            
        Returns:
            dict: Journey information including minutes until arrival
            
        Raises:
            RequestException: If API request fails
            ValueError: If journey data is invalid or bus hasn't departed
        """
        params = {
            'FromStageName': origin,
            'ToStageName': destination,
            'JourneyType': 0,
            'RouteID': 0,
            'JrEndStageID': 0,
            'IsStageSelection': 1
        }
        
        try:
            logger.debug("Fetching bus data for %s to %s", origin, destination)
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            parsed_data = response.json()
            
            # Handle both list and dictionary responses
            journey_list = None
            if isinstance(parsed_data, dict):
                journey_list = parsed_data.get('Data', {}).get('JourneyList', [])
            elif isinstance(parsed_data, list):
                journey_list = parsed_data
            
            if not journey_list:
                raise ValueError("No journey data available")
                
            journey = journey_list[0]
            if journey['JourneyID'] == 0:
                raise ValueError("The bus has not departed yet")
                
            minutes = self._string_time_to_minutes(journey['LeavingIn'])
            logger.debug("Bus from %s to %s arriving in %s minutes", origin, destination, minutes)
            
            return {
                'minutes_until_arrival': minutes,
                'journey_id': journey['JourneyID'],
                'status': journey['LeavingIn']
            }
            
        except RequestException as e:
            logger.error("API request failed: %s", str(e))
            raise
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Error parsing API response: %s", str(e))
            raise ValueError(f"Invalid API response: {str(e)}")
        except Exception as e:
            logger.error("Unexpected error getting bus arrival time: %s", str(e))
            raise
    
    def collect(self) -> Dict:
        """Collect bus metrics for the configured route.
        
        Returns:
            dict: Bus arrival information for the monitored route
        """
        try:
            return self._get_journey_info(
                self.from_stage_name,
                self.to_stage_name
            )
        except Exception as e:
            logger.error("Error collecting bus metrics: %s", str(e))
            raise RuntimeError(f"Error collecting bus metrics: {str(e)}")

    def format_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the raw bus metrics for the metrics SDK.
        
        Args:
            raw_metrics (dict): Raw bus metrics from collect()
            
        Returns:
            dict: Formatted metrics ready for SDK
        """
        if 'error' in raw_metrics:
            return {'error': raw_metrics['error']}
        
        # Create a unique name for this route
        route_name = f"{self.from_stage_name.replace(' ', '_')}_to_{self.to_stage_name.replace(' ', '_')}_bus_time"
        
        metrics_data = {
            'name': route_name,
            'value': raw_metrics['minutes_until_arrival'],
            'unit': 'minutes',
            'description': f'Minutes until next bus from {self.from_stage_name} to {self.to_stage_name}',
            'metadata': {
                'from_stop': self.from_stage_name,
                'to_stop': self.to_stage_name,
                'status': raw_metrics.get('status', 'Unknown'),
                'journey_id': raw_metrics.get('journey_id', 'Unknown'),
                'collector_type': 'bus',
                'collection_time': time.time()
            }
        }
        
        return metrics_data
    
    def collect_and_send(self) -> Dict[str, Any]:
        """
        Collect, format and send bus metrics for the configured route.
        
        Returns:
            dict: Bus metrics or dict with error information
        """
        # Defer to the base class implementation with our dry_run setting
        result = super().collect_and_send(dry_run=self.dry_run)
        
        # Add our route-specific logging if the collection was successful
        if 'error' not in result:
            logger.info("Bus from %s to %s: %s minutes", 
                      self.from_stage_name, self.to_stage_name, result['minutes_until_arrival'])
        
        return result


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test the collector with a sample route
    from_stop = "Limerick"
    to_stop = "Dublin"
    
    collector = BusCollector(from_stop, to_stop, dry_run=True)
    result = collector.collect_and_send()
    
    if 'error' not in result:
        print("Bus from %s to %s arriving in %s minutes" % 
             (from_stop, to_stop, result['minutes_until_arrival']))
    else:
        print("Error: %s" % result['error'])
