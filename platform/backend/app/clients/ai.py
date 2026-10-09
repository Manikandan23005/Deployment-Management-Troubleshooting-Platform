# --- Pluggable AI Engine Client ---
import httpx
from typing import Optional, Dict, Any
from app.core.settings import settings
from app.core.logging import logger
from shared.exceptions import AIModelTriageException

class AIClient:
    """Manages chat completions requests to OpenAI, Groq, Ollama, and LM Studio engines."""
    
    def generate_chat_response(
        self, 
        prompt: str, 
        system_prompt: str = "You are a DevOps Incident Analysis Assistant.",
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        provider_name = provider or settings.AI_PROVIDER or "ollama"
        provider_name = provider_name.lower()
        
        try:
            if provider_name == "openai":
                return self._call_openai_compatible(
                    url="https://api.openai.com/v1/chat/completions",
                    api_key=settings.OPENAI_API_KEY,
                    model=model or "gpt-4-turbo",
                    system_prompt=system_prompt,
                    prompt=prompt
                )
            elif provider_name == "groq":
                groq_model = model or getattr(settings, "LLM_MODEL", None) or "openai/gpt-oss-20b"
                # If legacy/unsupported model name was specified, fallback to fast gpt-oss-20b
                if "llama" in groq_model.lower():
                    groq_model = "openai/gpt-oss-20b"
                return self._call_openai_compatible(
                    url="https://api.groq.com/openai/v1/chat/completions",
                    api_key=settings.GROQ_API_KEY,
                    model=groq_model,
                    system_prompt=system_prompt,
                    prompt=prompt
                )
            elif provider_name == "lmstudio":
                host = settings.LMSTUDIO_HOST or "http://localhost:1234/v1"
                return self._call_openai_compatible(
                    url=f"{host}/chat/completions",
                    api_key="lm-studio-token",
                    model="local-model",
                    system_prompt=system_prompt,
                    prompt=prompt
                )
            else: # Fallback to local Ollama API
                host = settings.OLLAMA_HOST or "http://localhost:11434"
                return self._call_ollama(host, system_prompt, prompt)
        except Exception as e:
            logger.error(f"AI Client provider {provider_name} request failed: {str(e)}")
            raise AIModelTriageException(f"AI completions failed: {str(e)}")

    def stream_chat_response(
        self,
        prompt: str,
        system_prompt: str = "You are a DevOps Incident Analysis Assistant.",
        provider: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Streams chat completion tokens in real-time from Groq or OpenAI."""
        provider_name = (provider or settings.AI_PROVIDER or "groq").lower()
        if provider_name == "groq":
            groq_model = model or getattr(settings, "LLM_MODEL", None) or "openai/gpt-oss-20b"
            if "llama" in groq_model.lower():
                groq_model = "openai/gpt-oss-20b"
            yield from self._stream_openai_compatible(
                url="https://api.groq.com/openai/v1/chat/completions",
                api_key=settings.GROQ_API_KEY,
                model=groq_model,
                system_prompt=system_prompt,
                prompt=prompt
            )
        elif provider_name == "openai":
            yield from self._stream_openai_compatible(
                url="https://api.openai.com/v1/chat/completions",
                api_key=settings.OPENAI_API_KEY,
                model=model or "gpt-4-turbo",
                system_prompt=system_prompt,
                prompt=prompt
            )
        else:
            full_text = self.generate_chat_response(prompt, system_prompt=system_prompt, provider=provider, model=model)
            for chunk in full_text.split(" "):
                yield chunk + " "

    def _stream_openai_compatible(self, url: str, api_key: str, model: str, system_prompt: str, prompt: str):
        import json
        if not api_key:
            raise AIModelTriageException("API Key is missing for selected remote completions engine.")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": True,
            "temperature": 0.2
        }
        with httpx.Client(timeout=45.0) as client:
            with client.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code != 200:
                    raise AIModelTriageException(f"Stream API returned {response.status_code}")
                for line in response.iter_lines():
                    if line.startswith("data: ") and line.strip() != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            choices = chunk.get("choices")
                            if choices and len(choices) > 0:
                                delta = choices[0].get("delta", {}).get("content", "")
                                if delta:
                                    yield delta
                        except Exception:
                            continue

    def _call_openai_compatible(self, url: str, api_key: str, model: str, system_prompt: str, prompt: str) -> str:
        if not api_key:
            raise AIModelTriageException("API Key is missing for selected remote completions engine.")
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        with httpx.Client(timeout=45.0) as client:
            response = client.post(url, headers=headers, json=body)
            if response.status_code != 200:
                raise AIModelTriageException(f"API endpoint returned error {response.status_code}: {response.text}")
            return response.json()["choices"][0]["message"]["content"]

    def _call_ollama(self, host: str, system_prompt: str, prompt: str) -> str:
        url = f"{host}/api/chat"
        body = {
            "model": "llama3",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {"temperature": 0.2}
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=body)
            if response.status_code != 200:
                raise AIModelTriageException(f"Ollama local endpoint returned error {response.status_code}: {response.text}")
            return response.json()["message"]["content"]

ai_client = AIClient()
