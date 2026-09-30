"""POC test config: isolated sqlite + temp storage, set before importing app."""
import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["SB_DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp.name}"
os.environ["SB_STORAGE_DIR"] = tempfile.mkdtemp(prefix="speech-book-data-")
os.environ["SB_POC_MODE"] = "true"
