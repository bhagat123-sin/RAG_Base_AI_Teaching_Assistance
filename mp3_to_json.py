import os
import json
import whisper

modal = whisper.load_model("small")

audios = os.listdir("audioS")

for audio in audios:
    if audio.lower().endswith(".mp3"):
        filename = os.path.splitext(audio)[0]

        # Split at the first space
        numbers, title = filename.split(" ", 1)

        print(numbers, title)

        result = modal.transcribe( audio = f"audioS/{audio}",
                                   language = "hi",
                                    task = "translate",
                                    word_timestamps = False)

        chunks = []
        for segment in result['segments']:
            chunks.append({"numbers": numbers, "title": title, "start": segment['start'], "end": segment['end'], "text": segment['text']})

            chunks_with_metadata = {"chunks": chunks, "text" : result["text"]}

        with open(f"jsons/{audio}.json","w") as f:
            json.dump(chunks_with_metadata, f)