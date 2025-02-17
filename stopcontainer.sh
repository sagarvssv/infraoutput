#!/bin/bash

echo "Starting Docker container"

# Authenticate with ECR
aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin 010438505789.dkr.ecr.ap-south-1.amazonaws.com

# Pull the latest Docker image
docker pull 010438505789.dkr.ecr.ap-south-1.amazonaws.com/mallapp_vcloud:latest

# Run the Docker container
docker run -d -p 5000:5000 --name my-Mallappapplication 010438505789.dkr.ecr.ap-south-1.amazonaws.com/mallapp_vcloud:latest
