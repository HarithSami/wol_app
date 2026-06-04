const http = require('http');
const dgram = require('dgram');
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');

const configPath = path.join(__dirname, 'config.json');
let config = {
    PORT: 8080,
    DEVICES: [],
    BROADCAST_IP: '255.255.255.255',
    UDP_PORT: 9
};

function loadConfig() {
    try {
        if (fs.existsSync(configPath)) {
            const fileConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
            config = { ...config, ...fileConfig };
        }
    } catch (err) {
        console.error('Error reading config.json:', err);
    }
}

loadConfig();

function createMagicPacket(mac) {
    const macBytes = mac.split(':').map(hex => parseInt(hex, 16));
    const packet = Buffer.alloc(102);
    for (let i = 0; i < 6; i++) packet[i] = 0xFF;
    for (let i = 1; i <= 16; i++) {
        for (let j = 0; j < 6; j++) {
            packet[i * 6 + j] = macBytes[j];
        }
    }
    return packet;
}

function checkStatus(ip) {
    return new Promise((resolve) => {
        const cmd = process.platform === 'win32' ? `ping -n 1 -w 500 ${ip}` : `ping -c 1 -W 1 ${ip}`;
        exec(cmd, (err) => {
            resolve(!err);
        });
    });
}

const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    
    if (req.method === 'GET') {
        if (url.pathname === '/' || url.pathname === '/index.html') {
            fs.readFile(path.join(__dirname, 'index.html'), (err, data) => {
                if (err) {
                    res.writeHead(500);
                    res.end('Error loading index.html');
                    return;
                }
                res.writeHead(200, { 'Content-Type': 'text/html' });
                res.end(data);
            });
        } else if (url.pathname === '/api/devices') {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify(config.DEVICES));
        } else if (url.pathname === '/api/status') {
            const ip = url.searchParams.get('ip');
            if (!ip) {
                res.writeHead(400);
                res.end('Missing IP');
                return;
            }
            const isOnline = await checkStatus(ip);
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ online: isOnline }));
        }
    } else if (req.method === 'POST' && url.pathname === '/wake') {
        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', () => {
            try {
                const { mac } = JSON.parse(body);
                if (!mac) throw new Error('Missing MAC');
                
                const packet = createMagicPacket(mac);
                const socket = dgram.createSocket('udp4');
                socket.bind(() => {
                    socket.setBroadcast(true);
                    socket.send(packet, 0, packet.length, config.UDP_PORT, config.BROADCAST_IP, (err) => {
                        socket.close();
                        if (err) {
                            res.writeHead(500);
                            res.end('Error');
                        } else {
                            res.writeHead(200);
                            res.end('OK');
                        }
                    });
                });
            } catch (err) {
                res.writeHead(400);
                res.end('Invalid request');
            }
        });
    } else {
        res.writeHead(404);
        res.end('Not Found');
    }
});

server.listen(config.PORT, '0.0.0.0', () => {
    console.log(`WOL Server running at http://0.0.0.0:${config.PORT}/`);
});