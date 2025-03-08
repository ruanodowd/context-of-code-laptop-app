#!/usr/bin/env python3
"""
Command Relay Module for receiving and executing commands from a server.
This module uses a polling approach to fetch commands from the server,
making it suitable for clients behind NAT, firewalls, or restrictive networks.
"""
import json
import logging
import os
import subprocess
import sys
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Callable

import requests

from sdk import config

# Setup logging
logger = logging.getLogger(__name__)

class CommandExecutor:
    """Executes commands received from the server."""
    
    def __init__(self):
        """Initialize the command executor."""
        # Define allowed commands and their handlers
        self.command_handlers = {
            "shutdown_wsl": self._handle_shutdown_wsl,
            "ping": self._handle_ping,
            # Add more commands as needed
        }
    
    def execute_command(self, command: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a command with the given parameters.
        
        Args:
            command (str): The command to execute
            params (dict, optional): Parameters for the command
            
        Returns:
            dict: Result of the command execution
        """
        if command not in self.command_handlers:
            logger.warning(f"Unknown command: {command}")
            return {
                "status": "error",
                "message": f"Unknown command: {command}"
            }
        
        try:
            handler = self.command_handlers[command]
            return handler(params or {})
        except Exception as e:
            logger.error(f"Error executing command {command}: {str(e)}")
            return {
                "status": "error",
                "message": f"Error executing command: {str(e)}"
            }
    
    def _handle_shutdown_wsl(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the shutdown_wsl command.
        
        Args:
            params (dict): Parameters for the command
            
        Returns:
            dict: Result of the command execution
        """
        logger.info("Executing shutdown WSL command")
        try:
            # Execute the wsl.exe --shutdown command
            result = subprocess.run(
                ["wsl.exe", "--shutdown"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    "status": "success",
                    "message": "WSL shutdown successful"
                }
            else:
                return {
                    "status": "error",
                    "message": f"WSL shutdown failed: {result.stderr}"
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "message": "WSL shutdown command timed out"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error during WSL shutdown: {str(e)}"
            }
    
    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the ping command.
        
        Args:
            params (dict): Parameters for the command
            
        Returns:
            dict: Result of the command execution
        """
        return {
            "status": "success",
            "message": "pong",
            "timestamp": time.time()
        }


class CommandRelayClient:
    """Client for polling commands from the server."""
    
    def __init__(
        self,
        server_url: Optional[str] = None,
        api_key: Optional[str] = None,
        client_id: Optional[str] = None,
        poll_interval: int = 30,
        last_command_id: Optional[str] = None
    ):
        """
        Initialize the command relay client.
        
        Args:
            server_url (str, optional): Base URL of the command server
            api_key (str, optional): API key for authentication
            client_id (str, optional): Unique ID for this client
            poll_interval (int): Seconds between polling for commands
            last_command_id (str, optional): ID of the last processed command
        """
        self.server_url = server_url or os.environ.get("COMMAND_SERVER_URL", "http://localhost:8000")
        self.api_key = api_key or os.environ.get("COMMAND_API_KEY", config.API_KEY)
        self.client_id = client_id or os.environ.get("CLIENT_ID", str(uuid.uuid4()))
        self.poll_interval = poll_interval
        self.last_command_id = last_command_id
        
        self.executor = CommandExecutor()
        self.running = False
        self.thread = None
        
        # File to store the last processed command ID
        self.state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "command_relay_state.json")
        self._load_state()
    
    def _load_state(self) -> None:
        """Load the state from file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_command_id = state.get("last_command_id", self.last_command_id)
                    logger.debug(f"Loaded state: last_command_id={self.last_command_id}")
            except (IOError, json.JSONDecodeError) as e:
                logger.error(f"Failed to load state: {str(e)}")
    
    def _save_state(self) -> None:
        """Save the state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    "last_command_id": self.last_command_id,
                    "client_id": self.client_id,
                    "updated_at": time.time()
                }, f)
        except IOError as e:
            logger.error(f"Failed to save state: {str(e)}")
    
    def _poll_commands(self) -> None:
        """Poll for commands from the server."""
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        params = {
            "client_id": self.client_id
        }
        
        try:
            response = requests.get(
                f"{self.server_url.rstrip('/')}/api/commands/pending",
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                commands = response.json()
                
                if commands:
                    logger.info(f"Received {len(commands)} new command(s)")
                    logger.debug(f"Command data: {commands}")
                    
                    for cmd in commands:
                        # Extract command details - handle different possible formats
                        command_id = cmd.get("id") or cmd.get("command_id")
                        command = cmd.get("command_type") or cmd.get("command")
                        params = cmd.get("params", {})
                        
                        # Debug log the raw command data
                        logger.debug(f"Raw command data: {cmd}")
                        
                        # Skip commands with missing ID or command type
                        if not command_id or not command:
                            logger.warning(f"Skipping command with missing ID or command type: {cmd}")
                            continue
                            
                        logger.info(f"Processing command: {command} (ID: {command_id})")
                        
                        # Execute the command
                        result = self.executor.execute_command(command, params)
                        
                        # Send the result back to the server
                        self._send_command_result(command_id, result)
                        
                        # Update the last command ID
                        self.last_command_id = command_id
                        self._save_state()
                
                # Send heartbeat even if no commands
                self._send_heartbeat()
                
            elif response.status_code == 401:
                logger.error("Authentication failed. Check your API key.")
            elif response.status_code == 404:
                logger.error("Command endpoint not found. Check your server URL.")
            else:
                logger.error(f"Failed to poll commands: {response.status_code} - {response.text}")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error polling commands: {str(e)}")
    
    def _send_command_result(self, command_id: str, result: Dict[str, Any]) -> bool:
        """
        Send command execution result to the server.
        
        Args:
            command_id (str): ID of the command
            result (dict): Result of the command execution
            
        Returns:
            bool: True if successful, False otherwise
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "client_id": self.client_id,
            "command_id": command_id,
            "result": result,
            "timestamp": time.time()
        }
        
        try:
            response = requests.post(
                f"{self.server_url.rstrip('/')}/api/commands/results",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent result for command {command_id}")
                return True
            else:
                logger.error(f"Failed to send result: {response.status_code} - {response.text}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending result: {str(e)}")
            return False
    
    def _send_heartbeat(self) -> bool:
        """
        Send a heartbeat to the server.
        
        Returns:
            bool: True if successful, False otherwise
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        data = {
            "client_id": self.client_id,
            "timestamp": time.time(),
            "status": "active",
            "last_command_id": self.last_command_id
        }
        
        try:
            response = requests.post(
                f"{self.server_url.rstrip('/')}/api/clients/heartbeat",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.debug("Successfully sent heartbeat")
                return True
            else:
                logger.warning(f"Failed to send heartbeat: {response.status_code} - {response.text}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending heartbeat: {str(e)}")
            return False
    
    def _run_polling_loop(self) -> None:
        """Run the polling loop."""
        logger.info(f"Starting command polling with interval {self.poll_interval} seconds")
        
        # Register with the server
        self._register_client()
        
        while self.running:
            try:
                self._poll_commands()
            except Exception as e:
                logger.error(f"Error in polling loop: {str(e)}")
            
            # Sleep until next poll
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def _register_client(self) -> bool:
        """
        Register this client with the server.
        
        Returns:
            bool: True if successful, False otherwise
        """
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Try to get a meaningful hostname
        hostname = os.environ.get("HOSTNAME", None)
        if not hostname:
            try:
                import socket
                hostname = socket.gethostname()
            except:
                hostname = "unknown"
                
        data = {
            "client_id": self.client_id,
            "client_type": "metrics_client",
            "hostname": hostname,
            "timestamp": time.time()
        }
        
        try:
            response = requests.post(
                f"{self.server_url.rstrip('/')}/api/clients/register",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully registered client with ID: {self.client_id}")
                return True
            else:
                logger.error(f"Failed to register client: {response.status_code} - {response.text}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error registering client: {str(e)}")
            return False
    
    def start(self) -> None:
        """Start the command relay client in a separate thread."""
        if self.running:
            logger.warning("Command relay client is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_polling_loop, daemon=True)
        self.thread.start()
        logger.info("Command relay client started")
    
    def stop(self) -> None:
        """Stop the command relay client."""
        if not self.running:
            logger.warning("Command relay client is not running")
            return
        
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        
        logger.info("Command relay client stopped")


# Singleton instance for easy import
default_client = None

def start_command_relay(
    server_url: Optional[str] = None,
    api_key: Optional[str] = None,
    client_id: Optional[str] = None,
    poll_interval: int = 30
) -> CommandRelayClient:
    """
    Start the command relay client.
    
    Args:
        server_url (str, optional): Base URL of the command server
        api_key (str, optional): API key for authentication
        client_id (str, optional): Unique ID for this client
        poll_interval (int): Seconds between polling for commands
        
    Returns:
        CommandRelayClient: The command relay client instance
    """
    global default_client
    
    if default_client is None:
        default_client = CommandRelayClient(
            server_url=server_url,
            api_key=api_key,
            client_id=client_id,
            poll_interval=poll_interval
        )
    
    default_client.start()
    return default_client

def stop_command_relay() -> None:
    """Stop the command relay client."""
    global default_client
    
    if default_client:
        default_client.stop()
        default_client = None


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description='Command relay client for receiving commands from a server.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--server-url', type=str,
                        help='Base URL of the command server')
    parser.add_argument('--api-key', type=str,
                        help='API key for authentication')
    parser.add_argument('--client-id', type=str,
                        help='Unique ID for this client')
    parser.add_argument('--poll-interval', type=int, default=30,
                        help='Interval between polling for commands in seconds')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='Log level')
    
    args = parser.parse_args()
    
    # Setup logging
    numeric_level = getattr(logging, args.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {args.log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the command relay client
    client = start_command_relay(
        server_url=args.server_url,
        api_key=args.api_key,
        client_id=args.client_id,
        poll_interval=args.poll_interval
    )
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Command relay client interrupted by user")
        stop_command_relay()
