import logging
import json # Import json
from app.agents.base import BaseAgent
from app.core.orchestrator import WorkflowState
from app.prompts.base import SYSTEM_PROMPT_CORE, XML_OUTPUT_INSTRUCTION
from app.prompts.memory import GAP_ANALYSIS_SYSTEM_PROMPT, build_gap_analysis_prompt
from app.api.schemas import UnifiedResponse, DiagnosisItem, FollowUpQuestion, ResponseType

logger = logging.getLogger(__name__)

class MemoryAgent(BaseAgent):
    """
    規格書 3.3 Path A Logic: 
    Retrieve (已在 Orchestrator 完成) -> Align -> Revise (Gap Analysis)
    """
    
    async def run(self, state: WorkflowState) -> WorkflowState:
        # 1. 獲取 Orchestrator 檢索到的最佳案例
        # 注意：state.retrieved_context 是一個 list，Path A 假設有至少一個高分案例
        if not state.retrieved_context:
            logger.warning("[MemoryAgent] No context retrieved for Path A.")
            return state
            
        best_case = state.retrieved_context[0] # Top 1
        base_similarity = best_case.get('similarity', 0.0)
        
        # 從 summary 中提取素體與新感特徵
        constitution_features = []
        acute_onset_features = []
        
        try:
            summary_data = {}
            if isinstance(state.diagnosis_summary, dict):
                summary_data = state.diagnosis_summary
            elif isinstance(state.diagnosis_summary, str):
                summary_data = json.loads(state.diagnosis_summary)
            
            constitution_features = summary_data.get("constitution_features", [])
            acute_onset_features = summary_data.get("acute_onset_features", [])
        except Exception as e:
            logger.warning(f"[MemoryAgent] Failed to parse diagnosis_summary: {e}")
        
        # 2. 構建 Prompt
        prompt = build_gap_analysis_prompt(
            patient_input=state.user_input_raw,
            ref_case=best_case,
            constitution_features=constitution_features,
            acute_onset_features=acute_onset_features
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_CORE + "\n" + GAP_ANALYSIS_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
            {"role": "user", "content": prompt}
        ]
        
        # 3. 呼叫 LLM 進行差異分析
        response_text = await self.client.generate_completion(messages, temperature=0.1)
        
        try:
            result = self.parse_xml_json(response_text)
            
            # 4. 處理修訂結果
            revised_diag_name = result.get("revised_diagnosis", best_case.get('diagnosis_main'))
            revised_treatment = result.get("revised_treatment", best_case.get('treatment_principle'))
            modification_note = result.get("modification_note", "")
            risk_flag = result.get("risk_flag", False)
            conf_adj = result.get("confidence_adjustment", 0.0)
            
            final_confidence = max(0.0, min(1.0, base_similarity + conf_adj))
            
            # 5. 構建 UnifiedResponse
            diagnosis_list = [
                DiagnosisItem(
                    rank=1,
                    disease_name=revised_diag_name,
                    confidence=final_confidence,
                    condition=None
                )
            ]
            
            # 構建 Evidence Trace (顯示修訂過程)
            evidence_trace = (
                f"Path A (Memory): 基於相似案例 (ID: {best_case.get('case_id')}) 進行修訂。\n"
                f"相似度: {base_similarity:.2f} -> 修正後: {final_confidence:.2f}\n"
                f"差異分析: {modification_note}"
            )
            
            # 構建 Formatted Report
            formatted_report = (
                f"### 診斷建議 (基於案例修訂)\n"
                f"**診斷:** {revised_diag_name}\n"
                f"**建議治則:** {revised_treatment}\n"
                f"**參考病機:** {best_case.get('pathology_analysis')}\n"
                f"**修訂說明:** *{modification_note}*"
            )
            
            if risk_flag:
                formatted_report += "\n\n**[警示]** 病人症狀與參考案例存在潛在衝突，請醫師審慎評估。"

            response = UnifiedResponse(
                response_type=ResponseType.DEFINITIVE if not risk_flag else ResponseType.FALLBACK,
                diagnosis_list=diagnosis_list,
                follow_up_question=FollowUpQuestion(
                    required=False, 
                    question_text=f"系統參考了類似案例並針對您的特殊情況做了微調：{modification_note}。請問是否符合您的狀況？", 
                    options=["符合", "補充說明", "不符合"]
                ),
                evidence_trace=evidence_trace,
                safety_warning="潛在病機衝突" if risk_flag else None,
                visualization_data={},
                formatted_report=formatted_report
            )
            
            state.final_response = response
            
        except Exception as e:
            logger.error(f"[MemoryAgent] Gap analysis failed: {str(e)} \nRaw: {response_text}")
            
            # Fallback for parsing error in MemoryAgent
            state.final_response = UnifiedResponse(
                response_type=ResponseType.FALLBACK,
                diagnosis_list=[],
                follow_up_question=FollowUpQuestion(required=True, question_text="系統在案例分析時發生錯誤，請提供更多細節。", options=[]),
                evidence_trace=f"System Error in Memory Agent: {str(e)}",
                formatted_report="",
                safety_warning="案例分析異常",
                visualization_data={}
            )
            
        return state
