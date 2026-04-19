import logging
import json
from app.agents.base import BaseAgent
from app.core.orchestrator import WorkflowState
from app.prompts.base import SYSTEM_PROMPT_CORE, XML_OUTPUT_INSTRUCTION
# Import V3.0 Prompt components
from app.prompts.reasoning import CLUSTER_CBR_SYSTEM_PROMPT, build_cluster_cbr_prompt
from app.api.schemas import UnifiedResponse, DiagnosisItem, FollowUpQuestion, ResponseType
from app.database.weaviate_client import WeaviateClient

logger = logging.getLogger(__name__)

class ReasoningAgent(BaseAgent):
    """
    SCBR V3.0 Reasoning Agent
    Core Logic: Cluster Decision with Anchor Repair (群體決策 + 黃金案例修補)
    """
    def __init__(self, nvidia_client, weaviate_client: WeaviateClient):
        super().__init__(nvidia_client)
        self.weaviate_client = weaviate_client

    async def run(self, state: WorkflowState) -> WorkflowState:
        # V3.0: 移除內部的重複檢索邏輯，改為從 state 接收 Orchestrator 準備好的資料
        # 1. 獲取資料
        retrieved_cases = state.retrieved_context if state.retrieved_context else []
        retrieved_rules = getattr(state, 'retrieved_rules', [])
        distribution_pool = getattr(state, 'distribution_pool', {})
        
        logger.info(f"🧬 [Reasoning] 接收戰情數據: 案例數={len(retrieved_cases)}, 規則數={len(retrieved_rules)}")
        logger.debug(f"📊 [Reasoning] 診斷分佈: {distribution_pool}")

        # 2. 準備 Prompt 輸入特徵
        features_for_prompt = {
            "user_input_raw": state.user_input_raw,
            "standardized_features": state.standardized_features, 
            "diagnosis_summary": state.diagnosis_summary 
        }
        
        # 3. 構建 V3.0 Cluster-CBR Prompt
        prompt = build_cluster_cbr_prompt(
            features=features_for_prompt,
            distribution_pool=distribution_pool,
            retrieved_cases=retrieved_cases,
            retrieved_rules=retrieved_rules
        )
        
        logger.info("🧠 [Reasoning] 啟動 LLM 進行 Cluster-CBR 推理 (定位 -> 否決 -> 修補)...")
        
        # 4. LLM 推理
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_CORE + "\n" + CLUSTER_CBR_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
            {"role": "user", "content": prompt}
        ]
        
        response_text = await self.client.generate_completion(messages, temperature=0.1)
        
        try:
            result_json = self.parse_xml_json(response_text)
            
            diagnosis_list = [DiagnosisItem(**d) for d in result_json.get("diagnosis_list", [])]
            
            # --- Log Reasoning Outcome ---
            top_diag = diagnosis_list[0].disease_name if diagnosis_list else "Unknown"
            logger.info(f"💡 [Reasoning] 推理完成。首選診斷: '{top_diag}' (Confidence: {diagnosis_list[0].confidence if diagnosis_list else 0.0})")
            if result_json.get("evidence_trace"):
                logger.debug(f"📜 [Reasoning] 推理軌跡摘要: {result_json['evidence_trace'][:100]}...")
            # -----------------------------

            follow_up_data = result_json.get("follow_up_question")
            follow_up = None
            if follow_up_data:
                if not follow_up_data.get("question_text") and follow_up_data.get("discriminating_question"):
                    follow_up_data["question_text"] = follow_up_data["discriminating_question"]
                
                try:
                    follow_up = FollowUpQuestion(**follow_up_data)
                except Exception as e:
                    logger.warning(f"[Reasoning] FollowUpQuestion validation failed: {e}. Using fallback.")
                    follow_up = FollowUpQuestion(required=False, question_text="請問還有其他症狀嗎？", options=[])

            response_type = result_json.get("response_type", ResponseType.FALLBACK)
            
            formatted_report_content = result_json.get("formatted_report")
            if not formatted_report_content and response_type == ResponseType.FALLBACK and diagnosis_list:
                formatted_report_content = "## 鑑別診斷報告 (可能證型)\n"
                for diag in diagnosis_list:
                    formatted_report_content += f"- **{diag.disease_name}** (信心度: {diag.confidence:.1%})\n"
                    if diag.condition:
                        formatted_report_content += f"  - *判斷依據/待確認:* {diag.condition}\n"
                formatted_report_content += "\n---"

            # 注入真實的引用來源到 evidence_trace (增強可解釋性)
            evidence_trace = result_json.get("evidence_trace", "無法取得推導過程")
            if retrieved_rules:
                top_rule = retrieved_rules[0]
                rule_name = top_rule.get('syndrome_name') or top_rule.get('rule_id')
                evidence_trace += f"\n\n(系統參考規則: {rule_name})"

            response = UnifiedResponse(
                response_type=response_type,
                diagnosis_list=diagnosis_list,
                follow_up_question=follow_up,
                evidence_trace=evidence_trace,
                safety_warning=None,
                visualization_data=None,
                formatted_report=formatted_report_content
            )
            state.diagnosis_candidates = diagnosis_list
            state.final_response = response
            # Note: state.retrieved_context is already set by Orchestrator
            
        except Exception as e:
            logger.error(f"🔴 [Reasoning] LLM 輸出解析失敗: {e} \nRaw Output: {response_text}")
            
            state.final_response = UnifiedResponse(
                response_type=ResponseType.FALLBACK,
                diagnosis_list=[],
                follow_up_question=FollowUpQuestion(required=True, question_text="系統推導發生錯誤，請重新描述症狀。", options=[]),
                evidence_trace=f"System Error: {str(e)}",
                formatted_report="",
                safety_warning=None,
                visualization_data=None
            )
            
        return state