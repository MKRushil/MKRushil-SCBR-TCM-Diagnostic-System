"""
DiagnosisAgent - 診斷生成代理
V3.1+ Reasoning Layer - Actor

職責：
- 策略選擇（微幅修補 vs 大幅重構）
- 適應性修補（繼承/反轉/剪裁/擴展）
- 八綱整合
- 生成診斷草稿
"""

import logging
from typing import Dict, Any, List
from app.agents.base import BaseAgent
from app.prompts.diagnosis import DIAGNOSIS_SYSTEM_PROMPT, build_diagnosis_prompt
from app.prompts.base import XML_OUTPUT_INSTRUCTION

logger = logging.getLogger(__name__)


class DiagnosisAgent(BaseAgent):
    """
    DiagnosisAgent - 主治醫師 (Generator)
    
    執行任務：
    1. 策略選擇: 根據離群判定選擇「微幅修補」或「大幅重構」
    2. 適應性修補: 以 Anchor Case 為模板進行 Delta 調整
    3. 八綱整合: 參考戰情分析的八綱傾向
    4. 生成治則: 根據修補後的病機生成治療原則
    """
    
    async def run(
        self,
        user_features: Dict[str, Any],
        anchor_case: Dict[str, Any],
        analysis_result: Dict[str, Any],
        retrieved_rules: List[Dict] = None,
        baseline_mode: str = "none" # [V3.1] Experiment Mode
    ) -> Dict[str, Any]:
        """
        執行診斷生成
        
        Args:
            user_features: 患者特徵（含症狀、舌脈）
            anchor_case: Top-1 黃金案例
            analysis_result: 戰情分析結果（含離群判定、八綱傾向）
            retrieved_rules: 參考規則（可選）
            
        Returns:
            Dict containing draft diagnosis
        """
        if retrieved_rules is None:
            retrieved_rules = []
        
        is_outlier = analysis_result.get('is_outlier_suspect', False)
        
        from app.prompts.diagnosis import StrategyType
        strategy_type = StrategyType.MAJOR_RECONSTRUCTION if is_outlier else StrategyType.MINOR_REPAIR
        
        prompt = build_diagnosis_prompt(
            user_features, 
            anchor_case, 
            analysis_result,
            retrieved_rules,
            strategy_type,
            baseline_mode # Pass baseline_mode
        )
        
        logger.info(f"[Step 2: 協商與修補] [DiagnosisAgent] 正在執行診斷推理 (策略: {strategy_type.value})...")
        
        try:
            messages = [
                {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]
            
            response_text = await self.client.generate_completion(messages, temperature=0.3)
            result = self.parse_xml_json(response_text)
            
            # 確保信心分數是 float
            disease_name = result.get('disease_name', '未知診斷')
            try:
                confidence = float(result.get('confidence_level', 0.0))
            except (ValueError, TypeError):
                confidence = 0.0
            
            logger.info(f"[Step 2: 協商與修補] [DiagnosisAgent] 初步推理完成: 診斷='{disease_name}', 信心={confidence:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"[Step 2: 協商與修補] [DiagnosisAgent] 推理過程發生錯誤: {e}")
            # Fallback (返回 None，讓 Orchestrator 處理重試或降級)
            return None
