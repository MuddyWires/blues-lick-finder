"""Small file helpers shared by the data code."""

import os
import tempfile
from pathlib import Path


def write_text_atomic(path, text):
    """Write `text` so a crash never leaves a half-written file: write a temp
    file in the same folder, then swap it in with os.replace."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
