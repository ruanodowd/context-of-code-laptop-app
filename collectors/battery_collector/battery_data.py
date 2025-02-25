import os
import subprocess
import json

def is_wsl():
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False

def get_battery_info():
    if is_wsl():
        try:
            # PowerShell command to get battery information
            cmd = 'powershell.exe -command "(Get-WmiObject Win32_Battery | Select-Object -Property EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json)"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0 and result.stdout.strip():
                battery_data = json.loads(result.stdout)
                
                # BatteryStatus: 1 = Discharging, 2 = AC Power
                percentage = battery_data['EstimatedChargeRemaining']
                is_charging = battery_data['BatteryStatus'] == 2
                status = "Charging" if is_charging else "Discharging"
                
                return {
                    'percentage': percentage,
                    'is_charging': is_charging,
                    'status': status
                }
            else:
                return {'error': 'Could not retrieve battery information from Windows'}
                
        except Exception as e:
            return {'error': f'Error getting battery information: {str(e)}'}
    
    # Original Linux implementation
    battery_path = '/sys/class/power_supply/BAT0'
    try:
        with open(os.path.join(battery_path, 'capacity'), 'r') as f:
            percentage = int(f.read().strip())
        
        with open(os.path.join(battery_path, 'status'), 'r') as f:
            status = f.read().strip()
        
        is_charging = status == "Charging"
        
        return {
            'percentage': percentage,
            'is_charging': is_charging,
            'status': status
        }
    except FileNotFoundError:
        return {'error': 'Battery information not available'}

if __name__ == '__main__':
    battery_info = get_battery_info()
    if 'error' in battery_info:
        print(battery_info['error'])
    else:
        print(f"Battery percentage: {battery_info['percentage']}%")
        print(f"Charging status: {'Charging' if battery_info['is_charging'] else 'Not charging'}")
        print(f"Current status: {battery_info['status']}")