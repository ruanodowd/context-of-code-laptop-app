import os
import subprocess
import json
import logging
import time
from typing import Dict, Any
from sdk.collector import Collector

logger = logging.getLogger(__name__)

class BatteryCollector(Collector):
    """Collector for battery metrics."""
    
    def __init__(self, dry_run: bool = False):
        self.battery_path = '/sys/class/power_supply/BAT0'
        self.dry_run = dry_run
    
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

    def format_metrics(self, raw_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format the raw battery metrics for the metrics SDK.
        
        Args:
            raw_metrics (dict): Raw battery metrics from collect()
            
        Returns:
            dict: Formatted metrics ready for SDK
        """
        if 'error' in raw_metrics:
            return {'error': raw_metrics['error']}
            
        # Use custom metric name if set, otherwise use default
        metric_name = self.metric_name or 'battery_percentage'
            
        metrics_data = {
            'name': metric_name,
            'value': raw_metrics['metric'],
            'unit': '%',
            'description': 'Battery charge percentage',
            'metadata': {
                'collector_type': 'battery',
                'is_charging': raw_metrics.get('is_charging', False),
                'collection_time': time.time()
            }
        }
        
        return metrics_data
    
    def collect_and_send(self) -> Dict[str, Any]:
        """
        Collect, format and send battery metrics.
        
        Returns:
            dict: Battery metrics or dict with error information
        """
        # Call the base class implementation with our dry_run setting
        return super().collect_and_send(dry_run=self.dry_run)


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    collector = BatteryCollector(dry_run=True)
    result = collector.collect_and_send()
    
    if 'error' not in result:
        print("Successfully collected battery metrics: %s%%" % result['metric'])
    else:
        print("Failed to collect battery metrics: %s" % result['error'])