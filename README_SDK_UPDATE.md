# Metrics SDK Update

This document explains the updates made to the Metrics SDK to make it compatible with the web app.

## Changes Made

1. **Configuration Updates**:
   - Updated the default server URL to point to the web app's metrics endpoint (`http://localhost:8000/api/metrics`)
   - Set a default API key for authentication

2. **SDK Implementation Updates**:
   - Added support for metric types management (loading, creating, and caching)
   - Updated the data format to match the web app's expected schema
   - Improved bulk sending of buffered metrics
   - Enhanced error handling and logging
   - Removed the client ID header as it's not used by the web app

3. **New Features**:
   - Automatic metric type registration
   - Better health checking by querying the metric types endpoint
   - Improved buffering and retry logic

## How to Use the Updated SDK

### Basic Usage

```python
from sdk import metrics_sdk

# Send a simple metric
metrics_sdk.send_metrics({
    'name': 'cpu_usage',
    'value': 75.5,
    'unit': '%',
    'description': 'CPU usage percentage'
})
```

### Configuration

You can configure the SDK using environment variables:

- `METRICS_SERVER_URL`: URL of the metrics server (default: `http://localhost:8000/api/metrics`)
- `METRICS_API_KEY`: API key for authentication (default: `default-api-key`)
- `METRICS_CLIENT_ID`: Client ID for identifying the source (default: `default-client`)
- `METRICS_BUFFER_FILE`: Path to the buffer file (default: `metrics_buffer.json`)
- `LOG_LEVEL`: Logging level (default: `INFO`)

### Example Script

An example script is provided in `example_usage.py` that demonstrates how to collect and send system metrics using the updated SDK.

To run the example:

```bash
python example_usage.py
```

## Web App Compatibility

The SDK is now compatible with the web app's API endpoints:

- `/api/metrics/` - For sending individual metrics
- `/api/metrics/bulk` - For sending multiple metrics at once
- `/api/metric-types/` - For managing metric types

The SDK automatically handles metric type registration and formats the data according to the web app's expected schema.

## Troubleshooting

If you encounter issues:

1. Check that the web app is running and accessible
2. Verify that the API key matches between the SDK and web app
3. Look at the logs for detailed error messages
4. Check the buffer file (`metrics_buffer.json`) for any buffered metrics that failed to send
