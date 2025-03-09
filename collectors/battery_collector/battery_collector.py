import os
import subprocess
import json
import logging
from sdk.collector import Collector

logger = logging.getLogger(__name__)

class BatteryCollector(Collector):
    """Collector for battery metrics."""
    
    def __init__(self):
        self.battery_path = '/sys/class/power_supply/BAT0'
    
    def _is_wsl(self):
        """Check if running under Windows Subsystem for Linux."""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except IOError:
            return False
    
    def collect(self):
        """Collect battery metrics.
        
        Returns:
            dict: Battery information including percentage, charging status, and any errors
        """
        try:
            if self._is_wsl():
                return self._collect_wsl()
            return self._collect_linux()
        except Exception as e:
            logger.error("Error collecting battery metrics: %s", str(e))
            raise RuntimeError(f"Error collecting battery metrics: {str(e)}")
    
    def _collect_wsl(self):
        """Collect battery metrics in WSL environment."""
        try:
            # PowerShell command to get battery information
            cmd = 'powershell.exe -command "(Get-WmiObject Win32_Battery | Select-Object -Property EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json)"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0 and result.stdout.strip():
                battery_data = json.loads(result.stdout)
                percentage = battery_data['EstimatedChargeRemaining']
                
                return {
                    'metric': percentage,
                    'timestamp': None  # Will be added by aggregator
                }
            else:
                raise RuntimeError('Could not retrieve battery information from Windows')
                
        except Exception as e:
            raise RuntimeError(f'Error getting battery information: {str(e)}')
    
    def _collect_linux(self):
        """Collect battery metrics in Linux environment."""
        try:
            with open(os.path.join(self.battery_path, 'capacity'), 'r') as f:
                percentage = int(f.read().strip())
            
            with open(os.path.join(self.battery_path, 'status'), 'r') as f:
                status = f.read().strip()
            
            # Include charging status in the output
            is_charging = status == "Charging"
            
            return {
                'metric': percentage,
                'is_charging': is_charging,
                'timestamp': None  # Will be added by aggregator
            }
        except FileNotFoundError:
            raise RuntimeError('Battery information not available')

if __name__ == '__main__':
    collector = BatteryCollector()
    battery_info = collector.safe_collect()
    if 'error' in battery_info:
        print(battery_info['error'])
    else:
        print("Battery percentage: %s%%" % battery_info['metric'])