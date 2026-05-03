import sys
import os
import json
import asyncio
import _thread
import threading
import time
import urllib.request
import gc

# Force UTF-8 for Windows terminals
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

# 1. Mock CPython gc to have MicroPython's mem_free
if not hasattr(gc, 'mem_free'):
    gc.mem_free = lambda: 520 * 1024  # Simulate 520KB free

# 2. Create Mock Modules for MicroPython specifics
class MockMachine:
    def freq(self, hz=None):
        return 150000000
    def reset(self):
        print("EMULATOR: machine.reset() called. Exiting instead.")
        sys.exit(0)
    class WDT:
        def __init__(self, timeout=0): pass
        def feed(self): pass
    class ADC:
        def __init__(self, pin): pass
        def read_u16(self): return 20000

sys.modules['machine'] = MockMachine()
sys.modules['ujson'] = json
sys.modules['uasyncio'] = asyncio
sys.modules['uos'] = os
sys.modules['uos'].rename = os.replace  # Windows needs os.replace to overwrite files
sys.modules['ntptime'] = type('MockNTP', (), {'settime': lambda: None})()

import base64
class MockUbinascii:
    @staticmethod
    def b2a_base64(data):
        return base64.b64encode(data)
sys.modules['ubinascii'] = MockUbinascii()

class MockUrequestsResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
    def json(self):
        return json.loads(self.text)
    def close(self):
        pass

class MockUrequests:
    def get(self, url, headers=None, timeout=None):
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return MockUrequestsResponse(response.status, response.read().decode('utf-8'))
        except Exception as e:
            return MockUrequestsResponse(500, str(e))
            
    def post(self, url, data=None, json_data=None, json=None, headers=None, timeout=None):
        return self._make_request("POST", url, data, json_data, json, headers, timeout)

    def put(self, url, data=None, json_data=None, json=None, headers=None, timeout=None):
        return self._make_request("PUT", url, data, json_data, json, headers, timeout)

    def _make_request(self, method, url, data=None, json_data=None, json=None, headers=None, timeout=None):
        headers = headers or {}
        body = None
        j_data = json_data if json_data else json
        if j_data is not None:
            body = sys.modules['ujson'].dumps(j_data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif data:
            body = data.encode('utf-8') if isinstance(data, str) else data
            
        print(f"[EMU] Making {method} request to {url}")
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                print(f"[EMU] {method} request finished with status {response.status}")
                return MockUrequestsResponse(response.status, response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print(f"[EMU] {method} request HTTPError: {e.code}")
            return MockUrequestsResponse(e.code, e.read().decode('utf-8'))
        except Exception as e:
            print(f"[EMU] {method} request Exception: {e}")
            return MockUrequestsResponse(500, str(e))

sys.modules['urequests'] = MockUrequests()
sys.modules['micropython'] = type('MockMicropython', (), {'const': lambda x: x})()
sys.modules['network'] = type('MockNetwork', (), {'WLAN': lambda x: type('WLAN', (), {'isconnected': lambda self: True, 'ifconfig': lambda self: ('127.0.0.1',)})()})()
_thread.stack_size = lambda x: None

# Use RLock for emulator to prevent self-deadlocks during complex nested calls
import locks
locks.state_lock = threading.RLock()

# 3. Import Picoling core after mocks are injected
import agent_core
import memory
import telegram_bot
from horizon import start_background_worker
from poller import COMMANDS, _handle_auto, _handle_ghost, _handle_reboot

# 4. Intercept Telegram output so it prints to our console instead of sending to the API!
def mock_send(text, max_len=2000):
    print(f"\n[PICOLING]: {text}\n[YOU]: ", end="", flush=True)

telegram_bot.send_telegram_msg = mock_send

# 5. Build Emulator Event Loop
async def emulator_loop():
    print("=" * 50)
    print("=== Picoling PC Emulator Started ===")
    print("Type your message and press Enter. Type '/quit' to exit.")
    print("=" * 50)
    
    memory.init_memory()
    start_background_worker() # Enabled for background testing
    
    # Run input in a separate thread to avoid blocking asyncio
    def input_thread(loop):
        while True:
            text = input("[YOU]: ")
            if not text:
                continue
            if text == "/quit":
                os._exit(0)
            
            # Handle commands locally
            if text.startswith("."):
                parts = text.split(" ", 1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""
                
                if cmd == ".auto":
                    print(_handle_auto(args))
                elif cmd == ".ghost":
                    print(_handle_ghost(args))
                elif cmd == ".reboot":
                    _handle_reboot()
                elif cmd in COMMANDS:
                    print(COMMANDS[cmd](args))
                else:
                    print(f"Unknown command: {cmd}")
                print("[YOU]: ", end="", flush=True)
                continue
                
            # Process normal messages via agent_core
            print(f"[EMU] Submitting message: {text}")
            fut = asyncio.run_coroutine_threadsafe(agent_core.process_user_message(text), loop)
            def done_cb(f):
                if f.exception():
                    print(f"\n[EMU] Error in process_user_message: {f.exception()}")
            fut.add_done_callback(done_cb)
            print("[EMU] Message submitted.")
            
    loop = asyncio.get_running_loop()
    threading_thread = __import__('threading').Thread(target=input_thread, args=(loop,), daemon=True)
    threading_thread.start()
    
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    # Ensure directories exist
    for d in ["skills", "data"]:
        os.makedirs(d, exist_ok=True)
        
    try:
        asyncio.run(emulator_loop())
    except KeyboardInterrupt:
        print("\nEmulator stopped.")
