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
                # Handle dictionary response format
                # Check if we got a no journeys available message
                if parsed_data.get('Message') == "No journeys available.":
                    logger.info("No journeys available for %s to %s", origin, destination)
                    return {
                        'status': 'no_journeys',
                        'message': f"No journeys available from {origin} to {destination}"
                    }
                    
                # Get journey list from response
                if 'Data' in parsed_data:
                    # If Data is a dict, get JourneyList from it
                    if isinstance(parsed_data['Data'], dict):
                        journey_list = parsed_data['Data'].get('JourneyList', [])
                    # If Data is a list, use it directly
                    elif isinstance(parsed_data['Data'], list):
                        journey_list = parsed_data['Data']
                    # Otherwise, empty list
                    else:
                        journey_list = []
                else:
                    journey_list = []
            elif isinstance(parsed_data, list):
                # Handle list response format
                journey_list = parsed_data
            
            if not journey_list:
                logger.info("Empty journey list for %s to %s", origin, destination)
                return {
                    'status': 'no_journeys',
                    'message': f"No journey data available from {origin} to {destination}"
                }
                
            # Safely access the first journey
            try:
                # Ensure journey_list contains dictionaries with required keys
                if not isinstance(journey_list[0], dict):
                    logger.warning("Unexpected journey data format: %s", type(journey_list[0]))
                    return {
                        'status': 'invalid_format',
                        'message': f"Unexpected journey data format: {type(journey_list[0])}"
                    }
                    
                # Get the first journey from the list
                journey = journey_list[0]
            except IndexError:
                logger.info("Journey list is empty for %s to %s", origin, destination)
                return {
                    'status': 'no_journeys',
                    'message': f"No journeys available from {origin} to {destination}"
                }
            
            # Debug log the journey data structure
            logger.debug("Journey data: %s", json.dumps(journey, indent=2))
            if journey.get('JourneyID', 0) == 0:
                logger.info("The bus from %s to %s has not departed yet", origin, destination)
                return {
                    'status': 'not_departed',
                    'message': f"The bus from {origin} to {destination} has not departed yet"
                }
                
            # Check if journey has required keys
            required_keys = ['JourneyID', 'LeavingIn']
            missing_keys = [key for key in required_keys if key not in journey]
            if missing_keys:
                logger.error("Missing required keys in journey data: %s", missing_keys)
                logger.debug("Available keys: %s", list(journey.keys()))
                raise ValueError(f"Missing required keys in journey data: {missing_keys}")
                
            # Extract time until arrival
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
            dict: Bus arrival information for the monitored route or error information
        """
        try:
            return self._get_journey_info(
                self.from_stage_name,
                self.to_stage_name
            )
        except ValueError as e:
            # Handle expected errors like no journeys available
            error_message = str(e)
            logger.info("Bus collection issue: %s", error_message)
            return {
                'status': 'error',
                'message': error_message,
                'route': f"{self.from_stage_name} to {self.to_stage_name}"
            }
        except Exception as e:
            # Handle unexpected errors
            error_message = str(e)
            logger.error("Error collecting bus metrics: %s", error_message)
            return {
                'status': 'error',
                'message': f"Error collecting bus metrics: {error_message}",
                'route': f"{self.from_stage_name} to {self.to_stage_name}"
            }

    def format_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the raw bus metrics for the metrics SDK.
        
        Args:
            raw_metrics (dict): Raw bus metrics from collect()
            
        Returns:
            dict: Formatted metrics ready for SDK
        """
        # Use custom metric name if set, otherwise create a default route name
        route_name = self.metric_name or f"{self.from_stage_name.replace(' ', '_')}_to_{self.to_stage_name.replace(' ', '_')}_bus_time"
        
        # Check if we have minutes_until_arrival - this is the success case
        if 'minutes_until_arrival' in raw_metrics:
            # We have a valid arrival time
            minutes = raw_metrics['minutes_until_arrival']
            
            metrics_data = {
                'name': route_name,
                'value': minutes,  # Use the actual minutes value
                'unit': 'min',
                'description': f'Minutes until next bus from {self.from_stage_name} to {self.to_stage_name}',
                'metadata': {
                    'from_stop': self.from_stage_name,
                    'to_stop': self.to_stage_name,
                    'status': raw_metrics.get('status', 'Available'),
                    'journey_id': raw_metrics.get('journey_id', 'Unknown'),
                    'collector_type': 'bus',
                    'collection_time': time.time()
                }
            }
            return metrics_data
            
        # Handle specific error cases
        if 'status' in raw_metrics:
            status = raw_metrics['status']
            if status == 'not_departed':
                # Bus hasn't departed yet - this is not an error, just zero minutes
                return {
                    'name': route_name,
                    'value': 0,  # Zero minutes until arrival for not departed buses
                    'unit': 'min',
                    'description': f'Minutes until next bus from {self.from_stage_name} to {self.to_stage_name}',
                    'metadata': {
                        'from_stop': self.from_stage_name,
                        'to_stop': self.to_stage_name,
                        'status': 'Not departed',
                        'collector_type': 'bus',
                        'collection_time': time.time()
                    }
                }
            else:
                # Other status cases (no_journeys, invalid_format, etc.)
                return {
                    'name': route_name,
                    'value': 0,  # Use 0 as a placeholder value for error cases
                    'unit': 'min',
                    'description': f'Minutes until next bus from {self.from_stage_name} to {self.to_stage_name}',
                    'error': raw_metrics.get('message', f'Status: {status}'),
                    'metadata': {
                        'from_stop': self.from_stage_name,
                        'to_stop': self.to_stage_name,
                        'status': status,
                        'collector_type': 'bus',
                        'collection_time': time.time()
                    }
                }
        
        # Handle error field for backward compatibility
        if 'error' in raw_metrics:
            return {
                'name': route_name,
                'value': 0,  # Use 0 as a placeholder value for error cases
                'unit': 'min',
                'description': f'Minutes until next bus from {self.from_stage_name} to {self.to_stage_name}',
                'error': raw_metrics['error'],
                'metadata': {
                    'from_stop': self.from_stage_name,
                    'to_stop': self.to_stage_name,
                    'status': 'Error',
                    'collector_type': 'bus',
                    'collection_time': time.time()
                }
            }
            
        # Fallback for any other case
        return {
            'name': route_name,
            'value': 0,  # Use 0 as a placeholder value for unknown cases
            'unit': 'min',
            'description': f'Minutes until next bus from {self.from_stage_name} to {self.to_stage_name}',
            'error': 'No arrival time information available',
            'metadata': {
                'from_stop': self.from_stage_name,
                'to_stop': self.to_stage_name,
                'status': 'Unknown',
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
        # Collect the raw metrics
        raw_metrics = self.safe_collect()
        
        # Format the metrics for sending
        formatted_metrics = self.format_metrics(raw_metrics)
        
        # Log appropriate information based on the collection result
        if 'minutes_until_arrival' in raw_metrics:
            # Successfully collected arrival time
            minutes = raw_metrics['minutes_until_arrival']
            logger.info("Bus from %s to %s: %s minutes", 
                      self.from_stage_name, self.to_stage_name, minutes)
        elif 'status' in raw_metrics and raw_metrics['status'] == 'not_departed':
            # Bus hasn't departed yet
            logger.info("The bus from %s to %s has not departed yet", 
                      self.from_stage_name, self.to_stage_name)
        elif 'error' in raw_metrics or ('status' in raw_metrics and raw_metrics['status'] != 'success'):
            # Error occurred during collection
            error_msg = raw_metrics.get('message', raw_metrics.get('error', 'Unknown error'))
            logger.info("Bus collection issue: %s", error_msg)
        
        # Send the formatted metrics
        if self.dry_run:
            logger.info("DRY RUN: Would send %s metrics: %s", self.name, formatted_metrics)
        else:
            # Import here to avoid circular imports
            try:
                from sdk import metrics_sdk
                metrics_sdk.send_metrics(formatted_metrics)
            except (ImportError, AttributeError) as e:
                logger.warning("Cannot send metrics: %s", str(e))
        
        # Return the raw metrics with additional information
        return {**raw_metrics, 'formatted_metrics': formatted_metrics}


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
