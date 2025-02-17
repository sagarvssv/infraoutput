#!/bin/bash
# Check if CodeDeploy agent is running
echo "Checking if CodeDeploy agent is running..."
if ! sudo service codedeploy-agent status > /dev/null; then
  echo "CodeDeploy agent is not running. Attempting to start it..."
  sudo service codedeploy-agent start
  if [ $? -eq 0 ]; then
    echo "CodeDeploy agent started successfully."
  else
    echo "Failed to start CodeDeploy agent."
    exit 1
  fi
else
  echo "CodeDeploy agent is already running."
fi
