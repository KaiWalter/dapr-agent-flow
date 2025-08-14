from services.classifier import classify_transcription
from models.voice2action import ClassificationRequest, ClassificationResult
import os

def classify_transcription_activity(ctx, input: dict) -> dict:
    """
    Activity to classify a transcription using OpenAI and save the result as a JSON file next to the audio.
    Input: {
        'transcription_path': str,  # Path to the transcription JSON file
        'prompt_path': str,         # Path to the prompt file
    }
    Output: {
        'classification_path': str,  # Path to the evaluated JSON file
        'result': dict,              # Classification result
    }
    """
    import json
    req = ClassificationRequest(**input)
    result: ClassificationResult = classify_transcription(req)
    # Save classification as JSON object next to transcription file
    eval_path = os.path.splitext(req.transcription_path)[0] + '.evaluated.json'
    with open(eval_path, 'w', encoding='utf-8') as f:
        json.dump(result.result, f, ensure_ascii=False, indent=2)
    return {'classification_path': eval_path, 'result': result.result}
