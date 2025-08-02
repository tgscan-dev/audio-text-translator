import whisper

model = whisper.load_model("turbo")
result = model.transcribe("/Users/thomas/repo/001/audio-text-translator/uploads/1.mp3")
print(result["text"])