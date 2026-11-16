from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_PATH = DATA_DIR / "lessons.json"
TOPICS_PATH = DATA_DIR / "topics.txt"
LEVELS_PATH = DATA_DIR / "levels.json"
EMBEDDINGS_PATH = DATA_DIR / "chunk_embeddings.npz"
PRACTICE_LOG_PATH = DATA_DIR / "practice_log.json"
