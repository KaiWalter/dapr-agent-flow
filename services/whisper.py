import os
from dapr_agents import OpenAIAudioClient
from dapr_agents.types.llm import AudioTranscriptionRequest
from models.voice2action import TranscriptionRequest, TranscriptionResult


def transcribe_audio_file(req: TranscriptionRequest) -> TranscriptionResult:
    """Transcribe an audio file using OpenAI via dapr-agents OpenAIAudioClient.

    Preserves the existing contract: accepts TranscriptionRequest and returns
    TranscriptionResult(text=str).
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    if not os.path.isfile(req.audio_path):
        raise FileNotFoundError(f"Audio file not found: {req.audio_path}")

    client = OpenAIAudioClient()
    transcription_request = AudioTranscriptionRequest(
        model="whisper-1",
        file=req.audio_path,  # path string; client handles file opening/bytes
        # language can be provided optionally, e.g., language="en"
        prompt=req.terms_prompt if getattr(req, "terms_prompt", None) else None,
    )

    response = client.create_transcription(request=transcription_request)
    text = getattr(response, "text", "") or ""
    return TranscriptionResult(text=text)
