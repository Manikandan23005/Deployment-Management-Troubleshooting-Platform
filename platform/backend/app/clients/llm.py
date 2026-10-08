# --- Dedicated AWS Bedrock AI completions client ---
from typing import Optional
import json
import boto3
from app.core.settings import settings
from app.core.logging import logger
from shared.exceptions import DevOpsNexusException

import threading
import time

class LLMClient:
    """Manages conversational AI diagnostics exclusively utilizing AWS Bedrock models."""
    def __init__(self):
        self._last_bedrock_check: float = 0.0
        self._bedrock_verified: bool = False
        self._check_lock = threading.Lock()
        # Start background health-checker thread
        self._start_background_checker()

    def _start_background_checker(self):
        def _worker():
            # Initial slight delay so backend starts instantly
            time.sleep(2.0)
            while True:
                try:
                    self._check_bedrock_sync()
                except Exception as e:
                    logger.debug(f"Background Bedrock check encountered: {e}")
                time.sleep(300.0)

        t = threading.Thread(target=_worker, daemon=True, name="BedrockVerifierDaemon")
        t.start()

    def _check_bedrock_sync(self):
        with self._check_lock:
            region = getattr(settings, "BEDROCK_REGION", None) or getattr(settings, "DEFAULT_AWS_REGION", "us-east-1")
            target_model = getattr(settings, "BEDROCK_MODEL_ID", None) or "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            from botocore.config import Config
            boto_config = Config(connect_timeout=2.0, read_timeout=3.0, retries={'max_attempts': 0})
            client = boto3.client("bedrock-runtime", region_name=region, config=boto_config)
            try:
                response = client.converse(
                    modelId=target_model,
                    messages=[{"role": "user", "content": [{"text": "ping"}]}],
                    inferenceConfig={"temperature": 0.1, "maxTokens": 5}
                )
                if response.get("output"):
                    self._bedrock_verified = True
                    logger.info("AWS Bedrock successfully verified and active.")
            except Exception as e:
                err_str = str(e)
                if "Operation not allowed" in err_str or "AccessDenied" in err_str or "ValidationException" in err_str:
                    self._bedrock_verified = False
                    logger.debug(f"AWS Bedrock pending account activation: {err_str}")

    def _generate_bedrock_response(self, prompt: str, system_prompt: str, model_id: Optional[str] = None) -> str:
        if not self._bedrock_verified:
            # Bedrock is not yet verified on this AWS account; immediately yield to high-speed deterministic Jarvis
            raise DevOpsNexusException("AWS Bedrock pending AWS account verification (retrying in background).")

        region = getattr(settings, "BEDROCK_REGION", None) or getattr(settings, "DEFAULT_AWS_REGION", "us-east-1")
        target_model = model_id or getattr(settings, "BEDROCK_MODEL_ID", None) or "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

        candidate_models = [
            target_model,
            "amazon.nova-pro-v1:0",
            "amazon.nova-lite-v1:0",
            "us.meta.llama3-3-70b-instruct-v1:0"
        ]

        unique_candidates = []
        for m in candidate_models:
            if m and m not in unique_candidates:
                unique_candidates.append(m)

        from botocore.config import Config
        boto_config = Config(connect_timeout=2.0, read_timeout=3.0, retries={'max_attempts': 0})
        client = boto3.client("bedrock-runtime", region_name=region, config=boto_config)
        last_error = None

        for m_id in unique_candidates:
            try:
                response = client.converse(
                    modelId=m_id,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    system=[{"text": system_prompt}],
                    inferenceConfig={"temperature": 0.1, "maxTokens": 1024}
                )
                output_text = response.get("output", {}).get("message", {}).get("content", [])[0].get("text", "")
                if output_text:
                    self._bedrock_verified = True
                    logger.info(f"AWS Bedrock response successfully generated using model '{m_id}' in region '{region}'.")
                    return output_text
            except Exception as e:
                err_str = str(e)
                last_error = err_str
                logger.debug(f"Bedrock converse call failed for model {m_id}: {err_str}")
                if "Operation not allowed" in err_str or "AccessDenied" in err_str or "ValidationException" in err_str:
                    self._bedrock_verified = False
                    break

        raise DevOpsNexusException(f"AWS Bedrock model invocation failed in region '{region}': {last_error}")

    def generate_chat_response(
        self,
        prompt: str,
        system_prompt: str = "You are a DevOps Assistant.",
        provider: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """Exclusively invokes AWS Bedrock models."""
        return self._generate_bedrock_response(prompt, system_prompt, model_id=model)

llm_client = LLMClient()
