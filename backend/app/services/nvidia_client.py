import httpx
import logging
import numpy as np
from typing import Dict, Any, List
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

class NvidiaClient:
    """
    規格書 1.2: 資源調度策略與 API 封裝
    負責與 NVIDIA NIM 服務溝通。
    包含 Error 500 防禦機制 (Soft Landing) 與 Mock 降級。
    """
    def __init__(self):
        self.llm_api_key = settings.NVIDIA_LLM_API_KEY
        self.embedding_api_key = settings.NVIDIA_EMBEDDING_API_KEY
        self.base_url = settings.LLM_API_URL
        self.model = settings.LLM_MODEL_NAME
        self.embed_model = settings.EMBEDDING_MODEL_NAME
        
    def _get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def get_embedding(self, text: str, input_type: str = "query") -> List[float]:
        """
        獲取向量 (含：空值攔截 + 錯誤軟著陸 + Mock 降級)
        Args:
            text: 輸入文本
            input_type: 'query' 或 'passage' (僅針對 E5 模型生效)
        """
        # [防禦] 第一道防線：空值攔截 (Input Sanitization)
        if not text or not str(text).strip():
            logger.warning(f"[NvidiaClient] Embedding input is empty or None. Returning random vector.")
            return list(np.random.rand(1024))

        url = f"{self.base_url}/embeddings"
        payload = {
            "input": [text],
            "model": self.embed_model,
            "encoding_format": "float"
        }
        
        # [Compatibility] Only add input_type for E5 models
        if "e5" in self.embed_model.lower():
            payload["input_type"] = input_type
        
        headers = self._get_headers(self.embedding_api_key)
        
        # [防禦] 第二道防線：API 錯誤軟著陸 (Soft Landing)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client: # Embedding 快，30s 足夠
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data['data'][0]['embedding']

        except Exception as e:
            # 🛡️ 第三道防線：Mock 降級 (Fallback)
            logger.error(f"[NvidiaClient] Embedding API failed for: '{str(text)[:20]}...'. Reason: {str(e)}")
            logger.warning(f"[NvidiaClient] System falling back to Mock Vector to prevent crash.")
            
            # 回傳隨機向量，讓流程能繼續走下去
            return list(np.random.rand(1024))

    async def generate_completion(self, 
                                messages: List[Dict[str, str]], 
                                temperature: float = 0.2,
                                max_tokens: int = 4096) -> str:
        """
        調用 LLM 生成回應 (含 Timeout 優化)
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": 0.7,
            "max_tokens": max_tokens,
            "stream": False
        }

        headers = self._get_headers(self.llm_api_key)

        try:
            async with httpx.AsyncClient(timeout=120.0) as client: # ⚠️ 延長至 120 秒
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data['choices'][0]['message']['content']
                return content
        except Exception as e:
            logger.error(f"[NvidiaClient] LLM Generation Failed: {str(e)}")
            raise e