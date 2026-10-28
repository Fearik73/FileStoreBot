import json
import logging
import os
import re
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


# ----------------- Effect IDs ---------------------------
MESSAGE_EFFECT_ID = 5104841245755180586
BROADCAST_EFFECT_ID = 5046509860389126442

# ---------------- Telegram ----------------
API_ID = int(_required("API_ID"))
API_HASH = _required("API_HASH")
TOKEN = _required("TOKEN")
SESSION = _required("SESSION")
ADMIN_IDS = [int(i) for i in re.split(r"[,\s]+", _env("ADMIN_IDS", "7375326036")) if i]
DB_CHANNEL = int(_required("DB_CHANNEL"))
WORKERS = int(_env("WORKERS", "200"))
LOG_FILE_NAME = _env("LOG_FILE_NAME", "bot.log")

# ---------------- Updater ----------------
UPSTREAM_REPO = _env("UPSTREAM_REPO", "https://github.com/Fearik73/FileStoreBot")
UPSTREAM_BRANCH = _env("UPSTREAM_BRANCH", "main")

# ---------------- Database ----------------
DB_URI = _required("DB_URI")
DB_NAME = _required("DB_NAME")
USERS_COLLECTION = _env("USERS_COLLECTION", "users")
FSUB_COLLECTION = _env("FSUB_COLLECTION", "fsub")
REQUEST_COLLECTION = _env("REQUEST_COLLECTION", "request_sub")
SETTINGS_COLLECTION = _env("SETTINGS_COLLECTION", "settings")

# --------------- Start Buttons -----------------
_START_BUTTON_RAW = _env("START_BUTTON", '''[
  {"name": "Ongoing Anime", "url": "http://t.me/Od3nsLinks_bot?start=18LTEwMDI2NzQyMDM5NTu9cVY="},
  {"name": "Finished Anime", "url": "http://t.me/Od3nsLinks_bot?start=16LTEwMDI2NjMwODUzH19vNzg="}
]''')
try:
    START_BUTTON = [b for b in json.loads(_START_BUTTON_RAW) if b.get("name") and b.get("url")]
except Exception:
    START_BUTTON = []

# ---------------- Shortener ----------------
SHORT_URL = _env("SHORT_URL", "")
SHORT_API = _env("SHORT_API", "")
SHORT_TUT = _env("SHORT_TUT", "")

# ---------------- Messages ----------------
def _photo(name, default):
    value = os.environ.get(name)
    return default if value is None else value.strip()


def _msg(name, default):
    value = os.environ.get(name)
    return value.replace("\\n", "\n") if value and value.strip() else default


SETTINGS_IMAGE = _photo("SETTINGS_IMAGE", "https://files.catbox.moe/3yxex9.jpg")

MESSAGES = {
    "START": _msg("START_MSG", "<b>›› Hello {first},\n\nI can store private files in Specified Channel and other users can access it from special link.\n\n<blockquote>Visit - @Od3ns_Animes</blockquote></b>"),
    "FSUB": _msg("FSUB_MSG", "<b>⚠️ Subscription Required...</b>\n\nYou haven't joined the required channel(s) yet! Please join them to use me."),
    "SHORT_MSG": _msg("SHORT_MSG", "<b>📊 ʜᴇʏ {first}, \n\n‼️ ɢᴇᴛ ᴀʟʟ ꜰɪʟᴇꜱ ɪɴ ᴀ ꜱɪɴɢʟᴇ ʟɪɴᴋ ‼️\n\n ⌯ ʏᴏᴜʀ ʟɪɴᴋ ɪꜱ ʀᴇᴀᴅʏ, ᴋɪɴᴅʟʏ ᴄʟɪᴄᴋ ᴏɴ ᴏᴘᴇɴ ʟɪɴᴋ ʙᴜᴛᴛᴏɴ..</b>"),
    "START_PHOTO": _photo("START_PHOTO", ""),
    "FSUB_PHOTO": _photo("FSUB_PHOTO", ""),
    "SHORT_PIC": _photo("SHORT_PIC", ""),
}


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

