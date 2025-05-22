import os
import sys
import subprocess
import time
import signal
import argparse

SERVER_SCRIPT = 'server.py'
PID_FILE = 'server.pid'
LLM_SERVER_SCRIPT = 'llm_server.py'
LLM_PID_FILE = 'llm_server.pid'


def start_server(port=5050):
    if os.path.exists(PID_FILE):
        print('Server is already running (pid file exists).')
        return
    cmd = [sys.executable, SERVER_SCRIPT]
    env = os.environ.copy()
    env['CONFLUENCE_API_PORT'] = str(port)
    with open('server.log', 'a') as out:
        proc = subprocess.Popen(cmd, env=env, stdout=out, stderr=out)
        with open(PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        print(f'Started server.py (PID {proc.pid}) on port {port}. Logs: server.log')

def stop_server():
    if not os.path.exists(PID_FILE):
        print('Server is not running (no pid file).')
        return
    with open(PID_FILE) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f'Stopped server.py (PID {pid}).')
    except Exception as e:
        print(f'Error stopping server: {e}')
    os.remove(PID_FILE)

def server_status():
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = f.read().strip()
        print(f'Server is running (PID {pid}).')
    else:
        print('Server is not running.')

def start_llm_server(port=5051):
    if os.path.exists(LLM_PID_FILE):
        print('LLM server is already running (pid file exists).')
        return
    cmd = [sys.executable, LLM_SERVER_SCRIPT]
    env = os.environ.copy()
    env['LLM_SERVER_PORT'] = str(port)
    with open('llm_server.log', 'a') as out:
        proc = subprocess.Popen(cmd, env=env, stdout=out, stderr=out)
        with open(LLM_PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        print(f'Started llm_server.py (PID {proc.pid}) on port {port}. Logs: llm_server.log')

def stop_llm_server():
    if not os.path.exists(LLM_PID_FILE):
        print('LLM server is not running (no pid file).')
        return
    with open(LLM_PID_FILE) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f'Stopped llm_server.py (PID {pid}).')
    except Exception as e:
        print(f'Error stopping LLM server: {e}')
    os.remove(LLM_PID_FILE)

def llm_server_status():
    if os.path.exists(LLM_PID_FILE):
        with open(LLM_PID_FILE) as f:
            pid = f.read().strip()
        print(f'LLM server is running (PID {pid}).')
    else:
        print('LLM server is not running.')

def main():
    parser = argparse.ArgumentParser(description='Manage the Flask API server and LLM server.')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'start-llm', 'stop-llm', 'status-llm'])
    parser.add_argument('--port', type=int, default=None, help='Port to run the server on (default: 5050 for API, 5051 for LLM)')
    args = parser.parse_args()
    if args.command == 'start':
        port = args.port or 5050
        start_server(port)
    elif args.command == 'stop':
        stop_server()
    elif args.command == 'status':
        server_status()
    elif args.command == 'start-llm':
        port = args.port or 5051
        start_llm_server(port)
    elif args.command == 'stop-llm':
        stop_llm_server()
    elif args.command == 'status-llm':
        llm_server_status()

if __name__ == '__main__':
    main() 