import requests
import json
import time

BASE_URL = "https://dharaneesh74-jira-to-pr.hf.space"

def test_server():
    print(f"Testing live server at: {BASE_URL}")
    
    # 1. Health Check
    try:
        health = requests.get(f"{BASE_URL}/health")
        print(f"Health: {health.status_code} - {health.json()}")
    except Exception as e:
        print(f"Health Failed: {e}")
        return

    # 2. Reset (Stateless HTTP)
    print("\nTesting /reset (easy-ticket)...")
    try:
        reset = requests.post(f"{BASE_URL}/reset", json={"task_id": "easy-ticket"})
        if reset.status_code == 200:
            data = reset.json()
            print(f"Reset Success!")
            print(f"   Observation: {data['observation']['terminal_output'][:100]}...")
        else:
            print(f"Reset Failed: {reset.status_code} - {reset.text}")
    except Exception as e:
        print(f"Reset Error: {e}")

    # 3. State Check
    print("\nChecking /state...")
    try:
        state = requests.get(f"{BASE_URL}/state")
        if state.status_code == 200:
            data = state.json()
            print(f"State retrieved!")
            print(f"   Episode ID: {data['episode_id']}")
            print(f"   Current Task: {data['current_task']}")
            print(f"   Step Count: {data['step_count']}")
        else:
            print(f"State Failed: {state.status_code}")
    except Exception as e:
        print(f"State Error: {e}")

if __name__ == "__main__":
    test_server()
