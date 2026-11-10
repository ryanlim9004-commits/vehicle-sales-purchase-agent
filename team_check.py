"""Read-only installation checks; optional reports are written only on request.

Run with the project Python: python team_check.py [--ollama] [--output PATH].
This checks service/model metadata, not model inference or market accuracy.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
import platform
import struct
import subprocess
import sys
import tomllib
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent
MODEL = 'qwen3:4b'
TESTED_MODEL_ID = '359d7dd4bcda'


def now_malaysia():
    return datetime.now(timezone(timedelta(hours=8)))


def default_report_path(kind):
    # Local results are ignored by Git; each explicit run gets a separate file.
    stamp = now_malaysia().strftime('%Y%m%d-%H%M%S-%f')
    return ROOT/'team_results'/f'{kind}-{stamp}.json'


def save_new_report(path, report):
    # Do not overwrite a previous test, consultation export or source artifact.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def locked_packages(path):
    # The committed lock uses simple exact pins, one distribution per line.
    packages = {}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('==')
        if len(parts) != 2 or not all(parts):
            raise ValueError('Expected an exact package pin in requirements-lock.txt.')
        packages[parts[0]] = parts[1]
    return packages


def package_findings(pins):
    findings = []
    for name, expected in pins.items():
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != expected:
            findings.append({'package': name, 'expected': expected, 'installed': installed})
    return findings


def repository_identity(root=ROOT):
    # ZIP downloads have no Git metadata. Hash code/data as a separate identity
    # rather than mistaking an enclosing unrelated repository for this project.
    names = {p.name for p in root.glob('*.py')}
    names.update(('requirements-lock.txt', '.streamlit/config.toml',
                  'data/vehicles_real.json', 'data/vehicles_simulation.json', 'data/historical_simulation_source.json',
                  'data/model_evidence_v2.json', 'data/regression_manifest.json',
                  'data/historical_price_model.json'))
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
              for name in sorted(names) if (root/name).is_file()}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    revision = dirty = None
    try:
        args = dict(cwd=root, capture_output=True, text=True, timeout=5, check=True)
        top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], **args).stdout.strip()
        if Path(top).resolve() == root.resolve():
            revision = subprocess.run(['git', 'rev-parse', 'HEAD'], **args).stdout.strip()
            dirty = bool(subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], **args).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return {'git_commit': revision, 'tracked_changes': dirty,
            'code_and_data_sha256': digest, 'file_sha256': hashes}


def ollama_metadata():
    # Contact only this machine. Do not route loopback checks through a proxy,
    # perform inference, download a model or inspect unrelated local models.
    opener = build_opener(ProxyHandler({}))
    def read(endpoint):
        with opener.open('http://127.0.0.1:11434/api/' + endpoint, timeout=4) as response:
            return json.load(response)
    version, tags = read('version'), read('tags')
    model = next((m for m in tags.get('models', []) if m.get('name', m.get('model', '')).lower() == MODEL.lower()), None)
    return {'server_version': version.get('version'), 'required_model': MODEL,
            'model_present': model is not None, 'model_digest': model.get('digest') if model else None}


def collect_environment(*, check_ollama=False):
    report = {'checked_at': now_malaysia().isoformat(), 'scope': 'Installation and saved-data check, not inference or independent assessment.',
              'python_version': platform.python_version(), 'platform': platform.system(),
              'architecture': platform.machine(), 'checks': [], 'source': repository_identity()}
    def check(name, passed, detail, *, warning=False):
        report['checks'].append({'name': name, 'status': 'pass' if passed else 'warning' if warning else 'fail', 'detail': detail})
    check('python_3_13', sys.version_info[:2] == (3, 13), 'Use regular CPython 3.13; actual: ' + platform.python_version())
    check('64_bit_python', struct.calcsize('P') == 8, 'The handoff installation was verified on Windows x64.')
    if platform.system() != 'Windows':
        check('tested_platform', False, 'Only Windows x64 clean installation has been checked locally; record other-platform results separately.', warning=True)
    try:
        mismatches = package_findings(locked_packages(ROOT/'requirements-lock.txt'))
        report['package_mismatches'] = mismatches
        check('locked_packages', not mismatches, 'Exact package versions match the lock.' if not mismatches else 'Install requirements-lock.txt using this same Python; see package_mismatches.')
    except (OSError, ValueError) as error:
        mismatches = [str(error)]
        check('locked_packages', False, 'Could not read the committed lock: ' + str(error))
    imports_ok = True
    for name in ('pydantic', 'ollama', 'streamlit', 'numpy'):
        try:
            importlib.import_module(name)
        except Exception as error:
            imports_ok = False
            check('import_' + name, False, type(error).__name__ + ': ' + str(error)[:200])
    check('dependency_imports', imports_ok, 'Import checks do not call Ollama or start Streamlit.')
    if imports_ok:
        try:
            from vehicle_frame import load_vehicles, load_agent_vehicles
            from vehicle_evidence import load_catalogue
            from price_regression import PriceDataset, gate
            cars, catalogue = load_vehicles(ROOT/'data/vehicles_real.json'), load_catalogue()
            manifest = PriceDataset.model_validate_json((ROOT/'data/regression_manifest.json').read_bytes())
            report['saved_data'] = {'price_rows': len(cars), 'research_profiles': len(catalogue.profiles),
                                    'simulation_rows': sum(v.simulation is not None for v in load_agent_vehicles()),
                                    'agent_total_rows': len(load_agent_vehicles()),
                                    'snapshot_date': '2026-10-15', 'research_reviewed_on': catalogue.reviewed_on.isoformat(),
                                    'regression_data_issues': gate(manifest), 'regression_active_in_agent': False}
            check('data_schema', True, 'Saved sources validate. Insufficient regression evidence is a documented feature limit, not an installation failure.')
        except Exception as error:
            check('data_schema', False, type(error).__name__ + ': ' + str(error)[:200])
    try:
        config = tomllib.loads((ROOT/'.streamlit/config.toml').read_text(encoding='utf-8-sig'))
        check('local_ui_address', config.get('server', {}).get('address') == '127.0.0.1', 'Streamlit should bind to 127.0.0.1.')
    except (OSError, ValueError) as error:
        check('local_ui_address', False, str(error)[:200])
    if check_ollama:
        try:
            report['ollama'] = ollama_metadata()
            found = report['ollama']['model_present']
            check('ollama_service_and_model', found, 'Required local model: ' + MODEL + ('. Available.' if found else '. Run: ollama pull ' + MODEL))
            digest = report['ollama']['model_digest'] or ''
            if found and not digest.removeprefix('sha256:').startswith(TESTED_MODEL_ID):
                check('tested_model_digest', False, 'Model tag differs from the recorded model ID; keep the actual digest in your evidence.', warning=True)
        except (OSError, URLError, ValueError, TypeError, KeyError) as error:
            check('ollama_service_and_model', False, 'Open the Ollama application, or run ollama serve if no service exists. ' + type(error).__name__)
    report['status'] = 'failed' if any(c['status'] == 'fail' for c in report['checks']) else 'passed_with_warnings' if any(c['status'] == 'warning' for c in report['checks']) else 'passed'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ollama', action='store_true', help='Also check local service/model metadata; no inference')
    parser.add_argument('--output', type=Path, help='Write a new local JSON report; existing files are never overwritten')
    args = parser.parse_args()
    report = collect_environment(check_ollama=args.ollama)
    for item in report['checks']:
        print(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")
    if report.get('package_mismatches'):
        print(json.dumps(report['package_mismatches'], indent=2))
    if not args.ollama:
        print('[INFO] Ollama was not checked. Add --ollama for the local service/model check.')
    if args.output:
        try:
            save_new_report(args.output, report)
        except (OSError, ValueError) as error:
            parser.error('Report not saved: ' + str(error))
        print('Report: ' + str(args.output))
    print('Setup result: ' + report['status'])
    return 1 if report['status'] == 'failed' else 0


if __name__ == '__main__':
    raise SystemExit(main())
