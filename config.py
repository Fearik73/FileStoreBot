import logging
import os
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv

_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env")
if os.path.exists(_ENV_FILE):
    load_dotenv(_ENV_FILE)
else:
    load_dotenv()


def _env(name, default):
    value = os.environ.get(name)
    return default if value is None or not value.strip() else value.strip()


def _required(name):
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise SystemExit(f"❌ Missing required variable {name}.\nFill it in config.env")
    return value.strip()


# ---------------- Telegram / bot ----------------
API_ID = int(_required("API_ID"))
API_HASH = _required("API_HASH")
TOKEN = _required("TOKEN")
SESSION = _required("SESSION")
OWNER_ID = int(_required("OWNER_ID"))
ADMINS = [int(x) for x in _env("ADMINS", "").split(",") if x.strip()]
DB_CHANNEL = int(_required("DB_CHANNEL"))
WORKERS = int(_env("WORKERS", "5"))
PORT = _env("PORT", "5010")
LOG_FILE_NAME = _env("LOG_FILE_NAME", "bot.log")
MSG_EFFECT = int(_env("MSG_EFFECT", "0")) or None

# ---------------- Database ----------------
DB_URI = _required("DB_URI")
DB_NAME = _required("DB_NAME")

# --------------- Start Buttons -----------------
START_BUTTON='[
  {"name": "Ongoing Anime", "url": "http://t.me/Od3nsLinks_bot?start=18LTEwMDI2NzQyMDM5NTu9cVY="},
  {"name": "Finished Anime", "url": "http://t.me/Od3nsLinks_bot?start=16LTEwMDI2NjMwODUzH19vNzg="}
]'

# ---------------- Bot settings ----------------
AUTO_DEL = int(_env("AUTO_DEL", "300"))
PROTECT = _env("PROTECT", "true").lower() in ("1", "true", "yes", "on")

# ---------------- Shortener ----------------
SHORT_URL = _env("SHORT_URL", "")
SHORT_API = _env("SHORT_API", "")
SHORT_TUT = _env("SHORT_TUT", "")

# ---------------- Messages ----------------
MESSAGES = {k: v for k, v in {
    "START": os.environ.get("START_MSG"),
    "FSUB": os.environ.get("FSUB_MSG"),
    "SHORT_MSG": os.environ.get("SHORT_MSG"),
    "START_PHOTO": os.environ.get("START_PHOTO"),
    "FSUB_PHOTO": os.environ.get("FSUB_PHOTO"),
    "SHORT_PIC": os.environ.get("SHORT_PIC"),
    "SHORT": os.environ.get("SHORT_PANEL_PIC"),
}.items() if v}


def LOGGER(name: str, client_name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    formatter = logging.Formatter(
        f"[%(asctime)s - %(levelname)s] - {client_name} - %(name)s - %(message)s",
        datefmt='%d-%b-%y %H:%M:%S'
    )
    file_handler = RotatingFileHandler(LOG_FILE_NAME, maxBytes=50_000_000, backupCount=10)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
    
