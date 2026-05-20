# Telegram VPN Bot

Telegram VPN bot with:

- VPN subscription management
- Admin panel
- Payment requests
- User support system
- Subscription management
- QR-code VPN access
- Broadcast system
- Statistics
- SQLite database

---

# Features

## User Features

- User profile
- VPN purchase system
- Tariff selection
- Subscription status
- VPN config retrieval
- QR-code generation
- Built-in support chat

---

## Admin Features

- Admin panel
- User management
- Approve subscriptions
- Remove subscriptions
- Recreate VPN configs
- Pending payment requests
- Broadcast messages
- User statistics
- Telegram username display

---

# Tech Stack

- Python
- pyTelegramBotAPI
- SQLite
- WireGuard / VPN API

---

# Installation

## Clone repository

```bash
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

## Configure bot

Edit `config.py`

```python
BOT_TOKEN = "TOKEN"
ADMIN_ID = [123456789]

DB_PATH = "database/bot.db"
```

---

## Run bot

```bash
python main.py
```

---

# Database

The bot automatically creates:

- users table
- pending_payments table

---

# Project Structure

```text
database/
    db.py
handlers/
    admin_handlers.py
    user_handlers.py
services/
    sub_checker.py
    vpn.py
utils/
    error_handler.py
    qr.py
    rate_limiter.py
config.py
main.py
```

---

# TODO

- Auto-renew subscriptions
- Payment gateway integration
- Trial subscriptions
- Referral system
- Multi-admin roles
- PostgreSQL support
- Backup system

---

# License

MIT License