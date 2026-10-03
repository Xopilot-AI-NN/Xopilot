"""Run the same Xopilot UI in a loopback-only browser session."""
import argparse
import os
import runpy
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, default=8559)
parser.add_argument('--test-profile', action='store_true', help='Use a separate persistent QA profile')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
if args.test_profile:
    import tempfile
    os.environ['XDG_DATA_HOME'] = str(Path(tempfile.gettempdir()) / 'xopilot-user-qa')
    if sys.platform == 'win32':
        os.environ['APPDATA'] = os.environ['XDG_DATA_HOME']
os.environ['XOPILOT_LOCAL_WEB'] = '1'
os.environ['FLET_FORCE_WEB_SERVER'] = '1'
os.environ['FLET_SERVER_IP'] = '127.0.0.1'
os.environ['FLET_SERVER_PORT'] = str(args.port)
sys.path.insert(0, str(root / 'App'))
runpy.run_path(str(root / 'App' / 'App.py'), run_name='__main__')
