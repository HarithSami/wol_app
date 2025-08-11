#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template_string
import socket
import struct
import os
import yaml
import subprocess
import platform
import threading
import time
from pathlib import Path

app = Flask(__name__)

# Configuration
CONFIG_FILE = 'devices.yaml'

# Store device status in memory
device_status = {}
status_lock = threading.Lock()

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

def ping_device(ip_address, timeout=3):
    """
    Ping a device to check if it's online
    Returns tuple: (is_online, response_time_ms)
    """
    try:
        system = platform.system().lower()
        
        if system == "windows":
            # Windows ping command
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip_address]
        else:
            # Linux/Mac ping command
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip_address]
        
        start_time = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
        end_time = time.time()
        
        if result.returncode == 0:
            response_time = round((end_time - start_time) * 1000, 1)
            return True, response_time
        else:
            return False, None
            
    except subprocess.TimeoutExpired:
        return False, None
    except Exception as e:
        print(f"❌ Error pinging {ip_address}: {e}")
        return False, None

def check_all_devices():
    """
    Check the online status of all devices
    """
    global device_status
    devices = load_devices()
    
    if not devices:
        return
    
    print("🔍 Checking device status...")
    
    # Use threading to ping devices in parallel for faster checking
    threads = []
    results = {}
    
    def ping_worker(device_name, device_info):
        ip = device_info['ip']
        is_online, response_time = ping_device(ip)
        results[device_name] = {
            'online': is_online,
            'response_time': response_time,
            'last_checked': time.time(),
            'ip': ip
        }
        
        status_emoji = "🟢" if is_online else "🔴"
        time_str = f" ({response_time}ms)" if response_time else ""
        print(f"  {status_emoji} {device_name}: {ip}{time_str}")
    
    # Start ping threads
    for device_name, device_info in devices.items():
        thread = threading.Thread(target=ping_worker, args=(device_name, device_info))
        thread.start()
        threads.append(thread)
    
    # Wait for all pings to complete (with reasonable timeout)
    for thread in threads:
        thread.join(timeout=5)
    
    # Update global status with thread lock
    with status_lock:
        device_status.update(results)
    
    print(f"✅ Status check completed for {len(results)} devices")

# Load devices and check status on startup
devices_config = load_devices()
if devices_config:
    check_all_devices()

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
    Get list of configured devices with their online status
    """
    global devices_config, device_status
    devices_config = load_devices()  # Reload from file
    
    # Merge device config with status info
    devices_with_status = {}
    
    with status_lock:
        for device_name, device_info in devices_config.items():
            status = device_status.get(device_name, {
                'online': None,  # None means unknown/not checked yet
                'response_time': None,
                'last_checked': None,
                'ip': device_info['ip']
            })
            
            devices_with_status[device_name] = {
                **device_info,
                'status': status
            }
    
    return jsonify(devices_with_status)

@app.route('/devices/status', methods=['GET'])
def get_device_status():
    """
    Get only the status information for all devices
    """
    with status_lock:
        return jsonify(device_status.copy())

@app.route('/devices/check', methods=['POST'])
def check_device_status():
    """
    Manually trigger a status check for all devices
    """
    try:
        # Run status check in a separate thread to avoid blocking the request
        def async_check():
            check_all_devices()
        
        thread = threading.Thread(target=async_check)
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Status check initiated'
        })
    except Exception as e:
        print(f"❌ Error initiating status check: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/devices/ping/<device_name>', methods=['POST'])
def ping_single_device(device_name):
    """
    Ping a specific device and return its status
    """
    try:
        global devices_config, device_status
        
        if device_name not in devices_config:
            return jsonify({'error': 'Device not found'}), 404
        
        device_info = devices_config[device_name]
        ip_address = device_info['ip']
        
        # Ping the device
        is_online, response_time = ping_device(ip_address)
        
        # Update status
        status_info = {
            'online': is_online,
            'response_time': response_time,
            'last_checked': time.time(),
            'ip': ip_address
        }
        
        with status_lock:
            device_status[device_name] = status_info
        
        print(f"🔍 Pinged {device_name} ({ip_address}): {'🟢 Online' if is_online else '🔴 Offline'}")
        
        return jsonify({
            'success': True,
            'device_name': device_name,
            'status': status_info
        })
        
    except Exception as e:
        print(f"❌ Error pinging device {device_name}: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

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
            
            # Check status of the new device
            is_online, response_time = ping_device(ip_address)
            status_info = {
                'online': is_online,
                'response_time': response_time,
                'last_checked': time.time(),
                'ip': ip_address
            }
            
            with status_lock:
                device_status[device_name] = status_info
            
            return jsonify({
                'success': True,
                'message': f'Device "{device_name}" added successfully',
                'device': {
                    **devices_config[device_name],
                    'status': status_info
                }
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
        global devices_config, device_status
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
            # Also update status tracking
            with status_lock:
                if device_name in device_status:
                    device_status[new_name] = device_status.pop(device_name)
        
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
            
            # Check status of the updated device
            is_online, response_time = ping_device(ip_address)
            status_info = {
                'online': is_online,
                'response_time': response_time,
                'last_checked': time.time(),
                'ip': ip_address
            }
            
            with status_lock:
                device_status[new_name] = status_info
            
            return jsonify({
                'success': True,
                'message': f'Device "{new_name}" updated successfully',
                'device': {
                    **devices_config[new_name],
                    'status': status_info
                }
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
        global devices_config, device_status
        
        # Check if device exists
        if device_name not in devices_config:
            return jsonify({'error': 'Device not found'}), 404
        
        # Remove device
        del devices_config[device_name]
        
        # Remove from status tracking
        with status_lock:
            if device_name in device_status:
                del device_status[device_name]
        
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
        'version': '1.0.0',
        'devices_tracked': len(devices_config),
        'status_entries': len(device_status)
    })

if __name__ == '__main__':
    print("🚀 Starting Wake-on-LAN Server with Ping Support...")
    print("📱 Access the web interface at: http://localhost:5000")
    print("🔧 API endpoints:")
    print("   POST /wake - Send wake packet")
    print("   GET  /devices - List devices with status")
    print("   POST /devices - Add device")
    print("   PUT  /devices/<name> - Update device")
    print("   DELETE /devices/<name> - Delete device")
    print("   GET  /devices/status - Get all device status")
    print("   POST /devices/check - Refresh all device status")
    print("   POST /devices/ping/<name> - Ping specific device")
    print("   GET  /health - Health check")
    print()
    print(f"📄 Configuration file: {CONFIG_FILE}")
    print(f"📊 Loaded {len(devices_config)} device(s):")
    for name, device in devices_config.items():
        status = device_status.get(name, {})
        online_status = ""
        if status.get('online') is True:
            online_status = f" (🟢 {status.get('response_time', 'N/A')}ms)"
        elif status.get('online') is False:
            online_status = " (🔴 Offline)"
        print(f"   • {name}: {device['mac']} ({device['ip']}:{device['port']}){online_status}")
    print()
    
    # Check if PyYAML is installed
    try:
        import yaml
        print("✅ PyYAML is available")
    except ImportError:
        print("❌ PyYAML not found. Install with: pip install PyYAML")
        exit(1)
    
    print("🔧 Running in production mode (debug=False) to avoid /dev/shm issues")
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=False  # Disabled debug mode
    )
