"""Reproduce the complete analysis: python -m pipeline.run."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-ingest', action='store_true', help='Reuse the existing audited SQLite ledger.')
    args = parser.parse_args()
    steps = ([] if args.skip_ingest else ['pipeline.ingest']) + [
        'pipeline.analytics', 'pipeline.model', 'pipeline.currency', 'pipeline.build_dashboard_data']
    for step in steps:
        print(f'Running {step}', flush=True)
        subprocess.run([sys.executable, '-m', step], cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=ROOT, check=True)
    print('Analysis and source snapshot complete. Run npm run build to update the portable dashboard.')


if __name__ == '__main__':
    main()
