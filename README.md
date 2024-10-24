# 🔮 Harbinger

A vigilant messenger that watches over your Docker containers and reports their status to Slack. Like a digital herald for your containerized applications, Harbinger provides real-time notifications about container lifecycle events.

![Python](https://img.shields.io/badge/python-v3.6+-blue.svg)
![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🌟 Features

- 📊 Real-time monitoring of Docker container events
- 🐳 Support for both standalone containers and docker-compose services
- 🔔 Elegant Slack notifications with detailed container information
- 📝 Automatic log capture when containers exit
- 🎨 Color-coded status messages for different events
- ⚡ Low overhead and resource usage
- 🛠️ Easy configuration through environment variables

## 📋 Prerequisites

- Python 3.6+
- Docker Engine
- Slack Webhook URL
- Linux environment (tested on Ubuntu)

## 🚀 Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/luissarabando/harbinger.git
cd harbinger
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment variables**
```bash
# Create .env file
cp .env.example .env

# Edit your configuration
vim .env
```

4. **Run as a service**
```bash
# Copy service file
sudo cp harbinger.service /etc/systemd/system/

# Enable and start service
sudo systemctl enable harbinger
sudo systemctl start harbinger
```

## ⚙️ Configuration

Create a `.env` file with the following variables:

```ini
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
MONITOR_ENV=production
MONITOR_HOST=your-host-name
LOG_LINES=5
```

## 🔍 Example Notifications

Harbinger provides detailed, color-coded notifications for various container events:

- 🟢 Container starts
- 🔴 Container exits (with error codes)
- 💀 Container kills
- 🔄 Container restarts

## 🛠️ Running as a Service

Harbinger can be run as a systemd service for reliable operation:

```ini
[Unit]
Description=Harbinger Docker Monitor
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=root
Group=docker
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=/path/to/harbinger
ExecStart=/usr/bin/python3 harbinger.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 📝 Logs

Monitor Harbinger's operation through its logs:

```bash
# View service logs
sudo journalctl -u harbinger -f

# Check application logs
tail -f /var/log/harbinger.log
```

## 🐋 Docker Compose Support

Harbinger automatically detects and provides additional context for docker-compose services, including:

- Project name
- Service name
- Container relationships
- Compose-specific events

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ✨ Author

**Luis Sarabando**

- GitHub: [@luissarabando](https://github.com/luis15pt)

## 🙏 Acknowledgments

- Thanks to the Docker team for their excellent API
- Inspired by the need for better container monitoring
- Built with Python and ❤️

---
*May Harbinger watch over your containers with unwavering vigilance.*
