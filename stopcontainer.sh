#!/bin/bash

echo "Stopping and removing existing Docker container"
docker stop my-Mallappapplication || true
docker rm my-Mallappapplication || true

echo "Removing old Docker image"
docker rmi -f infraoutput_vcloud:latest || true

echo "Old containers and images removed successfully."
