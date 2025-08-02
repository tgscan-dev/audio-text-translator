import whisper


def speech2text(src_path: str):
    model = whisper.load_model("turbo")
    result = model.transcribe(src_path)
    return result["text"]
