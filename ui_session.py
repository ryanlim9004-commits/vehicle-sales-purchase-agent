"""Per-tab presentation state; no automatic disk persistence or shared customer memory."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
from threading import Lock, Event, Thread
import time
from uuid import uuid4
from agent_controller import AgentController, OllamaBackend, explicit_goal
from form_inputs import INTENTS

SNAPSHOT_DATE = date(2026, 10, 15)
_INFERENCE_LOCK = Lock()


# Only GPU access is shared across tabs; customer facts never live here.
def inference_lock():
    return _INFERENCE_LOCK


@dataclass
class BackgroundTurn:
    """An isolated, cancellable turn; it never writes directly into visible state."""
    working: object
    text: str
    goal: str
    form_patch: object
    request_id: str
    cancellation: Event
    done: Event = field(default_factory=Event)
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    cancelled_at: float | None = None
    response: dict | None = None
    error: str | None = None
    thread: Thread | None = None

    def cancel(self):
        if self.done.is_set():
            return False
        if not self.cancellation.is_set():
            self.cancelled_at = time.monotonic()
            self.cancellation.set()
        return True

    def run(self):
        try:
            self.response = self.working.submit(self.text, goal=self.goal, form_patch=self.form_patch, request_id=self.request_id)
        except BaseException as error:
            self.error = type(error).__name__
        finally:
            self.finished_at = time.monotonic()
            # Release before signalling completion so a finished turn cannot
            # leave the next consultation blocked on the shared model lock.
            _INFERENCE_LOCK.release()
            self.done.set()


@dataclass
class UISession:
    # Only this tab owns this mutable controller. Never cache it globally.
    controller: AgentController = field(default_factory=lambda: AgentController(as_of=SNAPSHOT_DATE))
    history: list = field(default_factory=list)
    last_response: dict | None = None
    completed_requests: dict = field(default_factory=dict)
    generation: int = 0
    active_turn: BackgroundTurn | None = None

    def start_background(self, text, *, goal, form_patch=None, request_id=None):
        """Start only after acquiring the model lock; return False if it is busy."""
        if self.active_turn is not None:
            raise ValueError('Finish or stop the current calculation before sending another request.')
        request_id = request_id or uuid4().hex
        if request_id in self.completed_requests:
            return True
        if not _INFERENCE_LOCK.acquire(blocking=False):
            return False
        try:
            cancellation = Event()
            base = self.controller
            # A real request owns a new backend and cancellation token. Test
            # adapters retain their scripted queue; visible memory stays private.
            backend = OllamaBackend(base.backend.model) if isinstance(base.backend, OllamaBackend) else base.backend
            controller = AgentController(state=base.state.model_copy(deep=True), backend=backend, cars=base.cars,
                                         as_of=base.as_of, limits=base.limits, clock=base.clock, cancellation=cancellation)
            working = UISession(controller, list(self.history), self.last_response, dict(self.completed_requests), self.generation)
            job = BackgroundTurn(working, text, goal, form_patch, request_id, cancellation)
            self.active_turn = job
            job.thread = Thread(target=job.run, name='vehicle-consultation', daemon=True)
            job.thread.start()
            return True
        except BaseException:
            self.active_turn = None
            _INFERENCE_LOCK.release()
            raise

    def finish_background(self):
        """Publish one completed turn; a cancelled turn's partial state is discarded."""
        job = self.active_turn
        if job is None or not job.done.is_set():
            return None
        if job.cancellation.is_set() or job.error:
            state = self.controller.state
            state.turn += 1
            state.ranked_vehicle_ids = []
            state.selected_vehicle_id = None
            cancelled = job.cancellation.is_set()
            state.event('system', action='cancelled_background_turn' if cancelled else 'background_turn_failed', request_id=job.request_id)
            response = self.controller._response('cancelled' if cancelled else 'model_error',
                'Calculation stopped. Your previously confirmed details are kept. You can send another message.' if cancelled else
                'The calculation could not finish. Your previously confirmed details are kept; please try again.')
            self.history = (self.history + [{'user': job.text, 'response': response}])[-20:]
            self.last_response = response
            self.completed_requests[job.request_id] = response
            self.completed_requests = dict(list(self.completed_requests.items())[-20:])
            self.generation += 1
        else:
            self.controller.state = job.working.controller.state
            self.history = job.working.history
            self.last_response = job.working.last_response
            self.completed_requests = job.working.completed_requests
            self.generation = job.working.generation
            response = job.response
        self.active_turn = None
        return response

    # A request ID prevents a Streamlit rerun from submitting the same turn twice.
    def submit(self, text, *, goal, form_patch=None, request_id=None):
        if self.active_turn is not None:
            raise ValueError('Finish or stop the current calculation before sending another request.')
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
