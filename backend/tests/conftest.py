import os
from tempfile import TemporaryDirectory


_pytest_data = TemporaryDirectory(prefix="paperpilot-pytest-")
_root = _pytest_data.name
os.environ["PAPERPILOT_DATA_DIR"] = os.path.join(_root, "data")
os.environ["PAPERPILOT_DATABASE_PATH"] = os.path.join(_root, "data", "neuronexus.sqlite3")
os.environ["PAPERPILOT_UPLOAD_DIR"] = os.path.join(_root, "uploads")
os.environ["PAPERPILOT_OUTPUT_DIR"] = os.path.join(_root, "outputs")


def pytest_sessionstart(session):
    from backend.database import init_db

    init_db()