#!/bin/bash
echo "Checking CodeDeploy logs..."
sudo tail -n 10 /var/log/aws/codedeploy-agent/codedeploy-agent.log
