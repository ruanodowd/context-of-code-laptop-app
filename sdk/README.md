# Metrics SDK

A lightweight SDK for collecting and sending metrics data to a server.

## Features

- Simple API for collecting and sending metrics
- Automatic buffering of metrics when server is unavailable
- Retry mechanism for failed requests
- Support for custom collectors
- Configurable via environment variables

## Usage

### Basic Usage

```python
from sdk import register_collector, collect_and_send
from sdk.collector import Collector

# Create a custom collector
class MyCollector(Collector):
    def collect(self):
        # Collect metrics
        return {
            'value': 42,
            'status': 'ok'
        }

# Register the collector
register_collector(MyCollector())

# Collect and send metrics
collect_and_send()
```

### Using the MetricsManager

```python
from sdk import MetricsManager
from sdk.collector import Collector

# Create a custom collector
class MyCollector(Collector):
    def collect(self):
        # Collect metrics
        return {
            'value': 42,
            'status': 'ok'
        }

# Create a metrics manager
manager = MetricsManager()

# Register the collector
manager.register_collector(MyCollector())

# Collect and send metrics
manager.collect_and_send()
```

### Using the MetricsClient Directly

```python
from sdk import MetricsClient

# Create a metrics client
client = MetricsClient(
    server_url='https://your-metrics-server.com/api/metrics',
    api_key='your-api-key',
    client_id='your-client-id'
)

# Create a metrics batch
metrics_batch = client.create_metrics_batch({
    'MyCollector': {
        'value': 42,
        'status': 'ok'
    }
})

# Send metrics
client.send_metrics(metrics_batch)
```

## Configuration

The SDK can be configured via environment variables:

- `METRICS_SERVER_URL`: URL of the metrics server
- `METRICS_API_KEY`: API key for authentication
- `METRICS_CLIENT_ID`: Client ID
- `METRICS_COLLECTION_INTERVAL`: Interval between collections in seconds
- `METRICS_BUFFER_FILE`: Path to the buffer file
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)

## Creating Custom Collectors

To create a custom collector, inherit from the `Collector` base class and implement the `collect()` method:

```python
from sdk.collector import Collector

class MyCollector(Collector):
    def collect(self):
        # Collect metrics
        return {
            'value': 42,
            'status': 'ok'
        }
```

The `collect()` method should return a dictionary of metrics. If an error occurs, it should raise an exception, which will be caught by the `safe_collect()` method and returned as an error dictionary.
