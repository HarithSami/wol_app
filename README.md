# Wake-on-LAN App (Ultra-Lightweight)

A minimal, ultra-lightweight Wake-on-LAN application built with raw Node.js (zero dependencies) and a pure HTML/CSS/JS frontend.

## Why the Rewrite?

The original version of this application used Python (Flask) and Streamlit. While functional, it was extremely resource-heavy on a Raspberry Pi:
- **Legacy Python Stack**: ~360MB RAM usage (11MB Flask + 350MB Streamlit).
- **New Node.js Stack**: **~45MB RAM usage**. That is an 87.5% reduction in memory footprint!
- **Zero Dependencies**: Uses only standard Node.js libraries (`http`, `dgram`).
- **Responsive UI**: The frontend is a highly optimized, vanilla HTML file that loads instantly and works flawlessly on both desktop and mobile devices.

## Setup

1. Clone the repository.
2. Ensure Node.js is installed.
3. Copy `config.example.json` to `config.json`.
4. Edit `config.json` and insert your target device's MAC Address.

```json
{
    "PORT": 8080,
    "MAC_ADDRESS": "YOUR:MAC:ADDRESS:HERE",
    "BROADCAST_IP": "255.255.255.255",
    "UDP_PORT": 9
}
```

## Running the App

```bash
node server.js
```

Then open `http://<YOUR_PI_IP>:8080` in your browser.

## Running as a Service (systemd)

You can run this via systemd to keep it running in the background.

```ini
[Unit]
Description=Lightweight Node.js WOL App
After=network.target

[Service]
ExecStart=/usr/bin/node /home/pi/wol_app/server.js
WorkingDirectory=/home/pi/wol_app
StandardOutput=syslog
StandardError=syslog
Restart=always
User=pi
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```