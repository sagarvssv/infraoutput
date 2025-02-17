#!/bin/bash
# Check status of CodeDeploy agent
echo "Checking status of CodeDeploy agent..."
sudo service codedeploy-agent status
if [ $? -ne 0 ]; then
  echo "CodeDeploy agent is not running. Attempting restart..."
  sudo service codedeploy-agent restart
  if [ $? -eq 0 ]; then
    echo "CodeDeploy agent restarted successfully."
  else
    echo "Failed to restart CodeDeploy agent."
    exit 1
  fi
else
  echo "CodeDeploy agent is running."
fi
