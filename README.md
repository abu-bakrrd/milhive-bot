# Milhive Bot

Telegram bot for product publishing with photo processing and Instagram integration.

## Project Structure

- `main.py`: Main bot script (Windows/EXE version).
- `vps_deploy/`: Version optimized for Ubuntu VPS.
  - `main.py`: Adapted for Linux.
  - `setup.sh`: Automated install script.
  - `milhive_bot.service`: Systemd service config.
- `product/`: Configuration files for production.
- `requirements.txt`: Python dependencies.

## Features

- Background removal and overlaying on custom backdrops.
- Automatic price calculation.
- Simultaneous posting to Telegram channel and Instagram.
- Automated deployment for VPS.

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials.
2. Install dependencies: `pip install -r requirements.txt` (or use `vps_deploy/setup.sh` on Linux).
3. Run `python main.py`.
