from abc import ABC, abstractmethod
from typing import Any, Dict
from app.services.nvidia_client import NvidiaClient
from app.core.orchestrator import WorkflowState

class BaseAgent(ABC):
    """
    規格書 2.0: Agent 基礎介面
    所有 Agent 必須繼承此類別並實作 run 方法。
    """
    def __init__(self, nvidia_client: NvidiaClient):
        self.client = nvidia_client

    @abstractmethod
    async def run(self, state: WorkflowState) -> WorkflowState:
        """
        接收當前 WorkflowState，執行邏輯後回傳更新後的 State。
        """
        pass
    
    def parse_xml_json(self, llm_output: str) -> Dict[str, Any]:
        """
        輔助函式：從 LLM 輸出中提取 JSON 區塊並解析。
        支援 <json> 標籤、Markdown Code Block 或直接尋找 {}。
        """
        import re
        import json
        
        # 1. 嘗試尋找 <json> 標籤
        match = re.search(r'<json>(.*?)</json>', llm_output, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass # 繼續嘗試其他方法

        # 2. 嘗試尋找 Markdown Code Block (```json ... ```)
        match = re.search(r'```json\s*(.*?)\s*```', llm_output, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 3. 嘗試尋找最外層的 {}
        # 這是最暴力的解法，尋找第一個 { 和最後一個 }
        try:
            start = llm_output.find('{')
            end = llm_output.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = llm_output[start:end+1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # 4. 如果都失敗，拋出詳細錯誤
        raise ValueError(f"Could not parse JSON from output. Raw length: {len(llm_output)}")