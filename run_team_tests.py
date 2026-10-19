"""Run all offline test modules and save a new local result, without Ollama.

These engineering tests do not replace independently authored user scenarios.
"""
import argparse
import os
from pathlib import Path
import time
import unittest
from team_check import ROOT, now_malaysia, repository_identity, default_report_path, save_new_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tester', default=None, help='Optional actual tester label, never inferred as teammate evidence')
    parser.add_argument('--output', type=Path, help='New JSON file; defaults to a timestamped path under team_results/')
    args = parser.parse_args()
    destination = args.output or default_report_path('offline')
    if destination.exists():
        parser.error('Output already exists. Choose a new name to preserve prior evidence.')
    # Several existing fixtures use relative paths. Set this process directory
    # explicitly so launching from another folder still tests the same project.
    os.chdir(ROOT)
    source = repository_identity()
    suite = unittest.defaultTestLoader.discover(str(ROOT), pattern='test_*.py', top_level_dir=str(ROOT))
    start = time.monotonic()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {'ran_at': now_malaysia().isoformat(), 'tester': args.tester,
              'scope': 'Offline engineering regression; model replies scripted; no independent relevance or market-accuracy claim.',
              'source': source, 'tests_run': result.testsRun, 'passed': result.wasSuccessful(),
              'elapsed_seconds': round(time.monotonic()-start, 3),
              'failures': [{'test': str(test), 'detail': detail} for test, detail in result.failures],
              'errors': [{'test': str(test), 'detail': detail} for test, detail in result.errors],
              'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped]}
    try:
        save_new_report(destination, report)
    except (OSError, ValueError) as error:
        parser.error('Report not saved: ' + str(error))
    print('Offline report: ' + str(destination), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
