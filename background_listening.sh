#!/bin/bash

BASH_COMMAND="bash ./start_listening.sh"
nohup $BASH_COMMAND > pyholder.log 2>&1 &

PID=$!

echo "Listener PID: $PID"
