import os
import json
import uvicorn
import logging
from pathlib import Path
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)

# Qwen3-max API Configuration from environment
QWEN_API_KEY = os.getenv("OPENAI_API_KEY", "sk-79bd9f13361049a4b5c91fc992a6e41a")
QWEN_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("OPENAI_MODEL", "qwen3-max")

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ResearcherAgent")

class ResearcherAgent:
    def __init__(self):
        self.name = "Researcher Agent"
        self.system_prompt = """
        你是一位专业的研究助手。
        你的目标是根据用户查询提供全面、准确且结构清晰的信息。
        当被问及某个主题时，请分解主题、解释关键概念并提供相关细节。
        由于你在当前环境中无法实时访问互联网，请依赖你的内部知识库（截止日期 2024/2025）。
        请用中文回答所有问题。
        """
        self.llm = ChatOpenAI(model=QWEN_MODEL, temperature=0.3, base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{input}")
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    async def handle_request(self, request):
        try:
            body = await request.json()
            logger.info(f"[{self.name}] Received request")
            
            # Extract user message
            user_msg = ""
            if 'params' in body and 'message' in body['params']:
                parts = body['params']['message'].get('parts', [])
                if parts:
                    user_msg = parts[0].get('text', '')
            
            if not user_msg:
                return JSONResponse({"error": "Empty message"}, status_code=400)

            # Try to parse user_msg as JSON (A2A protocol payload)
            try:
                payload = json.loads(user_msg)
                if isinstance(payload, dict) and "task_description" in payload:
                    task_desc = payload.get("task_description", "")
                    context = payload.get("context", {})
                    
                    # Reconstruct a better prompt for the LLM
                    formatted_input = f"Task: {task_desc}\n\nContext:\n{json.dumps(context, indent=2)}"
                    user_msg = formatted_input
                    logger.info(f"[{self.name}] Parsed A2A JSON payload. Task: {task_desc[:50]}...")
            except json.JSONDecodeError:
                # Not a JSON payload, treat as raw text
                pass
            except Exception as e:
                logger.warning(f"[{self.name}] Error parsing payload: {e}")

            logger.info(f"[{self.name}] Processing: {user_msg[:50]}...")
            
            # Call LLM
            response_text = await self.chain.ainvoke({"input": user_msg})
            
            logger.info(f"[{self.name}] Response generated ({len(response_text)} chars)")

            # Construct A2A response
            response_data = {
                "result": {
                    "message": {
                        "role": "model",
                        "parts": [
                            {
                                "text": response_text
                            }
                        ]
                    }
                }
            }
            return JSONResponse(response_data)
            
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)

agent = ResearcherAgent()

async def health_check(request):
    return JSONResponse({"status": "healthy", "agent": agent.name, "model": "qwen3-max"})

app = Starlette(debug=True, routes=[
    Route("/", agent.handle_request, methods=["POST"]),
    Route("/health", health_check, methods=["GET"]),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10001)
