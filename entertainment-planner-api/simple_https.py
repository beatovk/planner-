#!/usr/bin/env python3
from flask import Flask, send_from_directory
import ssl
import os

app = Flask(__name__)

# Serve static files from web2 directory
@app.route('/')
def index():
    return send_from_directory('/Users/user/entertainment planner/entertainment-planner-api/apps/web-mobile/web2', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('/Users/user/entertainment planner/entertainment-planner-api/apps/web-mobile/web2', filename)

if __name__ == '__main__':
    print("HTTP Server running on http://0.0.0.0:3000")
    print("Access locally: http://localhost:3000")
    app.run(host='0.0.0.0', port=3000, debug=True)
