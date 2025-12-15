import os
import json
import uvicorn
import logging
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Hardcoded API Key
GOOGLE_API_KEY = "AIzaSyC_aqH9032IaWIcRhymnxhSvoT-Mn_u5rs"
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WriterAgent")

class WriterAgent:
    def __init__(self):
        self.name = "Writer Agent"
        self.system_prompt = """
        你是一位富有创意的作家和编辑。
        你的目标是撰写引人入胜、高质量的内容。
        你可以撰写博客文章、故事、邮件、报告等。
        注重语气、风格和清晰度。
        如果输入包含原始数据或大纲，请将其转化为精美的文字作品。
        请优先用中文进行创作。
        """
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)
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

agent = WriterAgent()
app = Starlette(debug=True, routes=[
    Route("/", agent.handle_request, methods=["POST"]),
])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10002)
