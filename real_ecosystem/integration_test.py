import asyncio
import aiohttp
import json
import uuid
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

async def test_agent_interaction(agent_name, agent_port, task_desc, context=None):
    """
    Simulates the A2A protocol interaction used by YinQing executor.py
    """
    url = f"http://localhost:{agent_port}"
    print(f"\n--- Testing {agent_name} at {url} ---")
    
    if context is None:
        context = {}
        
    # Construct the payload exactly as executor.py does
    payload = {
        "task_description": task_desc,
        "context": context
    }
    query_str = json.dumps(payload)
    
    # Construct A2A Message structure (simplified for raw HTTP post)
    # The agents expect: body['params']['message']['parts'][0]['text']
    request_body = {
        "jsonrpc": "2.0",
        "method": "a2a/sendMessage",
        "id": str(uuid.uuid4()),
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "text": query_str
                    }
                ]
            }
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_body, timeout=30) as response:
                if response.status != 200:
                    print(f"❌ Failed: HTTP {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                
                data = await response.json()
                
                # Verify response structure (A2A)
                # Expected: result.message.parts[0].text
                try:
                    result = data.get("result", {})
                    message = result.get("message", {})
                    parts = message.get("parts", [])
                    if parts and "text" in parts[0]:
                        response_text = parts[0]["text"]
                        print(f"✅ Success: Received valid response")
                        print(f"Output Preview: {response_text[:100]}...")
                        return True
                    else:
                        print(f"❌ Failed: Invalid response structure: {data}")
                        return False
                except Exception as e:
                    print(f"❌ Failed: Error parsing response: {e}")
                    return False
                    
    except Exception as e:
        print(f"❌ Failed: Connection error: {e}")
        return False

async def main():
    print("🚀 Starting Integration Test for All Agents")
    
    # 1. Test Researcher
    await test_agent_interaction(
        "Researcher Agent", 10001, 
        "Research the history of Python", 
        {}
    )
    
    # 2. Test Writer (Dependent on research)
    await test_agent_interaction(
        "Writer Agent", 10002,
        "Write a short blog post based on the research",
        {"research_summary": "Python was created by Guido van Rossum..."}
    )
    
    # 3. Test Coder
    await test_agent_interaction(
        "Coder Agent", 10003,
        "Write a python hello world script",
        {}
    )
    
    # 4. Test Data Analyst
    await test_agent_interaction(
        "Data Analyst Agent", 10004,
        "Analyze this sales data: Q1=100, Q2=150",
        {}
    )
    
    # 5. Test Reviewer
    await test_agent_interaction(
        "Reviewer Agent", 10005,
        "Review this code: print('hello')",
        {}
    )
    
    # 6. Test Translator
    await test_agent_interaction(
        "Translator Agent", 10006,
        "Translate 'Hello World' to Spanish",
        {}
    )

if __name__ == "__main__":
    asyncio.run(main())
