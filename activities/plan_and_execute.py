import os
import json
from models.voice2action import ActionPlanRequest, ActionPlanResult, Action
from services.planner import plan_actions
from services.action_executor import execute_action

def plan_and_execute_activity(ctx, input: dict) -> dict:
    """
    Plan and execute actions based on a transcription. Writes a .actions.json next to the transcription.
    Input: { 'transcription_path': str }
    Output: { 'actions_path': str, 'executed': int }
    """
    req = ActionPlanRequest(**input)
    plan: ActionPlanResult = plan_actions(req)
    executed = 0
    # Execute actions (stubbed)
    for action in plan.actions:
        try:
            execute_action(action)
            executed += 1
        except Exception:
            # Keep going on failures; this is a stub executor
            pass
    # Save plan next to transcription
    actions_path = os.path.splitext(req.transcription_path)[0] + '.actions.json'
    with open(actions_path, 'w', encoding='utf-8') as f:
        json.dump({'actions': [a.model_dump() for a in plan.actions]}, f, ensure_ascii=False, indent=2)
    return {'actions_path': actions_path, 'executed': executed}
