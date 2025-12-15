from datetime import timedelta

RETRY_TIMES = 3
RETRY_DELAY = 1
AGENT_CACHE_TTL = timedelta(minutes=10)

def clean_response_str(s: str) -> str:
    if not s:
        return ""
    cleaned = s.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()
