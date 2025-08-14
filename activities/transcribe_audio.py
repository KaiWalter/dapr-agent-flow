from services.whisper import transcribe_audio_file
from models.voice2action import TranscriptionRequest, TranscriptionResult
import os

def transcribe_audio_activity(ctx, input: dict) -> dict:
    """
    Activity to transcribe an audio file using OpenAI Whisper and save the result as a JSON file next to the audio.
    Input: {
        'audio_path': str,  # Path to the audio file
        'mime_type': str,  # MIME type of the audio file
    }
    Output: {
        'transcription_path': str,  # Path to the JSON transcription file
        'text': str,               # Transcribed text
    }
    """
    req = TranscriptionRequest(**input)
    result: TranscriptionResult = transcribe_audio_file(req)
    # Save transcription as JSON next to audio file
    json_path = os.path.splitext(req.audio_path)[0] + '.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(result.json())
    return {'transcription_path': json_path, 'text': result.text}
