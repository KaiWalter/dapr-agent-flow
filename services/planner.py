import os
import requests
import json
from models.voice2action import ActionPlanRequest, ActionPlanResult, Action

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_CLASSIFICATION_MODEL = os.environ.get('OPENAI_CLASSIFICATION_MODEL', 'gpt-4.1-mini')
OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'

SYSTEM_PROMPT = (
    "You are an assistant that turns transcriptions into action plans. "
    "Always return strict JSON with an 'actions' array. "
    "Supported actions: create_task (payload: {title: string}), send_email (payload: {to?: string, subject?: string, body?: string}). "
    "If the user mentions creating a task or reminder, emit create_task. Otherwise, emit a single send_email as fallback."
)

def plan_actions(req: ActionPlanRequest) -> ActionPlanResult:
    with open(req.transcription_path, 'r', encoding='utf-8') as f:
        transcription = json.load(f)
    text = transcription['text'] if isinstance(transcription, dict) else str(transcription)
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': OPENAI_CLASSIFICATION_MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': text}
        ],
        'temperature': 0.0
    }
    resp = requests.post(OPENAI_CHAT_URL, headers=headers, json=data)
    resp.raise_for_status()
    content = resp.json()['choices'][0]['message']['content']
    try:
        parsed = json.loads(content)
    except Exception:
        import re
        m = re.search(r'\{.*\}', content, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else {'actions': [{'type': 'send_email', 'payload': {'body': text}}]}
    actions = [Action(**a) for a in parsed.get('actions', [])]
    if not actions:
        actions = [Action(type='send_email', payload={'body': text})]
    return ActionPlanResult(actions=actions)
