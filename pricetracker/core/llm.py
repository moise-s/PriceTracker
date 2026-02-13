import os
import logging
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI
from pricetracker.core.config import AgentConfig

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.client: Optional[AsyncOpenAI] = None
        
    def _get_client(self) -> AsyncOpenAI:
        if not self.client:
            api_key = os.environ.get(self.config.api_key_env)
            if not api_key:
                logger.warning(f"API key not found in env var: {self.config.api_key_env}")
            
            kwargs = {"api_key": api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
                
            self.client = AsyncOpenAI(**kwargs)
        return self.client

    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        response_format: Optional[Any] = None
    ) -> Any:
        client = self._get_client()
        model_name = model or self.config.model
        
        kwargs = {
            "model": model_name,
            "messages": messages,
        }
        
        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise
