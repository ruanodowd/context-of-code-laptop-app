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
from typing import Dict, Any, Optional, Callable

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
            logger.warning("Unknown command: %s", command)
            return {
                "status": "error",
                "message": f"Unknown command: {command}"
            }
        
        try:
            handler = self.command_handlers[command]
            return handler(params or {})
        except Exception as e:
            logger.error("Error executing command %s: %s", command, str(e))
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
        
        # File to store the last processed command ID - now in the sdk directory
        self.state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "command_relay_state.json")
        self._load_state()
    
    def _load_state(self) -> None:
        """Load the state from file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.last_command_id = state.get("last_command_id", self.last_command_id)
                    logger.debug("Loaded state: last_command_id=%s", self.last_command_id)
            except (IOError, json.JSONDecodeError) as e:
                logger.error("Failed to load state: %s", str(e))
    
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
            logger.error("Failed to save state: %s", str(e))
    
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
                
                if not commands:
                    logger.debug("No pending commands found")
                    return
                
                logger.info("Found %d pending commands", len(commands))
                for cmd in commands:
                    command_id = cmd.get("id")
                    command_type = cmd.get("command")
                    command_params = cmd.get("parameters", {})
                    
                    # Skip if we've already processed this command
                    if self.last_command_id and command_id == self.last_command_id:
                        logger.debug("Skipping already processed command: %s", command_id)
                        continue
                    
                    logger.info("Executing command %s: %s", command_id, command_type)
                    result = self.executor.execute_command(command_type, command_params)
                    
                    # Send the result back to the server
                    self._send_result(command_id, result)
                    
                    # Update the last processed command ID
                    self.last_command_id = command_id
                    self._save_state()
            else:
                logger.warning(
                    "Failed to fetch commands: %d - %s",
                    response.status_code,
                    response.text
                )
        except requests.RequestException as e:
            logger.error("Error polling commands: %s", str(e))
        except Exception as e:
            logger.error("Unexpected error polling commands: %s", str(e))
    
    def _send_result(self, command_id: str, result: Dict[str, Any]) -> None:
        """
        Send the command execution result back to the server.
        
        Args:
            command_id (str): ID of the processed command
            result (dict): Result of the command execution
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
                f"{self.server_url.rstrip('/')}/api/commands/result",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.debug("Successfully sent result for command %s", command_id)
            else:
                logger.warning(
                    "Failed to send result for command %s: %d - %s",
                    command_id,
                    response.status_code,
                    response.text
                )
        except requests.RequestException as e:
            logger.error("Error sending result for command %s: %s", command_id, str(e))
    
    def register_command_handler(self, command: str, handler: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        """
        Register a custom command handler.
        
        Args:
            command (str): The command name
            handler (callable): Function that takes parameters dict and returns result dict
        """
        self.executor.command_handlers[command] = handler
    
    def start(self) -> None:
        """Start the command polling thread."""
        if self.running:
            logger.warning("Command relay already running")
            return
        
        self.running = True
        
        def poll_loop():
            logger.info("Starting command relay poll loop")
            while self.running:
                try:
                    self._poll_commands()
                except Exception as e:
                    logger.error("Error in poll loop: %s", str(e))
                
                # Sleep for the poll interval
                for _ in range(int(self.poll_interval)):
                    if not self.running:
                        break
                    time.sleep(1)
        
        self.thread = threading.Thread(target=poll_loop, daemon=True)
        self.thread.start()
        logger.info("Command relay started with client_id: %s", self.client_id)
    
    def stop(self) -> None:
        """Stop the command polling thread."""
        if not self.running:
            logger.warning("Command relay not running")
            return
        
        logger.info("Stopping command relay")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning("Command relay thread did not stop cleanly")
            self.thread = None


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
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Command Relay Client")
    parser.add_argument("--server-url", help="Command server URL")
    parser.add_argument("--api-key", help="API key for authentication")
    parser.add_argument("--client-id", help="Client ID")
    parser.add_argument("--poll-interval", type=int, default=30, help="Poll interval in seconds")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    try:
        # Start the command relay
        client = start_command_relay(
            server_url=args.server_url,
            api_key=args.api_key,
            client_id=args.client_id,
            poll_interval=args.poll_interval
        )
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping...")
        stop_command_relay()
        sys.exit(0)
    except Exception as e:
        logger.error("Error in main thread: %s", str(e))
        stop_command_relay()
        sys.exit(1)
