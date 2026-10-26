"""Prove cancellation, isolated state, lock cleanup and read-only navigation."""
from datetime import date
import multiprocessing
from pathlib import Path
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from agent_controller import AgentController, OllamaBackend, ConsultationCancelled
from agent_state import SessionState
from buyer_profile import BuyerProfileFrame
from ui_session import UISession, inference_lock, verified_result
from test_agent import ScriptedBackend, sensed, planned, update

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 10, 15)


def waiting_request_worker(connection, payload):
    connection.send(('progress', None))
    time.sleep(20)


class BlockingPlanner(ScriptedBackend):
    def __init__(self):
        super().__init__(sensed(updates=[update('buyer.budget_myr', 1000000, 'RM1 million')]))
        self.entered = Event()
        self.owner = None

    def chat(self, messages, **options):
        if self.replies:
            return super().chat(messages, **options)
        self.entered.set()
        if not self.owner.active_turn.cancellation.wait(5):
            raise TimeoutError('Test did not request cancellation.')
        raise ConsultationCancelled()


def existing_customer(backend):
    state = SessionState(goal='buy', buyer=BuyerProfileFrame(budget_myr=60000, required_seats=5, usage=['city_commute']))
    return UISession(AgentController(state=state, backend=backend, as_of=AS_OF))


class CancellationTests(unittest.TestCase):
    def test_cancel_terminates_a_running_owned_process_without_waiting_for_timeout(self):
        backend = OllamaBackend()
        observed = []
        def run():
            try:
                backend.chat([], timeout_seconds=20)
            except Exception as error:
                observed.append(type(error))
        with patch('agent_controller._ollama_worker', waiting_request_worker):
            thread = Thread(target=run)
            thread.start()
            deadline = time.monotonic() + 5
            while not backend.received_stream_chunk and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(backend.received_stream_chunk)
            pid = backend.active_worker_pid
            started = time.monotonic()
            backend.cancellation.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertEqual(observed, [ConsultationCancelled])
        self.assertIsNone(backend.active_worker_pid)
        self.assertIsNotNone(backend.last_worker_exitcode)
        self.assertNotIn(pid, [process.pid for process in multiprocessing.active_children()])

    def test_cancel_does_not_retry_the_model_or_execute_tools(self):
        backend = ScriptedBackend(ConsultationCancelled())
        agent = AgentController(backend=backend, as_of=AS_OF)
        answer = agent.handle('I want to buy a car.')
        self.assertEqual(answer['status'], 'cancelled')
        self.assertEqual(len(backend.requests), 1)
        self.assertFalse(answer['tools'])

    def test_background_cancellation_discards_partial_facts_and_releases_model(self):
        backend = BlockingPlanner()
        ui = existing_customer(backend)
        backend.owner = ui
        self.assertTrue(ui.start_background('My budget is RM1 million.', goal='buy', request_id='cancel-me'))
        job = ui.active_turn
        self.assertTrue(backend.entered.wait(2))
        self.assertEqual(job.working.controller.state.buyer.budget_myr, 1000000)
        self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)
        self.assertTrue(job.cancel())
        self.assertTrue(job.done.wait(2))
        answer = ui.finish_background()
        self.assertEqual(answer['status'], 'cancelled')
        self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)
        self.assertEqual(ui.controller.state.buyer.usage, ['city_commute'])
        self.assertIsNone(verified_result(answer))
        self.assertEqual(len(ui.history), 1)
        self.assertIsNone(ui.finish_background())
        self.assertTrue(inference_lock().acquire(blocking=False))
        inference_lock().release()

    def test_success_commits_once_and_duplicate_request_does_not_restart(self):
        backend = ScriptedBackend(sensed(updates=[update('buyer.budget_myr', 40000, 'RM40000')]),
                                  planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        ui = existing_customer(backend)
        self.assertTrue(ui.start_background('My budget is RM40000.', goal='buy', request_id='once'))
        job = ui.active_turn
        self.assertTrue(job.done.wait(2))
        self.assertFalse(job.cancel())
        self.assertEqual(ui.finish_background()['status'], 'complete')
        self.assertEqual(ui.controller.state.buyer.budget_myr, 40000)
        count = len(backend.requests)
        self.assertTrue(ui.start_background('My budget is RM40000.', goal='buy', request_id='once'))
        self.assertIsNone(ui.active_turn)
        self.assertEqual(len(backend.requests), count)
        self.assertEqual(len(ui.history), 1)

    def test_busy_model_cannot_start_or_apply_a_turn(self):
        ui = existing_customer(ScriptedBackend())
        self.assertTrue(inference_lock().acquire(blocking=False))
        try:
            self.assertFalse(ui.start_background('My budget is RM1 million.', goal='buy'))
            self.assertIsNone(ui.active_turn)
            self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)
            self.assertFalse(ui.controller.backend.requests)
        finally:
            inference_lock().release()

    def test_new_request_runs_normally_after_cancellation(self):
        backend = BlockingPlanner()
        ui = existing_customer(backend)
        backend.owner = ui
        ui.start_background('My budget is RM1 million.', goal='buy')
        job = ui.active_turn
        self.assertTrue(backend.entered.wait(2))
        job.cancel()
        self.assertTrue(job.done.wait(2))
        ui.finish_background()
        ui.controller.backend = ScriptedBackend(sensed(updates=[update('buyer.budget_myr', 50000, 'RM50000')]),
                                              planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        ui.start_background('My budget is RM50000.', goal='buy')
        self.assertTrue(ui.active_turn.done.wait(2))
        self.assertEqual(ui.finish_background()['status'], 'complete')
        self.assertEqual(ui.controller.state.buyer.budget_myr, 50000)

    def test_menu_navigation_does_not_run_a_model_or_change_facts(self):
        ui = existing_customer(ScriptedBackend())
        app = AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=30)
        app.session_state['ui_session'] = ui
        app.run()
        for view in ('results', 'evidence', 'research'):
            app.button(key='nav_' + view).click().run()
            self.assertFalse(app.exception)
            self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)
            self.assertFalse(ui.controller.backend.requests)
            app.button(key='nav_consultation').click().run()
        self.assertEqual(len(app.chat_input), 1)

    def test_stop_button_cancels_a_running_turn_and_keeps_chat_usable(self):
        backend = BlockingPlanner()
        ui = existing_customer(backend)
        backend.owner = ui
        app = AppTest.from_file(str(ROOT/'streamlit_app.py'), default_timeout=30)
        app.session_state['ui_session'] = ui
        app.run()
        app.chat_input[0].set_value('My budget is RM1 million.').run()
        job = ui.active_turn
        self.assertIsNotNone(job)
        self.assertTrue(backend.entered.wait(2))
        self.assertFalse(app.button(key='cancel_calculation').disabled)
        app.button(key='cancel_calculation').click().run()
        self.assertTrue(job.done.wait(2))
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(ui.last_response['status'], 'cancelled')
        self.assertEqual(ui.controller.state.buyer.budget_myr, 60000)
        self.assertFalse(app.chat_input[0].disabled)
        self.assertTrue(app.button(key='cancel_calculation').disabled)


if __name__ == '__main__':
    unittest.main()
