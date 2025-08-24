from services.whisper import transcribe_audio_file
from models.voice2action import TranscriptionRequest, TranscriptionResult
import os
import logging

logger = logging.getLogger("transcribe_audio")

def transcribe_audio_activity(ctx, input: dict) -> dict:
    """
    Activity to transcribe an audio file using OpenAI Whisper and save the result as a JSON file next to the audio.
    Input: {
        'audio_path': str,  # Path to the audio file
        'mime_type': str,  # MIME type of the audio file
        'terms_file': str | None,  # Optional path to common terms file
    }
    Output: {
        'transcription_path': str,  # Path to the JSON transcription file
        'text': str,               # Transcribed text
    }
    """

    # Build optional prompt from terms file
    terms_prompt = None
    terms_file = input.get("terms_file")
    if terms_file:
        try:
            if os.path.isfile(terms_file):
                with open(terms_file, "r", encoding="utf-8") as f:
                    # one term per line, ignore blanks and comments
                    terms = [
                        ln.strip() for ln in f.readlines()
                        if (ln.strip() and not ln.strip().startswith("#"))
                    ]
                if terms:
                    # keep prompt concise to avoid oversized inputs
                    max_terms = 200
                    terms_limited = terms[:max_terms]
                    terms_joined = ", ".join(terms_limited)
                    terms_prompt = (
                        "Important domain terms that may appear in the audio."
                        " Prefer these spellings when applicable: " + terms_joined
                    )
            else:
                logger.warning("terms_file path not found: %s", terms_file)
        except Exception as e:
            logger.exception("Failed to read terms_file '%s': %s", terms_file, e)

    req = TranscriptionRequest(
        audio_path=input.get("audio_path"),
        mime_type=input.get("mime_type"),
        terms_prompt=terms_prompt,
    )
    result: TranscriptionResult = transcribe_audio_file(req)
    # Save transcription as JSON next to audio file
    json_path = os.path.splitext(req.audio_path)[0] + '.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        f.write(result.json())
    return {'transcription_path': json_path, 'text': result.text}
