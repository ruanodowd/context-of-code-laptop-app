# Metrics Collection Client

A Python-based metrics collection client that gathers various system metrics and sends them to a centralized web application.

## Features

- Modular collector system for different types of metrics
- Automatic retry mechanism for failed transmissions
- Local buffering of metrics when server is unavailable
- Configurable collection intervals
- UTC timestamp synchronization
- Secure API key authentication

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Set the following environment variables or modify `client/config.py`:

- `METRICS_SERVER_URL`: URL of your metrics server
- `METRICS_API_KEY`: API key for authentication
- `METRICS_CLIENT_ID`: Unique identifier for this client
- `METRICS_COLLECTION_INTERVAL`: Collection interval in seconds (default: 300)
- `LOG_LEVEL`: Logging level (default: INFO)

## Running the Client

```bash
python main.py
```

## Adding New Collectors

1. Create a new directory under `collectors/` for your collector
2. Implement a collector class with a `collect()` method
3. Register your collector in `main.py`

## Architecture

- `collectors/`: Individual metric collectors
- `client/`: Core client functionality
  - `config.py`: Configuration settings
  - `http_client.py`: HTTP communication with server
  - `metrics_buffer.py`: Local metric buffering
  - `aggregator.py`: Combines metrics from collectors
- `main.py`: Application entry point

## Error Handling

- Failed transmissions are automatically retried
- Metrics are buffered locally when server is unavailable
- All errors are logged for debugging

## Contributing

1. Create a new collector in the `collectors/` directory
2. Ensure it implements the required `collect()` method
3. Add any necessary configuration to `config.py`
4. Register the collector in `main.py`

## License

MIT