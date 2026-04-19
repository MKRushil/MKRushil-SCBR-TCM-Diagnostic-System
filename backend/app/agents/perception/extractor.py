"""
SymptomExtractor - 症狀提取代理
V3.1+ Perception Pipeline - Step 1

職責：
- NER (命名實體識別)
- 否定詞偵測
- 時序標記
"""

import logging
from typing import Dict, Any
from app.agents.base import BaseAgent
from app.prompts.perception import EXTRACTOR_SYSTEM_PROMPT, build_extraction_prompt
from app.prompts.base import XML_OUTPUT_INSTRUCTION

logger = logging.getLogger(__name__)


class SymptomExtractor(BaseAgent):
    """
    SymptomExtractor - 聽診器
    
    執行任務：
    1. 命名實體識別 (NER): 識別症狀、部位、程度
    2. 否定詞偵測: 區分「有發燒」與「沒有發燒」
    3. 時序關係標記: 區分「現病史」與「既往史」
    """
    
    async def run(
        self, 
        user_input: str,
        user_context_only: str = None,      # [V3.1.1 Phase 1B] 只含 user turns 的上下文
        cumulative_features: dict = None    # [V3.1.1 Phase 1B] 累積特徵池（用於主訴繼承）
    ) -> Dict[str, Any]:
        """
        執行症狀提取
        
        Args:
            user_input: 使用者原始輸入
            user_context_only: 只含 user turns 的上下文（不含 assistant）
            cumulative_features: 累積特徵池（用於主訴繼承）
            
        Returns:
            Dict containing extracted symptoms
        """
        logger.info("[問題分析與加權] [SymptomExtractor] 正在進行實體提取 (NER)...")
        
        # [V3.1.1 Phase 1B] 使用 user_context_only（如果提供）
        if user_context_only:
            logger.info(f"[SymptomExtractor] 提取來源: extraction_source=user_only")
        
        try:
            prompt = build_extraction_prompt(user_input)
            messages = [
                {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]
            
            response_text = await self.client.generate_completion(messages, temperature=0.1)
            result = self.parse_xml_json(response_text)
            
            # [V3.1.1 Phase 1B] 主訴繼承：從 cumulative_features 讀取（session-scoped）
            current_cc = result.get('chief_complaint', '').strip()
            if not current_cc and cumulative_features:
                inherited_cc = cumulative_features.get('chief_complaint', '')
                if inherited_cc:
                    result['chief_complaint'] = inherited_cc
                    logger.info(f"[SymptomExtractor] 主訴繼承 (from cumulative): '{inherited_cc}'")
            
            cc = result.get('chief_complaint', '未知')
            symptoms = [s.get('name') for s in result.get('symptoms', []) if not s.get('negated')]
            logger.info(f"[問題分析與加權] [SymptomExtractor] 提取結果: 主訴='{cc}', 有效症狀={symptoms}")
            return result
        
        except Exception as e:
            logger.error(f"[問題分析與加權] [SymptomExtractor] 提取失敗: {e}")
            # Fallback: 返回最小化結構
            return {
                "raw_symptoms_extracted": {
                    "chief_complaint": user_input[:50],
                    "symptoms": [],
                    "negated_symptoms": [],
                    "temporal_symptoms": [],
                    "tongue": "未提供",
                    "pulse": "未提供"
                }
            }

