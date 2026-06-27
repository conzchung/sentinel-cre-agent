import os
from dotenv import load_dotenv, find_dotenv
from langchain_openai import AzureChatOpenAI

load_dotenv(find_dotenv(), override=True)

# Mapping for reasoning effort enum changes
REASONING_EFFORT_MAP = {
    "minimal": "none",
}


def init_llm(llm_args, temperature=1, max_tokens=16384):
    """Initialize LLM based on specified provider."""
    llm_args = llm_args.copy()
    
    # Let llm_args override defaults if present
    temperature = llm_args.pop("temperature", temperature)
    max_tokens = llm_args.pop("max_tokens", max_tokens)
    max_tokens = llm_args.pop("max_completion_tokens", max_tokens)
    
    # Force temperature = 1 for reasoning-style models
    if "reasoning_effort" in llm_args:
        original = llm_args["reasoning_effort"]
        llm_args["reasoning_effort"] = REASONING_EFFORT_MAP.get(
            original, original
        )

        temperature = 1
        max_tokens = 128000
        
    llm = AzureChatOpenAI(
        **llm_args,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    )
        
    return llm


AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
API_KEY = os.getenv("OPENAI_API_KEY")


GPT54m_args = dict(
    azure_endpoint = AZURE_ENDPOINT,
    openai_api_version = "2025-04-01-preview",
    deployment_name = os.getenv("DEPLOYMENT_NAME_GPT54M"),
    openai_api_key = API_KEY,
    reasoning_effort='low'
)

GPT54_args = dict(
    azure_endpoint = AZURE_ENDPOINT,
    openai_api_version = "2025-04-01-preview",
    deployment_name = os.getenv("DEPLOYMENT_NAME_GPT54"),
    openai_api_key = API_KEY,
    reasoning_effort='low'
)