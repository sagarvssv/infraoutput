#!/bin/bash

echo "Stopping and removing existing Docker container"
docker stop my-Infraoutputppapplication  || true
docker rm my-Infraoutputppapplication  || true

echo "Removing old Docker image"
docker rmi -f mallapp_vcloud:latest|| true

echo "Old containers and images removed successfully."
