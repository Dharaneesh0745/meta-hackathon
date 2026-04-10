import asyncio
import os
import sys

# Verify imports from the new isolated package
try:
    from agentic_os_env.env import MockAgencyEnv
    from agentic_os_env.graders import grade_easy
    print("[OK] SUCCESS: agentic_os_env package is importable.")
except ImportError as e:
    print(f"[FAIL] Import error: {e}")
    sys.exit(1)

async def test_env():
    print("Testing MockAgencyEnv initialization...")
    env = MockAgencyEnv()
    try:
        result = await env.reset(task_id="easy-ticket")
        print(f"[OK] SUCCESS: Environment reset. Task: {result.info.get('task_id')}")
        
        # Test the grader discovery
        print("Testing Grader bridge...")
        score = grade_easy()
        print(f"[OK] SUCCESS: Grader bridge returned: {score}")
        
    except Exception as e:
        print(f"[FAIL] Environment logic error: {e}")
    finally:
        await env.close()

if __name__ == "__main__":
    asyncio.run(test_env())
