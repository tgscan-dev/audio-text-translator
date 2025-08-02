import asyncio
import os

import whisper
from tenacity import retry, stop_after_attempt, wait_none

# Get project root directory
ROOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "uploads")

# Initialize whisper model at module level
_model = whisper.load_model("turbo")


@retry(stop=stop_after_attempt(3), wait=wait_none)
def speech2text(src_path: str):
    # Convert to absolute path
    full_path = os.path.join(ROOT_DIR, src_path)
    result = _model.transcribe(full_path)
    return result["text"]


def aspeech2text(src_path: str):
    return asyncio.to_thread(speech2text, src_path)


if __name__ == "__main__":
    print(speech2text("1.mp3"))
