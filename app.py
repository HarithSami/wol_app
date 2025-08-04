#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template_string
import socket
import struct
import os

app = Flask(__name__)

def send_magic_packet(mac_address, ip_address, port=9):
    """
    Send a Wake-on-LAN magic packet to the specified MAC address
    """
    try:
        # Remove any separators and convert to uppercase
        mac_address = mac_address.replace(':', '').replace('-', '').upper()
        
        # Validate MAC address length
        if len(mac_address) != 12:
            raise ValueError("Invalid MAC address length")
        
        # Convert MAC address to bytes
        mac_bytes = bytes.fromhex(mac_address)
        
        # Create magic packet: 6 bytes of 0xFF followed by 16 repetitions of MAC address
        magic_packet = b'\xFF' * 6 + mac_bytes * 16
        
        # Create socket and send packet
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Send to broadcast address
        broadcast_ip = '.'.join(ip_address.split('.')[:-1]) + '.255'
        sock.sendto(magic_packet, (broadcast_ip, port))
        sock.close()
        
        return True, f"Magic packet sent to {mac_address} via {broadcast_ip}:{port}"
        
    except Exception as e:
        return False, f"Error sending magic packet: {str(e)}"

@app.route('/')
def index():
    """
    Serve the main HTML page
    """
    # Read the HTML file
    try:
        with open('index.html', 'r') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        # If index.html doesn't exist, return a basic version
        return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Wake-on-LAN Server</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>
            <h1>Wake-on-LAN Server</h1>
            <p>Please create an index.html file or use the artifact provided.</p>
            <form id="wolForm">
                <input type="text" id="mac" placeholder="MAC Address (DE:5E:D3:93:DF:F5)" required>
                <input type="text" id="ip" placeholder="IP Address (192.168.0.18)" required>
                <input type="number" id="port" placeholder="Port (9)" value="9">
                <button type="submit">Wake Device</button>
            </form>
            
            <script>
                document.getElementById('wolForm').addEventListener('submit', async (e) => {
                    e.preventDefault();
                    const mac = document.getElementById('mac').value;
                    const ip = document.getElementById('ip').value;
                    const port = document.getElementById('port').value || 9;
                    
                    const response = await fetch('/wake', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({mac, ip, port})
                    });
                    
                    const result = await response.json();
                    alert(result.message || result.error);
                });
            </script>
        </body>
        </html>
        '''

@app.route('/wake', methods=['POST'])
def wake_device():
    """
    Handle Wake-on-LAN requests
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract parameters
        mac_address = data.get('mac')
        ip_address = data.get('ip')
        port = data.get('port', 9)
        device_name = data.get('device_name', 'Unknown Device')
        
        # Validate required parameters
        if not mac_address:
            return jsonify({'error': 'MAC address is required'}), 400
        
        if not ip_address:
            return jsonify({'error': 'IP address is required'}), 400
        
        # Send magic packet
        success, message = send_magic_packet(mac_address, ip_address, port)
        
        if success:
            print(f"✅ Wake packet sent to {device_name} ({mac_address}) at {ip_address}:{port}")
            return jsonify({
                'success': True,
                'message': f'Wake packet sent to {device_name}',
                'details': message
            })
        else:
            print(f"❌ Failed to send wake packet to {device_name}: {message}")
            return jsonify({'error': message}), 500
            
    except Exception as e:
        print(f"❌ Server error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/devices', methods=['GET'])
def get_devices():
    """
    Get list of configured devices (for future expansion)
    """
    # This could be expanded to read from a config file or database
    devices = {
        "HARITH'S PC": {
            "mac": "DE:5E:D3:93:DF:F5",
            "ip": "192.168.0.18",
            "port": 9,
            "subnet": "255.255.255.0"
        }
    }
    return jsonify(devices)

@app.route('/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint
    """
    return jsonify({
        'status': 'healthy',
        'service': 'Wake-on-LAN Server',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    print("🚀 Starting Wake-on-LAN Server...")
    print("📱 Access the web interface at: http://localhost:5000")
    print("🔧 API endpoints:")
    print("   POST /wake - Send wake packet")
    print("   GET  /devices - List devices")
    print("   GET  /health - Health check")
    print()
    print("💻 Pre-configured device:")
    print("   Name: HARITH'S PC")
    print("   MAC:  DE:5E:D3:93:DF:F5")
    print("   IP:   192.168.0.18")
    print("   Port: 9")
    print()
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=True
    )