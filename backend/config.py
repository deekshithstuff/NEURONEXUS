import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("PAPERPILOT_DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = Path(os.environ.get("PAPERPILOT_UPLOAD_DIR", DATA_DIR / "uploads"))
OUTPUT_DIR = Path(os.environ.get("PAPERPILOT_OUTPUT_DIR", BASE_DIR / "outputs"))
DATABASE_PATH = Path(os.environ.get("PAPERPILOT_DATABASE_PATH", DATA_DIR / "neuronexus.sqlite3"))
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = {".docx", ".pdf"}

for directory in (DATA_DIR, UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)
