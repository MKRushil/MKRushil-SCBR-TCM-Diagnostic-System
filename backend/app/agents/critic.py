"""
CriticAgent - 評判代理
V3.1+ Reasoning Layer - Critic

職責：
- 舌脈對應檢核（最高優先級）
- 八綱一致性檢核
- 病程與解剖檢核
- 證據完整性檢核
- 信心分數計算
- 決策（PASS/FAIL/RETRY）
"""

import logging
from typing import Dict, Any
from enum import Enum
from app.agents.base import BaseAgent
from app.prompts.critic import CRITIC_SYSTEM_PROMPT, build_critic_prompt
from app.prompts.base import XML_OUTPUT_INSTRUCTION

logger = logging.getLogger(__name__)


class CriticDecision(str, Enum):
    """評判決策枚舉"""
    PASS = "PASS"
    FAIL = "FAIL"
    RETRY = "RETRY"


class CriticResult:
    """評判結果結構"""
    def __init__(
        self,
        decision: CriticDecision,
        confidence_score: float,
        critique: str,
        check_results: Dict[str, Any],
        correction_suggestion: str = None
    ):
        self.decision = decision
        self.confidence_score = confidence_score
        self.critique = critique
        self.check_results = check_results
        self.correction_suggestion = correction_suggestion


class CriticAgent(BaseAgent):
    """
    CriticAgent - 主任醫師 (Evaluator)
    
    執行任務：
    1. 舌脈對應檢核: 確認寒熱屬性與舌脈是否矛盾
    2. 八綱一致性檢核: 檢查診斷是否偏離族群傾向
    3. 病程與解剖檢核: 檢查是否違反病程邏輯或解剖學限制
    4. 證據完整性檢核: 檢查是否引用案例與修補過程
    5. 信心分數計算: 綜合相似度、共識度、規則符合度
    6. 觸發降級/重試: 若判定為 FAIL，提供修正建議
    """
    
    async def run(
        self,
        draft_diagnosis: Dict[str, Any],
        user_features: Dict[str, Any],
        analysis_result: Dict[str, Any]
    ) -> CriticResult:
        """
        執行診斷評判
        
        Args:
            draft_diagnosis: DiagnosisAgent 產出的診斷草稿
            user_features: 患者特徵（含舌脈）
            analysis_result: 戰情分析結果（含八綱傾向）
            
        Returns:
            CriticResult: 評判結果（包含決策、信心分數、評語）
        """
        logger.info("[Step 3: 適配與驗證] [CriticAgent] 正在進行嚴格檢核 (舌脈/八綱/證據)...")
        
        try:
            prompt = build_critic_prompt(
                draft_diagnosis,
                user_features,
                analysis_result
            )
            
            messages = [
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]
            
            response_text = await self.client.generate_completion(messages, temperature=0.0)
            result = self.parse_xml_json(response_text)
            
            decision = CriticDecision(result.get('decision', 'RETRY'))
            confidence_score = result.get('confidence_score', 0.5)
            critique = result.get('critique', '評判完成')
            check_results = result.get('check_results', {})
            correction_suggestion = result.get('correction_suggestion')
            
            # 記錄評判結果
            logger.info(f"[Step 3: 適配與驗證] [CriticAgent] 決策結果: {decision.value} (得分: {confidence_score:.2f})")
            
            # 記錄檢核細節 (Debug Level)
            for check_name, check_result in check_results.items():
                status = check_result.get('status', 'UNKNOWN')
                details = check_result.get('details', '')
                logger.debug(f"  - {check_name}: {status} | {details}")
            
            if decision == CriticDecision.FAIL:
                logger.warning(f"[Step 3: 適配與驗證] [CriticAgent] 駁回原因: {correction_suggestion}")
            elif decision == CriticDecision.RETRY:
                logger.info(f"[Step 3: 適配與驗證] [CriticAgent] 建議重試: {correction_suggestion}")
            
            return CriticResult(
                decision=decision,
                confidence_score=confidence_score,
                critique=critique,
                check_results=check_results,
                correction_suggestion=correction_suggestion
            )
        
        except Exception as e:
            logger.error(f"[Step 3: 適配與驗證] [CriticAgent] 評判過程發生錯誤: {e}")
            # Fallback: 保守策略，標記為 RETRY
            return CriticResult(
                decision=CriticDecision.RETRY,
                confidence_score=0.5,
                critique=f"評判過程發生錯誤: {str(e)}",
                check_results={},
                correction_suggestion="建議重試或使用下一順位案例"
            )
