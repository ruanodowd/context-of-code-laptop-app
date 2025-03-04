# Metrics Collection SDK

This SDK provides a framework for collecting and sending metrics to a central server. The SDK has been updated to work with the new data model that includes `MetricType`, `Source`, `Metric`, and `MetricMetadata` entities.

## Data Model

The server's data model has been updated to the following structure:

### MetricType
- **id**: UUID primary key
- **name**: Unique identifier for the metric type (e.g., 'cpu_usage', 'memory_usage')
- **description**: Detailed description of what this metric represents
- **unit**: The unit of measurement (e.g., '%', 'MB', 'requests/sec')
- **created_at**: When this metric type was defined
- **is_active**: Whether this metric type is currently active

### Source
- **id**: UUID primary key
- **name**: Name of the source (e.g., 'server1', 'process2')
- **description**: Detailed description of the source
- **ip_address**: IP address of the source (optional)
- **created_at**: When this source was defined
- **is_active**: Whether this source is currently active

### Metric
- **id**: UUID primary key
- **metric_type_id**: Reference to the metric type definition
- **source_id**: Reference to the source definition
- **value**: The numerical value of the metric
- **recorded_at**: When the metric was recorded

### MetricMetadata
- **id**: UUID primary key
- **metric_id**: Reference to the metric
- **key**: Metadata key
- **value**: Metadata value
- **created_at**: When this metadata was created

## SDK Usage

### Basic Usage

```python
from sdk import metrics_sdk

# Send a simple metric
metrics_sdk.send_metrics({
    'name': 'cpu_usage',
    'value': 45.2,
    'unit': '%',
    'description': 'CPU usage percentage'
})

# Send a metric with metadata
metrics_sdk.send_metrics({
    'name': 'memory_usage',
    'value': 1024.5,
    'unit': 'MB',
    'description': 'Memory usage in megabytes',
    'metadata': {
        'process_name': 'web_server',
        'pid': 12345
    }
})
```

### Configuration

The SDK can be configured using environment variables:

- `METRICS_SERVER_URL`: URL of the metrics server (default: http://localhost:8000/api/metrics)
- `METRICS_API_KEY`: API key for authentication (default: metrics-api-key-2025)
- `METRICS_SOURCE_NAME`: Name of the source (default: hostname)
- `METRICS_SOURCE_DESCRIPTION`: Description of the source (default: "Metrics from {hostname}")
- `METRICS_SOURCE_IP`: IP address of the source (default: None, detected by server)
- `METRICS_BUFFER_FILE`: Path to the buffer file (default: metrics_buffer.json)
- `LOG_LEVEL`: Logging level (default: INFO)

### Custom Client

You can create a custom client with specific configuration:

```python
from sdk.metrics_sdk import MetricsClient

custom_client = MetricsClient(
    server_url='http://metrics-server.example.com/api/metrics',
    api_key='your-api-key',
    source_name='custom-source',
    source_description='Custom metrics source',
    source_ip='192.168.1.100'
)

# Use the custom client
custom_client.send_metrics({
    'name': 'custom_metric',
    'value': 123.45,
    'unit': 'count'
})
```

## Collectors

The SDK includes a base `Collector` class that can be extended to create custom metric collectors. Each collector should implement the `collect()` method that returns a dictionary of metrics.

Example:

```python
from sdk.collector import Collector

class CPUCollector(Collector):
    def collect(self):
        # Collect CPU metrics
        cpu_usage = get_cpu_usage()  # Your implementation
        return {
            'metric': cpu_usage,
            'timestamp': None  # Will be added by SDK
        }
```

## Metrics Manager

The `MetricsManager` class provides a way to manage multiple collectors and collect metrics from all of them at once.

```python
from sdk.metrics_manager import MetricsManager
from my_collectors import CPUCollector, MemoryCollector

# Create a manager
manager = MetricsManager()

# Register collectors
manager.register_collector(CPUCollector())
manager.register_collector(MemoryCollector())

# Collect and send metrics from all collectors
manager.collect_and_send()
```

## Error Handling and Buffering

The SDK includes automatic buffering of metrics when the server is unavailable. Buffered metrics will be sent when the server becomes available again.

## CLI Application

The repository includes a command-line interface (CLI) application (`new_main.py`) that allows you to collect and send metrics with customizable options.

### Usage

```bash
./new_main.py [options]
```

### Options

#### General Options
- `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Set the logging level (default: INFO)
- `--interval INTERVAL`: Interval between collections in seconds (default: 60)
- `--count COUNT`: Number of collection rounds (0 for infinite) (default: 1)
- `--dry-run`: Do not send metrics to server, just log them

#### Collector Options
- `--collect-battery`: Collect battery metrics
- `--bus-routes [BUS_ROUTES ...]`: Bus routes to monitor in format "from_stop:to_stop"

#### SDK Configuration
- `--server-url SERVER_URL`: URL of the metrics server
- `--api-key API_KEY`: API key for authentication
- `--source-name SOURCE_NAME`: Source name for metrics
- `--source-description SOURCE_DESCRIPTION`: Description of the source
- `--source-ip SOURCE_IP`: IP address of the source
- `--buffer-file BUFFER_FILE`: Path to the buffer file
- `--max-retries MAX_RETRIES`: Maximum number of retries
- `--retry-delay RETRY_DELAY`: Delay between retries in seconds
- `--request-timeout REQUEST_TIMEOUT`: Request timeout in seconds

### Examples

#### Collect Battery Metrics Once
```bash
./new_main.py --collect-battery
```

#### Collect Bus Information Every 5 Minutes
```bash
./new_main.py --bus-routes "T310 UL East Gate / An Geata Thoir:T310 Hazel Hall Estate" "T310 Beechfield:T310 UL East Gate / An Geata Thoir" --interval 300 --count 0
```

#### Collect All Metrics with Custom Source Name
```bash
./new_main.py --collect-battery --bus-routes "T310 UL East Gate / An Geata Thoir:T310 Hazel Hall Estate" --source-name "my-laptop" --source-description "My Personal Laptop"
```

#### Dry Run to Test Configuration
```bash
./new_main.py --collect-battery --bus-routes "T310 UL East Gate / An Geata Thoir:T310 Hazel Hall Estate" --dry-run
```

## Command Relay System

The application includes a command relay system that allows the client to receive and execute commands from a server, even when behind NAT, firewalls, or restrictive networks like university networks. This system uses a polling approach where the client periodically checks for new commands from the server.

### Supported Commands

- `shutdown_wsl`: Shuts down the Windows Subsystem for Linux
- `ping`: Simple ping command for testing connectivity

### Usage

To enable the command relay system, use the following options:

```bash
./main.py --enable-command-relay --command-server-url "https://your-server.com/api" --poll-interval 30 --collect-battery
```

### Command Relay Options

- `--enable-command-relay`: Enable the command relay system
- `--command-server-url`: Base URL of the command server API
- `--poll-interval`: Interval between polling for commands in seconds (default: 30)

### How It Works

1. The client registers with the server on startup
2. The client periodically polls the server for new commands
3. When a command is received, the client executes it and sends the result back to the server
4. The client maintains a heartbeat with the server to indicate it's still active

This approach works well in restricted network environments since it only requires the client to make outbound HTTP requests, which are typically allowed even in restrictive networks.
