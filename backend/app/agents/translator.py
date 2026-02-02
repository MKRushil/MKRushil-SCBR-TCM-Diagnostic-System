from typing import Dict, Any, List
import logging
from collections import Counter

from app.agents.base import BaseAgent
from app.core.orchestrator import WorkflowState
from app.prompts.base import SYSTEM_PROMPT_CORE, XML_OUTPUT_INSTRUCTION
from app.prompts.translator import TRANSLATOR_SYSTEM_PROMPT, build_translation_prompt
# WeaviateClient is no longer directly used in Translator for inference, only for prompt building if needed
# from app.database.weaviate_client import WeaviateClient # Removed as not directly querying ontology anymore
from weaviate.classes.query import Filter # Still needed for Filter.by_property if part of schema validation
import asyncio # Still needed for async context if other async tasks were there, but now not for gather

logger = logging.getLogger(__name__)

class TranslatorAgent(BaseAgent):
    """
    規格書 3.3 LLM Translation
    負責將 Raw Input 轉為 Standardized Features。
    [Update V3.0] 負責生成 Weighted Query String 及提取 Primary Location (LLM-Driven)。
    """
    def __init__(self, nvidia_client, weaviate_client=None): # weaviate_client is now optional
        super().__init__(nvidia_client)
        self.weaviate_client = weaviate_client # Keep if needed elsewhere, but not for primary_location

    async def run(self, state: WorkflowState) -> WorkflowState:
        logger.info("🔍 [Translator] 開始分析用戶輸入...")
        prompt = build_translation_prompt(state.user_input_raw)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_CORE + "\n" + TRANSLATOR_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
            {"role": "user", "content": prompt}
        ]
        
        response_text = await self.client.generate_completion(messages, temperature=0.1)
        
        try:
            parsed_data = self.parse_xml_json(response_text)
            state.standardized_features = parsed_data
            
            # --- V3.0 Logic: Weighted Query Generation ---
            chief_complaint = parsed_data.get("chief_complaint", "")
            symptoms = parsed_data.get("symptoms", [])
            
            weighted_parts = []
            
            if chief_complaint:
                weighted_parts.append((chief_complaint + " ") * 5)
            
            for i, sym in enumerate(symptoms):
                if i < 2:
                    weighted_parts.append((sym + " ") * 2)
                else:
                    weighted_parts.append(sym)
            
            state.weighted_query_string = " ".join(weighted_parts)
            logger.debug(f"⚖️ [Translator] 生成加權查詢: '{state.weighted_query_string[:50]}...'")
            # ---------------------------------------------

            # --- V3.0 Logic: Primary Location Extraction (LLM-Driven) ---
            # Directly extract primary_location from LLM's parsed_data
            llm_inferred_location = parsed_data.get("primary_location")
            if llm_inferred_location and llm_inferred_location.strip() and llm_inferred_location != "未知":
                state.primary_location = llm_inferred_location
            else:
                state.primary_location = None # Fallback if LLM doesn't provide or provides '未知'
            
            logger.info(f"✅ [Translator] 解析完成: 主訴='{chief_complaint}', 病位='{state.primary_location}', 急症={parsed_data.get('is_emergency')}")
            # ---------------------------------------------

        except Exception as e:
            logger.error(f"🔴 [Translator] 解析失敗: {e}")
            state.standardized_features = {
                "chief_complaint": state.user_input_raw,
                "symptoms": [],
                "is_missing_info": True
            }
            state.weighted_query_string = state.user_input_raw
            state.primary_primary_location = None
            
        return state

    # Removed _infer_primary_location as it's now LLM-driven