import json
import logging
import requests
from requests.exceptions import RequestException
from typing import Dict, Optional
from sdk.collector import Collector

logger = logging.getLogger(__name__)

class BusCollector(Collector):
    """Collector for bus arrival metrics."""
    
    def __init__(self):
        self.base_url = "https://ticketbooking.dublincoach.ie/MobileAPI/MobileBooking/GetJourneyList"
        # Define common bus stops
        self.stops = {
            'ul_student_centre': "T310 UL Student Centre / Ionad na Mac Leinn",
            'hazel_hall': "T310 Hazel Hall Estate",
            'ul_east_gate': "T310 UL East Gate / An Geata Thoir"
        }
        
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
            logger.error(f"Error parsing time string '{time}': {str(e)}")
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
            logger.debug(f"Fetching bus data for {origin} to {destination}")
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            parsed_data = response.json()
            if not parsed_data.get('Data', {}).get('JourneyList'):
                raise ValueError("No journey data available")
                
            journey = parsed_data['Data']['JourneyList'][0]
            if journey['JourneyID'] == 0:
                raise ValueError("The bus has not departed yet")
                
            minutes = self._string_time_to_minutes(journey['LeavingIn'])
            logger.debug(f"Bus from {origin} to {destination} arriving in {minutes} minutes")
            
            return {
                'minutes_until_arrival': minutes,
                'journey_id': journey['JourneyID'],
                'status': journey['LeavingIn']
            }
            
        except RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing API response: {str(e)}")
            raise ValueError(f"Invalid API response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting bus arrival time: {str(e)}")
            raise
    
    def collect(self) -> Dict:
        """Collect bus metrics for configured routes.
        
        Returns:
            dict: Bus arrival information for all monitored routes
        """
        try:
            metrics = {
                'to_ul': self._get_journey_info(
                    self.stops['hazel_hall'],
                    self.stops['ul_east_gate']
                ),
                'from_ul': self._get_journey_info(
                    self.stops['ul_student_centre'],
                    self.stops['hazel_hall']
                )
            }
            return metrics
        except Exception as e:
            logger.error(f"Error collecting bus metrics: {str(e)}")
            raise RuntimeError(f"Error collecting bus metrics: {str(e)}")

if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Test the collector
    collector = BusCollector()
    try:
        metrics = collector.safe_collect()
        if 'error' in metrics:
            print(f"Error: {metrics['error']}")
        else:
            print("Bus Metrics:")
            print(f"To UL: {metrics['to_ul']['minutes_until_arrival']} minutes")
            print(f"From UL: {metrics['from_ul']['minutes_until_arrival']} minutes")
    except Exception as e:
        print(f"Error: {str(e)}")
