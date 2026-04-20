import os
import yaml
import httpx
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.settings import ModelSettings
from pydantic_ai.profiles.openai import OpenAIModelProfile
from dotenv import load_dotenv

# Ensure environment variables are loaded from .env
load_dotenv()

def get_model():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "gemini")
    model_name = llm_config.get("model", "gemini-2.5-flash")
    
    # Get timeout from config, default to 5 minutes
    timeout_mins = llm_config.get("sync_timeout_minutes", 5)
    timeout_seconds = timeout_mins * 60.0
    
    # Generate model settings
    settings = ModelSettings(timeout=timeout_seconds, temperature=0.1)
    
    if provider == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            print("⚠️ Warning: GEMINI_API_KEY not found in environment.")
        return GeminiModel(model_name)
    
    elif provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️ Warning: OPENAI_API_KEY not found in environment.")
        return OpenAIModel(model_name)
    
    elif provider == "ollama":
        print(f"🦙 Using local Ollama model: {model_name} (JSON Mode, {timeout_mins}m timeout)")
        
        profile = OpenAIModelProfile(
            supports_tools=False,
            supports_json_object_output=True,
            default_structured_output_mode='prompted'
        )
        
        return OpenAIModel(
            model_name,
            provider='ollama',
            profile=profile,
            settings=settings
        )
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
