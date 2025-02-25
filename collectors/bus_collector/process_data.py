import json
import logging
import requests
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

api_link = "https://ticketbooking.dublincoach.ie/MobileAPI/MobileBooking/GetJourneyList?FromStageName=T310 UL Student Centre / Ionad na Mac L&ToStageName=T310 Hazel Hall Estate&JourneyType=0&RouteID=0&JrEndStageID=0&IsStageSelection=1"

#getting home
origin = "T310 UL Student Centre / Ionad na Mac L"
destination = "T310 Hazel Hall Estate"

# getting to UL
origin = "T310 UL Student Centre / Ionad na Mac Leinn"
destination = "T310 UL East Gate / An Geata Thoir"
# its probably best to use the arrival time in UL to measure lateness


# convert data looking like this "1 hr 29 min" to an integer representing the number of minutes
# it may be listed as "arrived", which should be treated as 0 minutes
def string_time_to_time(time: str) -> int:
    """Convert string time format to minutes
    Args:
        time (str): Time string like "1 hr 29 min" or "Arrived"
    Returns:
        int: Number of minutes
    """
    if time == "Arrived":
        return 0
    time = time.split()
    try:
        if len(time) == 4:  # Format: "1 hr 29 min"
            return int(time[0]) * 60 + int(time[2])
        return int(time[0])  # Format: "29 min"
    except (IndexError, ValueError) as e:
        logger.error(f"Error parsing time string '{time}': {str(e)}")
        raise ValueError(f"Invalid time format: {time}")

def get_bus_arrival_time(destination: str, origin: str) -> int:
    """Get the arrival time for a bus from origin to destination
    Args:
        destination (str): Destination stop name
        origin (str): Origin stop name
    Returns:
        int: Minutes until arrival
    Raises:
        ValueError: If bus hasn't departed or data format is invalid
        RequestException: If API request fails
    """
    api_link = f"https://ticketbooking.dublincoach.ie/MobileAPI/MobileBooking/GetJourneyList?FromStageName={origin}&ToStageName={destination}&JourneyType=0&RouteID=0&JrEndStageID=0&IsStageSelection=1"
    
    try:
        logger.debug(f"Fetching bus data for {origin} to {destination}")
        response = requests.get(api_link, timeout=10)
        response.raise_for_status()
        data = response.text
        
        parsed_data = json.loads(data) # loads is bad, probably should use a library like json
        if not parsed_data.get('Data', {}).get('JourneyList'):
            raise ValueError("No journey data available")
            
        journey = parsed_data['Data']['JourneyList'][0]
        if journey['JourneyID'] == 0:
            raise ValueError("The bus has not departed yet")
            
        minutes = string_time_to_time(journey['LeavingIn'])
        logger.debug(f"Bus from {origin} to {destination} arriving in {minutes} minutes")
        return minutes
        
    except RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        raise
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error parsing API response: {str(e)}")
        raise ValueError(f"Invalid API response: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error getting bus arrival time: {str(e)}")
        raise
