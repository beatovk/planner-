#!/usr/bin/env python3
"""
Simple server starter script that works without terminal issues
"""
import subprocess
import sys
import os

def start_server():
    # Change to the correct directory
    os.chdir("/Users/user/entertainment planner/entertainment-planner-api")
    
    # Activate virtual environment and run server
    venv_python = "/Users/user/entertainment planner/venv/bin/python"
    
    print("Starting server on port 3000...")
    print("Frontend will be available at: http://localhost:3000")
    print("API will be available at: http://localhost:8000")
    
    try:
        # Start the simple HTTP server for frontend
        subprocess.run([venv_python, "simple_https.py"])
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    start_server()
