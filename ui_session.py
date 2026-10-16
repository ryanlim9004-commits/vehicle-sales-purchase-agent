"""Per-tab presentation state; no automatic disk persistence or shared customer memory."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
from threading import Lock
from uuid import uuid4
from agent_controller import AgentController, explicit_goal
from form_inputs import INTENTS

SNAPSHOT_DATE = date(2026, 10, 15)
_INFERENCE_LOCK = Lock()


# Only GPU access is shared across tabs; customer facts never live here.
def inference_lock():
    return _INFERENCE_LOCK


@dataclass
class UISession:
    # Only this tab owns this mutable controller. Never cache it globally.
    controller: AgentController = field(default_factory=lambda: AgentController(as_of=SNAPSHOT_DATE))
    history: list = field(default_factory=list)
    last_response: dict | None = None
    completed_requests: dict = field(default_factory=dict)
    generation: int = 0

    # A request ID prevents a Streamlit rerun from submitting the same turn twice.
    def submit(self, text, *, goal, form_patch=None, request_id=None):
        request_id = request_id or uuid4().hex
        if request_id in self.completed_requests:
            return self.completed_requests[request_id]
        if form_patch is None and text.strip().lower() not in ('/reset', '/stop', 'reset', 'start over', 'stop', 'cancel'):
            if explicit_goal(text) is None and self.controller.state.goal != goal:
                text = INTENTS[goal] + '\n' + text
        response = self.controller.handle(text, form_patch=form_patch)
        self.history.append({'user': text, 'response': response})
        self.history = self.history[-20:]
        self.last_response = response
        self.completed_requests[request_id] = response
        self.completed_requests = dict(list(self.completed_requests.items())[-20:])
        self.generation += 1  # New form widget IDs clear old input drafts.
        if response['status'] == 'reset':
            self.history = []
            self.last_response = None
            self.completed_requests = {}
        return response

    # Reset clears UI drafts/history as well as the Controller's replacement state.
    def reset(self):
        self.submit('/reset', goal=self.controller.state.goal or 'buy')

    # Evidence is downloaded only at the user's request; no file is written here.
    def export_json(self):
        return json.dumps({'export_version': 1, 'exported_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
                           'snapshot_date': SNAPSHOT_DATE.isoformat(), 'consultation_as_of': self.controller.as_of.isoformat(),
                           'data_mode': 'Saved snapshot demonstration; not live inventory',
                           'model': getattr(self.controller.backend, 'model', type(self.controller.backend).__name__),
                           'state': self.controller.state.model_dump(mode='json'), 'conversation': self.history,
                           'note': 'Consultation evidence export; not an automatic restore/import file or a transaction record.'},
                          ensure_ascii=False, indent=2, allow_nan=False)


# Render a link only for a saved HTTP(S) source, never arbitrary active content.
def source_url(value):
    from urllib.parse import urlsplit
    parsed = urlsplit(value or '')
    return value if parsed.scheme in ('http', 'https') and parsed.netloc else None


# Numbers in checked results remain unknown when absent; zero is displayed explicitly.
def display_money(value):
    return 'Unknown' if value is None else f'MYR {value:,.2f}'


# Only a checked complete response may feed the current result cards/tables.
def verified_result(response):
    if not response or response.get('status') != 'complete':
        return None
    checks = response.get('checks', [])
    if not checks or not all(item.get('passed') is True for item in checks):
        return None
    return response.get('result')
