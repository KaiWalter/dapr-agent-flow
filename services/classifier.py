import os
import requests
from models.voice2action import ClassificationRequest, ClassificationResult
import json

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_CLASSIFICATION_MODEL = os.environ.get('OPENAI_CLASSIFICATION_MODEL', 'gpt-4.1-mini')
OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'

def classify_transcription(req: ClassificationRequest) -> ClassificationResult:
    with open(req.transcription_path, 'r', encoding='utf-8') as f:
        transcription = json.load(f)
    transcription_text = transcription['text'] if isinstance(transcription, dict) and 'text' in transcription else transcription
    # Download prompt from OneDrive to a temp file
    from services.onedrive import OneDriveService
    http = __import__('services.http_client', fromlist=['HttpClient']).HttpClient()
    svc = OneDriveService(http)
    import tempfile
    with tempfile.NamedTemporaryFile('w+', delete=False, encoding='utf-8') as tmpf:
        svc.download_file_by_path(req.prompt_onedrive_path, tmpf.name)
        tmpf.flush()
        tmpf.seek(0)
        prompt = tmpf.read()
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': OPENAI_CLASSIFICATION_MODEL,
        'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': transcription['text']}
        ],
        'temperature': 0.0
    }
    response = requests.post(OPENAI_CHAT_URL, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    content = result['choices'][0]['message']['content']
    # Try to parse the LLM output as JSON
    try:
        parsed = json.loads(content)
    except Exception:
        # fallback: try to extract JSON substring
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
        else:
            raise ValueError('LLM did not return valid JSON')
    # Always include the transcription in the result
    if isinstance(parsed, dict):
        parsed['transcription'] = transcription_text
    return ClassificationResult(result=parsed)
