import logging
import os
from logging.handlers import RotatingFileHandler

import json

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
    
# ----------------- Effect ID ---------------------------

MSG_EFFECT = 5046509860389126442

# ---------------- Telegram ----------------
API_ID = int(_required("API_ID"))
API_HASH = _required("API_HASH")
TOKEN = _required("TOKEN")
SESSION = _required("SESSION")
ADMIN_ID = int(_env("ADMIN_ID", "7375326036"))
OWNER_ID = ADMIN_ID
ADMINS = [ADMIN_ID]
DB_CHANNEL = int(_required("DB_CHANNEL"))
WORKERS = int(_env("WORKERS", "5"))
LOG_FILE_NAME = _env("LOG_FILE_NAME", "bot.log")

# ---------------- Updater ----------------
UPSTREAM_REPO = _env("UPSTREAM_REPO", "https://github.com/Fearik73/FileStoreBot")
UPSTREAM_BRANCH = _env("UPSTREAM_BRANCH", "main")
os.environ["UPSTREAM_REPO"] = UPSTREAM_REPO
os.environ["UPSTREAM_BRANCH"] = UPSTREAM_BRANCH

# ---------------- Updater ----------------
UPSTREAM_REPO = _env("UPSTREAM_REPO", "https://github.com/Fearik73/FileStoreBot")
UPSTREAM_BRANCH = _env("UPSTREAM_BRANCH", "main")

# ---------------- Database ----------------
DB_URI = _required("DB_URI")
DB_NAME = _required("DB_NAME")

# --------------- Start Buttons -----------------
_START_BUTTON_RAW = _env("START_BUTTON", '''[
  {"name": "Ongoing Anime", "url": "http://t.me/Od3nsLinks_bot?start=18LTEwMDI2NzQyMDM5NTu9cVY="},
  {"name": "Finished Anime", "url": "http://t.me/Od3nsLinks_bot?start=16LTEwMDI2NjMwODUzH19vNzg="}
]''')
try:
    START_BUTTON = [b for b in json.loads(_START_BUTTON_RAW) if b.get("name") and b.get("url")]
except Exception:
    START_BUTTON = []

# ---------------- Bot settings ----------------
AUTO_DEL = int(_env("AUTO_DEL", "300"))

# ---------------- Shortener ----------------
SHORT_URL = _env("SHORT_URL", "")
SHORT_API = _env("SHORT_API", "")
SHORT_TUT = _env("SHORT_TUT", "")

# ---------------- Messages ----------------
def _msg(name, default):
    value = os.environ.get(name)
    return value.replace("\\n", "\n") if value and value.strip() else default


MESSAGES = {
    "START": _msg("START_MSG", "<b>›› ʜᴇʏ!!, {first} ~ <blockquote>ʟᴏᴠᴇ ᴘᴏʀɴʜᴡᴀ? ɪ ᴀᴍ ᴍᴀᴅᴇ ᴛᴏ ʜᴇʟᴘ ʏᴏᴜ ᴛᴏ ғɪɴᴅ ᴡʜᴀᴛ ʏᴏᴜ aʀᴇ ʟᴏᴏᴋɪɴɢ ꜰᴏʀ.</blockquote></b>"),
    "FSUB": _msg("FSUB_MSG", "<b><blockquote>›› ʜᴇʏ ×</blockquote>\n  ʏᴏᴜʀ ғɪʟᴇ ɪs ʀᴇᴀᴅʏ ‼️ ʟᴏᴏᴋs ʟɪᴋᴇ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ sᴜʙsᴄʀɪʙᴇᴅ ᴛᴏ ᴏᴜʀ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ, sᴜʙsᴄʀɪʙᴇ ɴᴏᴡ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇs</b>"),
    "SHORT_MSG": _msg("SHORT_MSG", "<b>📊 ʜᴇʏ {first}, \n\n‼️ ɢᴇᴛ ᴀʟʟ ꜰɪʟᴇꜱ ɪɴ ᴀ ꜱɪɴɢʟᴇ ʟɪɴᴋ ‼️\n\n ⌯ ʏᴏᴜʀ ʟɪɴᴋ ɪꜱ ʀᴇᴀᴅʏ, ᴋɪɴᴅʟʏ ᴄʟɪᴄᴋ ᴏɴ ᴏᴘᴇɴ ʟɪɴᴋ ʙᴜᴛᴛᴏɴ..</b>"),
    "START_PHOTO": _msg("START_PHOTO", "https://graph.org/file/510affa3d4b6c911c12e3.jpg"),
    "FSUB_PHOTO": _msg("FSUB_PHOTO", "https://telegra.ph/file/7a16ef7abae23bd238c82-b8fbdcb05422d71974.jpg"),
    "SHORT_PIC": _msg("SHORT_PIC", "https://telegra.ph/file/7a16ef7abae23bd238c82-b8fbdcb05422d71974.jpg"),
    "SHORT": _msg("SHORT_PANEL_PIC", "https://telegra.ph/file/8aaf4df8c138c6685dcee-05d3b183d4978ec347.jpg"),
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

