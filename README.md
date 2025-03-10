# Laptop Metrics Collection Application

A comprehensive solution for collecting, monitoring, and sending various system metrics from laptops to a central server. The application features a flexible SDK, customizable collectors, and a powerful command-line interface.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Using the CLI](#using-the-cli)
  - [Basic Usage](#basic-usage)
  - [Configuration Options](#configuration-options)
  - [Using JSON Configuration Files](#using-json-configuration-files)
  - [Command Relay](#command-relay)
- [Metrics SDK](#metrics-sdk)
  - [Data Model](#data-model)
  - [Key Components](#key-components)
  - [Basic SDK Usage](#basic-sdk-usage)
  - [Custom Client](#custom-client)
  - [Environment Variables](#environment-variables)
- [Collectors](#collectors)
  - [Available Collectors](#available-collectors)
  - [Creating Custom Collectors](#creating-custom-collectors)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

## Overview

This application provides a framework for collecting system metrics from laptops and sending them to a centralized metrics server. It's designed to be both simple to use for basic use cases and highly customizable for more advanced scenarios.

## Features

- **Modular Collector Architecture**: Easily add or customize what metrics you want to collect
- **Flexible SDK**: Robust SDK for programmatic use with buffering, retries, and error handling
- **Command-line Interface**: Comprehensive CLI for configuration and operation
- **JSON Configuration Support**: Load configurations from JSON files
- **Remote Command Execution**: Receive and execute commands from a central server
- **Automatic Metric Type Management**: Register and manage metric types automatically
- **Buffering and Retries**: Store metrics locally when server is unavailable
- **Metadata Support**: Add detailed metadata to your metrics
- **Dry Run Mode**: Test configurations without sending metrics

## Installation

```bash
# Clone the repository
git clone https://github.com/your-organization/laptop-metrics-app.git
cd laptop-metrics-app

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

The simplest way to get started is to use the command-line interface:

```bash
# Collect battery metrics once
python main.py --collectors battery --count 1

# Continuously collect battery metrics every 60 seconds
python main.py --collectors battery --interval 60

# Collect both battery and bus arrival metrics
python main.py --collectors battery bus:from_stage_name=Station1,to_stage_name=Station2
```

## Using the CLI

### Basic Usage

The application provides a comprehensive command-line interface:

```bash
python main.py --collectors [COLLECTORS...] [OPTIONS]
```

### Configuration Options

#### Collection Options
- `--collectors [COLLECTORS...]`: List of collectors to run in format "type:param1=value1,param2=value2"
- `--interval INTERVAL`: Interval between collections in seconds (default: 60)
- `--count COUNT`: Number of collection rounds (0 for infinite) (default: 0)
- `--dry-run`: Do not send metrics to server, just log them

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

#### Command Relay Options
- `--enable-command-relay`: Enable command relay to receive commands from server
- `--command-server-url COMMAND_SERVER_URL`: Base URL of the command server API
- `--poll-interval POLL_INTERVAL`: Interval between polling for commands in seconds

#### Other Options
- `--config-file CONFIG_FILE`: Path to JSON configuration file
- `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Set logging level

### Using JSON Configuration Files

You can store your configuration in a JSON file:

```json
{
    "collectors": ["battery", "bus:from_stage_name=Station1,to_stage_name=Station2"],
    "interval": 120,
    "count": 5,
    "log-level": "INFO",
    "server-url": "http://localhost:8000",
    "source-name": "Laptop-Config-File",
    "dry-run": false
}
```

And use it with:

```bash
python main.py --config-file your_config.json
```

Command-line arguments take precedence over values in the JSON file.

### Command Relay

The Command Relay feature allows the application to receive and execute commands from a central server:

```bash
python main.py --collectors battery --enable-command-relay --command-server-url http://command-server.example.com
```

## Metrics SDK

The SDK provides a framework for collecting and sending metrics to a central server.

### Data Model

The server's data model has the following structure:

#### MetricType
- **id**: UUID primary key
- **name**: Unique identifier for the metric type (e.g., 'cpu_usage', 'memory_usage')
- **description**: Detailed description of what this metric represents
- **unit**: The unit of measurement (e.g., '%', 'MB', 'requests/sec')
- **created_at**: When this metric type was defined
- **is_active**: Whether this metric type is currently active

#### Source
- **id**: UUID primary key
- **name**: Name of the source (e.g., 'server1', 'process2')
- **description**: Detailed description of the source
- **ip_address**: IP address of the source (optional)
- **created_at**: When this source was defined
- **is_active**: Whether this source is currently active

#### Metric
- **id**: UUID primary key
- **metric_type_id**: Reference to the metric type definition
- **source_id**: Reference to the source definition
- **value**: The numerical value of the metric
- **recorded_at**: When the metric was recorded

#### MetricMetadata
- **id**: UUID primary key
- **metric_id**: Reference to the metric
- **key**: Metadata key
- **value**: Metadata value
- **created_at**: When this metadata was created

### Key Components

- **MetricsClient**: Handles the communication with the metrics server
- **MetricsManager**: Manages collectors and orchestrates the collection process
- **Collector**: Base class for implementing metric collectors
- **CommandRelayClient**: Receives and executes commands from a central server

### Basic SDK Usage

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

### Environment Variables

The SDK can be configured using environment variables:

- `METRICS_SERVER_URL`: URL of the metrics server
- `METRICS_API_KEY`: API key for authentication
- `METRICS_SOURCE_NAME`: Name of the source
- `METRICS_SOURCE_DESCRIPTION`: Description of the source
- `METRICS_SOURCE_IP`: IP address of the source
- `METRICS_BUFFER_FILE`: Path to the buffer file
- `LOG_LEVEL`: Logging level

## Collectors

Collectors are responsible for gathering specific metrics. The application comes with several built-in collectors and allows you to create custom ones.

### Available Collectors

#### Battery Collector

Collects battery metrics such as charge percentage, charging status, and remaining time.

```bash
python main.py --collectors battery
```

#### Bus Collector

Collects bus arrival time metrics for specified routes.

```bash
python main.py --collectors "bus:from_stage_name=Station1,to_stage_name=Station2"
```

### Creating Custom Collectors

To create a custom collector, inherit from the `Collector` base class and implement the required methods:

```python
from sdk.collector import Collector
from typing import Dict, Any

class MyCustomCollector(Collector):
    def __init__(self, param1="default", param2=42):
        self.param1 = param1
        self.param2 = param2
    
    def collect(self) -> Dict[str, Any]:
        # Implement your metric collection logic here
        return {
            'my_value': 42,
            'status': 'ok'
        }
    
    def format_metrics(self, raw_metrics):
        return {
            'name': 'my_custom_metric',
            'value': raw_metrics['my_value'],
            'unit': 'count',
            'description': 'My custom metric',
            'metadata': {
                'param1': self.param1,
                'param2': self.param2
            }
        }
```

Register your collector by placing it in the `collectors` directory with the appropriate structure.

## Troubleshooting

Common issues and their solutions:

1. **Server Connection Issues**:
   - Verify the server URL is correct
   - Check network connectivity
   - Ensure the API key is valid

2. **Collector Errors**:
   - Check collector parameters
   - Verify the services the collector depends on are available
   - Look for specific error messages in the logs

3. **Configuration Issues**:
   - Validate JSON syntax in configuration files
   - Check for typos in parameter names
   - Ensure all required parameters are provided

## Examples

### Collecting Multiple Metrics

```bash
python main.py --collectors battery "bus:from_stage_name=Station1,to_stage_name=Station2" --interval 300 --count 10
```

### Using Dry Run Mode

```bash
python main.py --collectors battery --dry-run
```

### Creating a Custom Collector in Code

```python
from sdk.collector import Collector
from sdk import metrics_sdk

class WeatherCollector(Collector):
    def __init__(self, location="New York"):
        self.location = location
    
    def collect(self):
        # Simulate getting weather data
        return {
            'temperature': 22.5,
            'humidity': 65,
            'location': self.location
        }
    
    def format_metrics(self, raw_metrics):
        return {
            'name': f'weather_temperature_{self.location.lower().replace(" ", "_")}',
            'value': raw_metrics['temperature'],
            'unit': 'C',
            'description': f'Temperature in {self.location}',
            'metadata': {
                'humidity': raw_metrics['humidity'],
                'location': self.location
            }
        }

# Use the collector
metrics_sdk.init_client(source_name="Weather Station")
weather_collector = WeatherCollector(location="San Francisco")
metrics = weather_collector.collect()
formatted_metrics = weather_collector.format_metrics(metrics)
metrics_sdk.send_metrics(formatted_metrics)
```
