import os
import sys

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
from litellm import Router

load_dotenv()

# Model constants
PRIMARY_MODEL: str = "groq/openai/gpt-oss-20b"
FALLBACK_MODEL: str = "gemini/gemini-2.5-flash"
BACKUP_MODEL: str = "cerebras/llama-3.3-70b"

# Deployment model list
MODEL_LIST = [
    {
        "model_name": PRIMARY_MODEL,
        "litellm_params": {
            "model": PRIMARY_MODEL,
            "api_key": os.getenv("GROQ_API_KEY"),
        },
    },
    {
        "model_name": FALLBACK_MODEL,
        "litellm_params": {
            "model": FALLBACK_MODEL,
            "api_key": os.getenv("GEMINI_API_KEY"),
        },
    },
    {
        "model_name": BACKUP_MODEL,
        "litellm_params": {
            "model": BACKUP_MODEL,
            "api_key": os.getenv("CEREBRAS_API_KEY"),
        },
    },
]

# Fallbacks configuration
FALLBACKS = [
    {
        PRIMARY_MODEL: [FALLBACK_MODEL, BACKUP_MODEL]
    }
]

# Initialize Router
llm: Router = Router(
    model_list=MODEL_LIST,
    fallbacks=FALLBACKS,
    num_retries=3,
    cooldown_time=60,
    allowed_fails=1,
)


def call_llm(prompt: str) -> str:
    """Wrapper that calls llm.completion() and returns the text content, handling errors."""
    try:
        response = llm.completion(
            model=PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print(f"[Warning] call_llm failed: {e}")
        raise e


def test_connection(prompt: str = "say hello") -> str:
    """Sends prompt and prints response + which model answered."""
    response = llm.completion(
        model=PRIMARY_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content or ""
    model_used = getattr(response, "model", "unknown")

    try:
        print(f"Response: {content}")
        print(f"Answered by model: {model_used}")
    except UnicodeEncodeError:
        print(f"Response: {content.encode('ascii', errors='replace').decode('ascii')}")
        print(f"Answered by model: {model_used}")

    return content


if __name__ == "__main__":
    test_connection()