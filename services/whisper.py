import os
import requests
from models.voice2action import TranscriptionRequest, TranscriptionResult

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_WHISPER_URL = 'https://api.openai.com/v1/audio/transcriptions'

def transcribe_audio_file(req: TranscriptionRequest) -> TranscriptionResult:
    """
    Calls OpenAI Whisper API to transcribe the given audio file.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }
    # Use a context manager to ensure file handle is closed
    with open(req.audio_path, 'rb') as f:
        files = {
            'file': (os.path.basename(req.audio_path), f, req.mime_type),
            'model': (None, 'whisper-1'),
            'response_format': (None, 'json')
        }
        response = requests.post(OPENAI_WHISPER_URL, headers=headers, files=files)
    response.raise_for_status()
    data = response.json()
    return TranscriptionResult(text=data.get('text', ''))
