#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template_string
import socket
import struct
import os
import yaml
from pathlib import Path

app = Flask(__name__)

# Configuration
CONFIG_FILE = 'devices.yaml'

def load_devices():
    """
    Load devices from YAML configuration file
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                return data.get('devices', {})
        else:
            # Create empty config if file doesn't exist
            default_config = {
                'devices': {},
                'version': '1.0',
                'created_by': 'WoLow Wake-on-LAN App'
            }
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
            return {}
    except Exception as e:
        print(f"❌ Error loading devices: {e}")
        return {}

def save_devices(devices):
    """
    Save devices to YAML configuration file
    """
    try:
        config_data = {
            'devices': devices,
            'version': '1.0',
            'created_by': 'WoLow Wake-on-LAN App'
        }
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
        
        print(f"✅ Devices saved to {CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"❌ Error saving devices: {e}")
        return False

# Load devices on startup
devices_config = load_devices()

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
    # Read the HTML file with UTF-8 encoding
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
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
        global devices_config
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract parameters
        device_name = data.get('device_name', 'Unknown Device')
        
        # Check if we should use device from config or provided parameters
        if device_name in devices_config:
            device = devices_config[device_name]
            mac_address = device['mac']
            ip_address = device['ip']
            port = device['port']
        else:
            # Fall back to provided parameters
            mac_address = data.get('mac')
            ip_address = data.get('ip')
            port = data.get('port', 9)
        
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
    Get list of configured devices
    """
    global devices_config
    devices_config = load_devices()  # Reload from file
    return jsonify(devices_config)

@app.route('/devices', methods=['POST'])
def add_device():
    """
    Add a new device to the configuration
    """
    try:
        global devices_config
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract device information
        device_name = data.get('name')
        mac_address = data.get('mac')
        ip_address = data.get('ip')
        port = data.get('port', 9)
        subnet = data.get('subnet', '255.255.255.0')
        
        # Validate required fields
        if not device_name:
            return jsonify({'error': 'Device name is required'}), 400
        if not mac_address:
            return jsonify({'error': 'MAC address is required'}), 400
        if not ip_address:
            return jsonify({'error': 'IP address is required'}), 400
        
        # Add device to configuration
        devices_config[device_name] = {
            'mac': mac_address,
            'ip': ip_address,
            'port': port,
            'subnet': subnet
        }
        
        # Save to file
        if save_devices(devices_config):
            print(f"✅ Added device: {device_name} ({mac_address})")
            return jsonify({
                'success': True,
                'message': f'Device "{device_name}" added successfully',
                'device': devices_config[device_name]
            })
        else:
            return jsonify({'error': 'Failed to save device configuration'}), 500
            
    except Exception as e:
        print(f"❌ Error adding device: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/devices/<device_name>', methods=['PUT'])
def update_device(device_name):
    """
    Update an existing device in the configuration
    """
    try:
        global devices_config
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Check if device exists
        if device_name not in devices_config:
            return jsonify({'error': 'Device not found'}), 404
        
        # Extract device information
        new_name = data.get('name', device_name)
        mac_address = data.get('mac')
        ip_address = data.get('ip')
        port = data.get('port', 9)
        subnet = data.get('subnet', '255.255.255.0')
        
        # Validate required fields
        if not mac_address:
            return jsonify({'error': 'MAC address is required'}), 400
        if not ip_address:
            return jsonify({'error': 'IP address is required'}), 400
        
        # Remove old device if name changed
        if new_name != device_name:
            del devices_config[device_name]
        
        # Update device in configuration
        devices_config[new_name] = {
            'mac': mac_address,
            'ip': ip_address,
            'port': port,
            'subnet': subnet
        }
        
        # Save to file
        if save_devices(devices_config):
            print(f"✅ Updated device: {new_name} ({mac_address})")
            return jsonify({
                'success': True,
                'message': f'Device "{new_name}" updated successfully',
                'device': devices_config[new_name]
            })
        else:
            return jsonify({'error': 'Failed to save device configuration'}), 500
            
    except Exception as e:
        print(f"❌ Error updating device: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/devices/<device_name>', methods=['DELETE'])
def delete_device(device_name):
    """
    Delete a device from the configuration
    """
    try:
        global devices_config
        
        # Check if device exists
        if device_name not in devices_config:
            return jsonify({'error': 'Device not found'}), 404
        
        # Remove device
        del devices_config[device_name]
        
        # Save to file
        if save_devices(devices_config):
            print(f"✅ Deleted device: {device_name}")
            return jsonify({
                'success': True,
                'message': f'Device "{device_name}" deleted successfully'
            })
        else:
            return jsonify({'error': 'Failed to save device configuration'}), 500
            
    except Exception as e:
        print(f"❌ Error deleting device: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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
    print("   POST /devices - Add device")
    print("   PUT  /devices/<name> - Update device")
    print("   DELETE /devices/<name> - Delete device")
    print("   GET  /health - Health check")
    print()
    print(f"📄 Configuration file: {CONFIG_FILE}")
    print(f"📊 Loaded {len(devices_config)} device(s):")
    for name, device in devices_config.items():
        print(f"   • {name}: {device['mac']} ({device['ip']}:{device['port']})")
    print()
    
    # Check if PyYAML is installed
    try:
        import yaml
        print("✅ PyYAML is available")
    except ImportError:
        print("❌ PyYAML not found. Install with: pip install PyYAML")
        exit(1)
    
    # SOLUTION 1: Disable debug mode (Recommended for production)
    print("🔧 Running in production mode (debug=False) to avoid /dev/shm issues")
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=False  # CHANGED: Disabled debug mode
    )
    
    # SOLUTION 2: If you need debug mode, use the alternative below instead:
    # import tempfile
    # import os
    # 
    # # Set alternative temp directory if /dev/shm is not available
    # if not os.path.exists('/dev/shm'):
    #     tempfile.tempdir = '/tmp'
    # 
    # app.run(
    #     host='0.0.0.0',
    #     port=5000,
    #     debug=True,
    #     use_reloader=False  # Disable reloader to avoid multiprocessing issues
    # )
