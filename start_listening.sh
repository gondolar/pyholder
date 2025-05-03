#!/bin/bash

default_ip="192.168.8.10"
if [ -n "$1" ]; then
    custom_ip="$1"
else
    echo "Custom IP not specified in command line. Default: $default_ip"
    custom_ip="$default_ip"
fi
uvicorn pyholder:app --port 9018 --host "$custom_ip" --reload --log-level debug
