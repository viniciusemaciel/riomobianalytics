#!/bin/bash

PORT=8501

echo "RioMobiAnalytics Web Application"
echo "=================================="
echo ""

# Check if process is already running on port 8501
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "Port $PORT is already in use. Stopping existing process..."

    # Get PID of process using the port
    PID=$(lsof -t -i :$PORT)

    if [ -n "$PID" ]; then
        echo "Killing process $PID..."
        kill -9 $PID
        sleep 1
        echo "Process stopped."
    fi
fi

echo "Starting web application..."
echo ""

export PYTHONPATH="${PYTHONPATH}:$(pwd)"

streamlit run webapp/Home.py --server.port=$PORT --server.address=0.0.0.0
