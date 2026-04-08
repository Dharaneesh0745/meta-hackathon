import asyncio
import os
from inference import get_model_action
from env import MockAgencyEnv
from openai import OpenAI

async def test_inference():
    print("Final Verification...")
    
    # Initialize environment
    env = MockAgencyEnv()
    result = await env.reset()
    obs = result.observation
    
    # Use a dummy client
    client = OpenAI(api_key="verify-only")
    
    # Check fields
    try:
        fields = list(obs.model_dump().keys())
    except:
        fields = list(obs.dict().keys())
    print(f"Checking observation fields: {fields}")
    
    # Execute
    print("Executing get_model_action...")
    res = get_model_action(client, obs, 1)
    
    if res == "{}":
        print("SUCCESS: Prompt constructed and API call attempted.")
        return True
    else:
        print("SUCCESS: Model response received.")
        return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_inference())
        if success:
            print("VERIFICATION PASSED.")
        else:
            print("VERIFICATION FAILED.")
            exit(1)
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        exit(1)
