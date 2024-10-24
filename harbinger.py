#!/usr/bin/env python3
"""
Docker and Docker Compose Monitor with Slack Notifications
-------------------------------------------------------
A professional monitoring solution that tracks Docker container events,
including docker-compose services, and sends detailed notifications to Slack.

Features:
- Docker and docker-compose support
- Detailed error tracking and notifications
- Professional logging and error handling
- Configurable retry logic
- Comprehensive container information

Logs:
 - sudo cat /var/log/docker-monitor.log

Author: Luis Sarabando
Version: 1.1.0
License: MIT
"""

import docker
import requests
import json
import logging
import os
import socket
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List, Any

# Configuration Constants, will also load these from a .env file if its available
DEFAULT_CONFIG = {
    "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/YOUR/DEFAULT/WEBHOOK",
    "MONITOR_ENV": "production",
    "MONITOR_HOST": None,  # Will use socket.gethostname() if None
    "LOG_LINES": 5,
    "RETRY_INTERVAL": 10,  # Seconds to wait before retrying on error
    "MAX_RETRIES": 3,     # Maximum number of retries for Slack notifications
    "LOG_FILE": "docker_monitor.log"
}

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DEFAULT_CONFIG['LOG_FILE'])
    ]
)
logger = logging.getLogger(__name__)

class ConfigurationError(Exception):
    """Raised when there's an error in the configuration"""
    pass

class SlackNotificationError(Exception):
    """Raised when there's an error sending notifications to Slack"""
    pass

class DockerMonitorError(Exception):
    """Base class for Docker monitoring errors"""
    pass

class DockerSlackMonitor:
    """
    Main monitor class that handles Docker events and Slack notifications.

    This class monitors both standalone Docker containers and docker-compose services,
    providing detailed notifications for container lifecycle events.
    """

    def __init__(self):
        """Initialize the Docker monitor with configuration and connections"""
        self._load_configuration()
        self._initialize_docker_client()

    def _load_configuration(self) -> None:
        """
        Load configuration from environment variables or .env file
        Raises ConfigurationError if critical configurations are missing
        """
        try:
            # Attempt to load .env file
            try:
                from dotenv import load_dotenv
                if load_dotenv():
                    logger.info("Loaded configuration from .env file")
                    # Debug: Print the loaded webhook URL
                    logger.info(f"Loaded webhook URL: {os.getenv('SLACK_WEBHOOK_URL', 'Not found')}")
            except ImportError:
                logger.info("python-dotenv not installed, using environment variables")

            # Load critical configurations
            self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            
            if not self.slack_webhook_url:
                raise ValueError("SLACK_WEBHOOK_URL not found in environment or .env file")
            else:
                logger.info("Successfully loaded Slack webhook URL")

            # Load other configurations with defaults
            self.hostname = os.getenv('MONITOR_HOST', socket.gethostname())
            self.environment = os.getenv('MONITOR_ENV', 'production')
            self.log_lines = int(os.getenv('LOG_LINES', '5'))
            self.retry_interval = int(os.getenv('RETRY_INTERVAL', '10'))
            self.max_retries = int(os.getenv('MAX_RETRIES', '3'))

            # Debug: Print current configuration
            logger.info(f"Current configuration:")
            logger.info(f"Hostname: {self.hostname}")
            logger.info(f"Environment: {self.environment}")
            logger.info(f"Log lines: {self.log_lines}")

        except Exception as e:
            logger.error(f"Configuration error details: {str(e)}")
            raise ConfigurationError(f"Failed to load configuration: {str(e)}")
    def _initialize_docker_client(self) -> None:
        """
        Initialize the Docker client connection
        Raises DockerMonitorError if connection fails
        """
        try:
            self.client = docker.from_env()
            self.client.ping()  # Test connection
            logger.info(f"Successfully connected to Docker daemon on {self.hostname}")
        except docker.errors.DockerException as e:
            raise DockerMonitorError(f"Failed to connect to Docker daemon: {str(e)}")

    def _get_compose_info(self, container_attributes: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract docker-compose project and service information from container labels

        Args:
            container_attributes: Container attributes including labels

        Returns:
            Tuple[Optional[str], Optional[str]]: (project_name, service_name) or (None, None)
        """
        labels = container_attributes.get('Labels', {})

        # Check different possible compose label formats
        project = (
            labels.get('com.docker.compose.project') or
            labels.get('com.docker.compose.project.working_dir', '').split('/')[-1] or
            labels.get('com.docker.compose.project.name')
        )

        service = (
            labels.get('com.docker.compose.service') or
            labels.get('com.docker.compose.service.name')
        )

        return project, service

    def _format_container_name(self, attributes: Dict[str, Any]) -> str:
        """
        Format container name with compose information if available

        Args:
            attributes: Container attributes including labels

        Returns:
            str: Formatted container name/service description
        """
        project, service = self._get_compose_info(attributes)
        container_name = attributes.get('name', 'Unknown')

        if project and service:
            return f"{project}/{service}"
        return container_name

    def get_container_logs(self, container_id: str, tail: int = 5) -> str:
        """
        Fetch the last few lines of container logs with proper error handling

        Args:
            container_id: The ID of the container
            tail: Number of log lines to retrieve

        Returns:
            str: Formatted log output or error message
        """
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=True).decode('utf-8').strip()
            
            if not logs:
                return "No logs available"

            # Format logs with timestamps and proper indentation
            formatted_logs = []
            for line in logs.split('\n')[-tail:]:
                try:
                    # Split on first space to separate timestamp from message
                    parts = line.split(' ', 1)
                    if len(parts) >= 2:
                        # Handle timestamp with nanoseconds
                        timestamp_str = parts[0]
                        # Remove the nanoseconds part but keep milliseconds
                        timestamp_str = timestamp_str.split('.')[0] + 'Z'
                        try:
                            # Parse the timestamp
                            timestamp = datetime.strptime(
                                timestamp_str, 
                                '%Y-%m-%dT%H:%M:%SZ'
                            ).strftime('%Y-%m-%d %H:%M:%S')
                            message = parts[1]
                            formatted_logs.append(f"{timestamp} | {message}")
                        except ValueError as e:
                            # If timestamp parsing fails, just use the original line
                            logger.debug(f"Timestamp parsing error: {e}")
                            formatted_logs.append(line)
                    else:
                        formatted_logs.append(line)
                except Exception as e:
                    logger.debug(f"Error formatting log line: {e}")
                    formatted_logs.append(line)

            return "\n".join(formatted_logs)

        except docker.errors.NotFound:
            return "Container not found - may have been removed"
        except Exception as e:
            logger.error(f"Error fetching logs for container {container_id}: {str(e)}")
            return f"Error retrieving logs: {str(e)}"

    def _get_container_details(self, container_id: str) -> Dict[str, Any]:
        """
        Get detailed container information including compose details

        Args:
            container_id: The ID of the container

        Returns:
            Dict[str, Any]: Container details including compose information
        """
        try:
            container = self.client.containers.get(container_id)
            inspect = container.attrs

            project, service = self._get_compose_info(inspect['Config'])

            return {
                'name': inspect['Name'].lstrip('/'),
                'image': inspect['Config']['Image'],
                'project': project,
                'service': service,
                'compose': bool(project and service),
                'created': inspect['Created'],
                'state': inspect['State'],
                'network_mode': inspect['HostConfig']['NetworkMode']
            }
        except Exception as e:
            logger.error(f"Error getting container details: {str(e)}")
            return {}

    def format_status_message(self, status_text: str, exit_code: Optional[str] = None) -> str:
        """
        Format the status message with exit code if available

        Args:
            status_text: The status text to format
            exit_code: Optional exit code to include

        Returns:
            str: Formatted status message
        """
        if exit_code is not None and "EXIT" in status_text:
            if exit_code == "0":
                return f"{status_text} (Clean exit)"
            return f"{status_text} (Error exit code: {exit_code})"
        return status_text

    def _create_slack_payload(self, container_name: str, status: str, 
                            container_id: Optional[str] = None, 
                            exit_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a compact Slack message payload with the requested formatting
        """
        # Status mapping with emojis
        status_mapping = {
            "started": ("START", "✅"),
            "exited": ("EXITED", "❌"),
            "killed": ("KILLED", "💀"),
            "restart": ("RESTART", "🔄"),
            "start": ("START", "✅"),
            "stopped": ("STOPPED", "⏹️")
        }
        
        status_text, icon = status_mapping.get(status, (status.upper(), "•"))
        
        # Get container details
        details = self._get_container_details(container_id) if container_id else {}
        is_compose = details.get('compose', False)

        # Format status with exit code if present
        status_display = status_text
        if exit_code is not None and "EXIT" in status_text:
            status_display = f"{status_text} (Exit Code: {exit_code})"

        # Build the message content
        title = f"Docker Compose Service Event {icon}" if is_compose else f"Docker Container Event {icon}"
        
        # Build the main message text with proper formatting
        message_parts = [
            f"*Service:* `{details.get('project', 'Unknown')}/{details.get('service', 'Unknown')}`" if is_compose else f"*Service:* `{container_name}`",
            f"*Status:* `{status_display}`",
            f"*Host:* `{self.hostname}`",
            f"*Environment:* `{self.environment}`"
        ]

        if details.get('image'):
            message_parts.append(f"*Image:* {details.get('image')}")

        # Add logs section if needed
        logs = None
        if "EXIT" in status_text or status_text == "KILLED":
            logs = self.get_container_logs(container_id, self.log_lines) if container_id else "No logs available"
            if logs and logs != "No logs available":
                message_parts.append("\n*Recent Logs:*")
                message_parts.append(f"```{logs}```")

        # Colors for different states
        colors = {
            "START": "#36a64f",     # Green
            "EXITED": "#dc3545",    # Red
            "KILLED": "#ff6b6b",    # Light red
            "RESTART": "#4dabf7",   # Blue
            "STOPPED": "#ffd93d"    # Yellow
        }

        return {
            "attachments": [
                {
                    "color": colors.get(status_text, "#cccccc"),
                    "title": title,
                    "text": "\n".join(message_parts),
                    "mrkdwn_in": ["text"],
                    "footer": f"Docker Monitor - {self.hostname}",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }


    def send_slack_message(self, container_name: str, status: str,
                          container_id: Optional[str] = None,
                          exit_code: Optional[str] = None) -> None:
        """
        Send notification to Slack with retry logic

        Args:
            container_name: Name of the container
            status: Current status
            container_id: Optional container ID
            exit_code: Optional exit code

        Raises:
            SlackNotificationError: If notification fails after retries
        """
        message = self._create_slack_payload(container_name, status, container_id, exit_code)

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.slack_webhook_url,
                    data=json.dumps(message),
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )

                if response.status_code == 200:
                    logger.info(f"Notification sent for {container_name}: {status}")
                    return
                else:
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {response.text}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Attempt {attempt + 1}/{self.max_retries} failed: {str(e)}")

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_interval)

        raise SlackNotificationError(f"Failed to send notification after {self.max_retries} attempts")

    def monitor_containers(self) -> None:
            """
            Main monitoring loop for Docker container events
            Implements continuous retry logic and graceful shutdown
            """
            logger.info(f"Starting Docker container monitoring on {self.hostname}...")
            
            # Extended action mapping to handle more events
            action_mapping = {
                'die': 'exited',
                'kill': 'killed',
                'stop': 'stopped',
                'start': 'started',
                'restart': 'restarted',
                'pause': 'paused',
                'unpause': 'unpaused',
                'destroy': 'removed'  # This catches compose down events
            }
            
            while True:
                try:
                    for event in self.client.events(decode=True, filters={'type': 'container'}):
                        action = event['Action']
                        
                        # Only process relevant events
                        if action in action_mapping:
                            attributes = event['Actor']['Attributes']
                            container_id = event['Actor']['ID']
                            container_name = self._format_container_name(attributes)
                            mapped_status = action_mapping[action]
                            
                            try:
                                # Handle different types of exits
                                if action in ['die', 'kill', 'destroy']:
                                    exit_code = attributes.get('exitCode', 'Unknown')
                                    # Don't send notification for clean exits during compose down
                                    if action == 'destroy' and exit_code == '0' and self._is_compose_operation(attributes):
                                        logger.debug(f"Skipping clean compose down notification for {container_name}")
                                        continue
                                    self.send_slack_message(container_name, mapped_status, container_id, exit_code)
                                else:
                                    self.send_slack_message(container_name, mapped_status, container_id)
                                    
                            except SlackNotificationError as e:
                                logger.error(f"Failed to send notification: {str(e)}")
                                
                except KeyboardInterrupt:
                    logger.info("Received shutdown signal. Stopping container monitoring...")
                    break
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {str(e)}")
                    logger.info(f"Retrying in {self.retry_interval} seconds...")
                    time.sleep(self.retry_interval)

            def _is_compose_operation(self, attributes: Dict[str, Any]) -> bool:
                """
                Check if this is part of a docker-compose operation
                
                Args:
                    attributes: Container attributes including labels
                    
                Returns:
                    bool: True if this is a compose operation
                """
                labels = attributes.get('Labels', {})
                return any(label.startswith('com.docker.compose') for label in labels)

            def _create_slack_payload(self, container_name: str, status: str, 
                                    container_id: Optional[str] = None, 
                                    exit_code: Optional[str] = None) -> Dict[str, Any]:
                """
                Create Slack message payload with enhanced compose information
                """
                # Extended status mapping with more icons and colors
                status_mapping = {
                    "started": ("START", "🟢"),
                    "exited": ("EXITED", "🔴"),
                    "killed": ("KILLED", "💀"),
                    "stopped": ("STOPPED", "🟡"),
                    "restarted": ("RESTART", "🔄"),
                    "paused": ("PAUSED", "⏸️"),
                    "unpaused": ("UNPAUSED", "▶️"),
                    "removed": ("REMOVED", "🗑️")
                }
                
                status_text, icon = status_mapping.get(status, (status.upper(), "•"))
                
                # Extended color mapping
                colors = {
                    "START": "#36a64f",      # Green
                    "EXITED": "#dc3545",     # Red
                    "KILLED": "#ff6b6b",     # Light red
                    "STOPPED": "#ffd93d",    # Yellow
                    "RESTART": "#4dabf7",    # Blue
                    "PAUSED": "#e9ecef",     # Light gray
                    "UNPAUSED": "#748ffc",   # Purple
                    "REMOVED": "#868e96"     # Gray
                }
            

def main() -> None:
    """
    Main entry point with error handling
    """
    try:
        monitor = DockerSlackMonitor()
        monitor.monitor_containers()
    except ConfigurationError as e:
        logger.critical(f"Configuration error: {str(e)}")
        sys.exit(1)
    except DockerMonitorError as e:
        logger.critical(f"Docker error: {str(e)}")
        sys.exit(2)
    except Exception as e:
        logger.critical(f"Unexpected error: {str(e)}")
        sys.exit(3)

if __name__ == "__main__":
    main()
