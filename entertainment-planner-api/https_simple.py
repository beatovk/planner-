#!/usr/bin/env python3
import http.server
import ssl
import socketserver
import os

# Change to the web2 directory
os.chdir('/Users/user/entertainment planner/entertainment-planner-api/apps/web-mobile/web2')

# Create HTTPS server
class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

# Create server
with socketserver.TCPServer(("0.0.0.0", 8080), MyHTTPRequestHandler) as httpd:
    # Create SSL context with modern settings
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    context.load_cert_chain('cert.pem', 'key.pem')
    
    # Wrap socket with SSL
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    print("HTTPS Server running on https://0.0.0.0:8080")
    print("Access from phone: https://192.168.1.100:8080")
    print("Note: You may need to accept the self-signed certificate in Safari")
    httpd.serve_forever()
