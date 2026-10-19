"""Handoff boundaries: no false passes, overwritten evidence or hidden inference."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from importlib.metadata import PackageNotFoundError
from team_check import collect_environment, locked_packages, package_findings, repository_identity, save_new_report, ROOT
import evaluate_v2_live
import run_team_tests
from test_agent import ScriptedBackend, sensed, planned, update, AgentController, AS_OF


class TeamToolsTests(unittest.TestCase):
    def test_missing_and_wrong_packages_are_not_success(self):
        def version(name):
            if name == 'missing':
                raise PackageNotFoundError(name)
            return 'wrong'
        with patch('team_check.importlib.metadata.version', side_effect=version):
            result = package_findings({'missing': '1', 'changed': '2'})
        self.assertEqual(result[0]['installed'], None)
        self.assertEqual(len(result), 2)

    def test_lock_parser_rejects_non_exact_requirement(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'requirements.txt'
            path.write_text('numpy>=2\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                locked_packages(path)

    def test_reports_never_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'run.json'
            save_new_report(path, {'original': True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                save_new_report(path, {'original': False})
            self.assertEqual(path.read_bytes(), before)

    def test_offline_check_never_calls_service_and_regression_gap_is_expected(self):
        with patch('team_check.ollama_metadata', side_effect=AssertionError('No network allowed')):
            report = collect_environment()
        self.assertEqual(report['status'], 'passed')
        self.assertTrue(report['saved_data']['regression_data_issues'])
        self.assertFalse(report['saved_data']['regression_active_in_agent'])

    def test_missing_model_and_unreachable_service_fail_setup(self):
        for observation in ({'server_version': 'test', 'model_present': False, 'model_digest': None}, OSError('offline')):
            with self.subTest(observation=type(observation).__name__):
                kwargs = {'side_effect': observation} if isinstance(observation, Exception) else {'return_value': observation}
                with patch('team_check.ollama_metadata', **kwargs):
                    report = collect_environment(check_ollama=True)
                self.assertEqual(report['status'], 'failed')

    def test_changed_model_is_warning_and_digest_is_preserved(self):
        with patch('team_check.ollama_metadata', return_value={'server_version': 'test', 'model_present': True, 'model_digest': 'changed-model'}):
            report = collect_environment(check_ollama=True)
        self.assertEqual(report['status'], 'passed_with_warnings')
        self.assertEqual(report['ollama']['model_digest'], 'changed-model')

    def test_corrupted_research_is_a_real_failure(self):
        with patch('vehicle_evidence.load_catalogue', side_effect=ValueError('bad source scope')):
            report = collect_environment()
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(any(c['name'] == 'data_schema' and c['status'] == 'fail' for c in report['checks']))

    def test_zip_inside_other_repository_does_not_inherit_its_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'zip'
            root.mkdir()
            (root/'main.py').write_text('x = 1\n', encoding='utf-8')
            with patch('team_check.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout=folder)):
                report = repository_identity(root)
            self.assertIsNone(report['git_commit'])
            self.assertIn('main.py', report['file_sha256'])

    def test_failing_offline_suite_produces_failed_report_and_exit(self):
        def failure():
            raise AssertionError('Synthetic test runner failure, not a product failure')
        suite = unittest.TestSuite([unittest.FunctionTestCase(failure)])
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'offline.json'
            with patch.object(sys, 'argv', ['run_team_tests.py', '--output', str(output)]), patch('run_team_tests.unittest.defaultTestLoader.discover', return_value=suite), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                exit_code = run_team_tests.main()
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(exit_code, 1)
            self.assertFalse(report['passed'])
            self.assertEqual(len(report['failures']), 1)

    def test_live_runner_refuses_existing_output_before_any_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'existing.json'
            output.write_text('preserved', encoding='utf-8')
            with patch.object(sys, 'argv', ['evaluate_v2_live.py', '--output', str(output)]), patch('evaluate_v2_live.AgentController') as controller, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    evaluate_v2_live.main()
                controller.assert_not_called()
            self.assertEqual(output.read_text(encoding='utf-8'), 'preserved')

    def test_live_cli_output_keeps_historical_file_and_reports_actual_tools(self):
        first = [update('buyer.budget_myr', 60000, 'My vehicle-price budget is RM60000'),
                 update('buyer.required_seats', 5, 'I need 5 seats'),
                 update('buyer.usage', ['city_commute'], 'city commuting'),
                 update('buyer.safety_priority', 'high', 'Safety priority is high'),
                 update('buyer.comfort_priority', 'medium', 'Comfort priority is medium'),
                 update('buyer.reliability_priority', 'high', 'Reliability priority is high'),
                 update('buyer.fuel_priority', 'high', 'Fuel priority is high')]
        second = [update('buyer.budget_myr', 55000, 'vehicle-price budget to RM55000'),
                  update('buyer.space_priority', 'high', 'Luggage-space priority is high'),
                  update('buyer.excluded_brands', ['Toyota'], 'Exclude Toyota')]
        backend = ScriptedBackend(sensed('buy', 'buy a car', first), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'),
                                  sensed(updates=second), planned('inspect_requirements', 'rank_vehicles', 'check_result', 'finish'))
        agent = AgentController(backend=backend, as_of=AS_OF)
        before = (ROOT/'v2-live-results.json').read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)/'new.json'
            with patch.object(sys, 'argv', ['evaluate_v2_live.py', '--output', str(output), '--tester', 'synthetic-engineering-test']), patch('evaluate_v2_live.AgentController', return_value=agent), redirect_stdout(io.StringIO()):
                code = evaluate_v2_live.main()
            report = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(code, 0)
            self.assertEqual(report['completed_turns'], 2)
            self.assertTrue(report['passed'])
            self.assertTrue(all(t['response']['checks'] for t in report['turns']))
        self.assertEqual((ROOT/'v2-live-results.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
