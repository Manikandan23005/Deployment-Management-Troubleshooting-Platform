# --- Pluggable AI completions client ---
from typing import Optional
from openai import OpenAI
from app.core.settings import settings
from app.core.logging import logger
from shared.exceptions import DevOpsNexusException

class LLMClient:
    """Manages chat completions utilizing the OpenAI client SDK for pluggable backends."""
    
    def generate_chat_response(
        self,
        prompt: str,
        system_prompt: str = "You are a DevOps Assistant.",
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        selected_provider = (provider or settings.AI_PROVIDER or "groq").lower()
        if "groq" in selected_provider:
            resolved_provider = "groq"
        elif "openai" in selected_provider or "gpt" in selected_provider:
            resolved_provider = "openai"
        elif "ollama" in selected_provider:
            resolved_provider = "ollama"
        elif "lmstudio" in selected_provider:
            resolved_provider = "lmstudio"
        else:
            resolved_provider = selected_provider

        # Resolve target configurations
        if resolved_provider == "groq":
            api_key = settings.GROQ_API_KEY
            base_url = "https://api.groq.com/openai/v1"
            selected_model = model or settings.LLM_MODEL or "llama-3.3-70b-versatile"
            if not api_key:
                raise DevOpsNexusException("GROQ_API_KEY is not configured. Please configure it in your .env file.")
        elif resolved_provider == "openai":
            api_key = settings.OPENAI_API_KEY
            base_url = settings.OPENAI_BASE_URL or "https://api.openai.com/v1"
            selected_model = model or settings.LLM_MODEL or "gpt-4o-mini"
            if not api_key:
                raise DevOpsNexusException("OPENAI_API_KEY is not configured. Please configure it in your .env file.")
        elif resolved_provider == "ollama":
            api_key = "ollama"
            base_url = f"{settings.OLLAMA_HOST or 'http://localhost:11434'}/v1"
            selected_model = model or settings.LLM_MODEL or "llama3"
        elif resolved_provider == "lmstudio":
            api_key = "lmstudio"
            base_url = settings.LMSTUDIO_HOST or "http://localhost:1234/v1"
            selected_model = model or settings.LLM_MODEL or "local-model"
        else:
            raise DevOpsNexusException(f"Unsupported AI provider: {resolved_provider}")

        try:
            client = OpenAI(base_url=base_url, api_key=api_key, timeout=15.0)
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"AI completions failed for provider {resolved_provider}: {str(e)}")
            raise DevOpsNexusException(f"AI integration request failed: {str(e)}")

llm_client = LLMClient()
