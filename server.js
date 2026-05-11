const http = require('http');
const dgram = require('dgram');
const fs = require('fs');
const path = require('path');

const configPath = path.join(__dirname, 'config.json');
let config = {
    PORT: 8080,
    MAC_ADDRESS: '00:00:00:00:00:00',
    BROADCAST_IP: '255.255.255.255',
    UDP_PORT: 9
};

try {
    if (fs.existsSync(configPath)) {
        const fileConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
        config = { ...config, ...fileConfig };
    } else {
        console.warn('config.json not found, using default configuration.');
    }
} catch (err) {
    console.error('Error reading config.json:', err);
}

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

const server = http.createServer((req, res) => {
    if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
        fs.readFile(path.join(__dirname, 'index.html'), (err, data) => {
            if (err) {
                res.writeHead(500);
                res.end('Error loading index.html');
                return;
            }
            res.writeHead(200, { 'Content-Type': 'text/html' });
            res.end(data);
        });
    } else if (req.method === 'POST' && req.url === '/wake') {
        const packet = createMagicPacket(config.MAC_ADDRESS);
        const socket = dgram.createSocket('udp4');
        socket.bind(() => {
            socket.setBroadcast(true);
            socket.send(packet, 0, packet.length, config.UDP_PORT, config.BROADCAST_IP, (err) => {
                socket.close();
                if (err) {
                    console.error('Failed to send packet:', err);
                    res.writeHead(500);
                    res.end('Error');
                } else {
                    console.log('Magic packet sent to ' + config.MAC_ADDRESS);
                    res.writeHead(200);
                    res.end('OK');
                }
            });
        });
    } else {
        res.writeHead(404);
        res.end('Not Found');
    }
});

server.listen(config.PORT, '0.0.0.0', () => {
    console.log(`WOL Server running at http://0.0.0.0:${config.PORT}/`);
});