import requests
import asyncio
import websockets
import json

BASE_URL = "https://dharaneesh74-jira-to-pr.hf.space"
WS_URL = "wss://dharaneesh74-jira-to-pr.hf.space/ws"

async def audit_websocket():
    print("\n--- 1. WebSocket Audit ---")
    try:
        async with websockets.connect(WS_URL) as ws:
            print("Connected to WebSocket.")
            # 1. Reset via WS
            await ws.send(json.dumps({"type": "reset", "task_id": "easy-ticket"}))
            print("Reset command sent via WS.")
            resp_raw = await ws.recv()
            resp = json.loads(resp_raw)
            print(f"WS Response Type: {resp.get('type')}")
            if resp.get('type') == 'reset':
                print("✅ WebSocket Reset Successful!")
                return True
            else:
                print(f"❌ WebSocket Reset Error: {resp.get('message')}")
                return False
    except Exception as e:
        print(f"WS Audit Failed: {e}")
        return False

def audit_http():
    print("\n--- 2. HTTP Endpoints Audit ---")
    
    # 2.1 /step
    print("Testing /step (stateless)...")
    try:
        # We need a ticket active to test step. Let's try reset first
        requests.post(f"{BASE_URL}/reset", json={"task_id": "easy-ticket"})
        step_resp = requests.post(f"{BASE_URL}/step", json={"action": {"read_ticket": {"ticket_id": "easy-ticket"}}})
        print(f"Step Response: {step_resp.status_code}")
    except Exception as e:
         print(f"Step Failed: {e}")

    # 2.2 /docs
    print("Testing /docs...")
    try:
        docs = requests.get(f"{BASE_URL}/docs")
        print(f"Docs status: {docs.status_code} (Expect 200)")
    except Exception as e:
        print(f"Docs Failed: {e}")

    # 2.3 /web (or /)
    print("Testing /web (UI)...")
    try:
        web = requests.get(f"{BASE_URL}/")
        print(f"UI status: {web.status_code} (Expect 200)")
    except Exception as e:
        print(f"UI Failed: {e}")

async def main():
    print("Starting 100% Certainty Audit...")
    audit_http()
    await audit_websocket()

if __name__ == "__main__":
    asyncio.run(main())
