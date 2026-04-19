import logging
import json
from app.agents.base import BaseAgent
from app.core.orchestrator import WorkflowState
from app.prompts.base import SYSTEM_PROMPT_CORE, XML_OUTPUT_INSTRUCTION
from app.prompts.summarizer import SUMMARIZER_SYSTEM_PROMPT, build_summarizer_prompt

logger = logging.getLogger(__name__)

class SummarizerAgent(BaseAgent):
    """
    規格書 3.4: 螺旋上下文與 LLM10 防禦
    執行時機: HTTP Response 回傳後 (Background Task)
    功能: 壓縮對話歷史，提取結構化事實。
    """
    
    async def run(self, state: WorkflowState) -> WorkflowState:
        logger.info(f"[Summarizer] Starting background summarization for Session: {state.session_id}")
        
        try:
            # 準備舊摘要 (如果是 Dict 則轉字串)
            current_summary_str = "尚無摘要"
            if state.diagnosis_summary:
                if isinstance(state.diagnosis_summary, dict):
                    current_summary_str = json.dumps(state.diagnosis_summary, ensure_ascii=False)
                else:
                    current_summary_str = str(state.diagnosis_summary)

            prompt = build_summarizer_prompt(
                history_content=state.user_input_raw,
                current_summary=current_summary_str
            )

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_CORE + "\n" + SUMMARIZER_SYSTEM_PROMPT + "\n" + XML_OUTPUT_INSTRUCTION},
                {"role": "user", "content": prompt}
            ]

            # 呼叫 LLM
            response_text = await self.client.generate_completion(messages, temperature=0.1)
            
            # 解析結果
            result = self.parse_xml_json(response_text)
            
            # 更新狀態 - 直接儲存完整的結構化結果 (Dict)
            state.diagnosis_summary = result
            
            summary_text = result.get("updated_diagnosis_summary", "")
            logger.info(f"[Summarizer] Summary updated: {summary_text[:50]}...")
            
            return state

        except Exception as e:
            logger.error(f"[Summarizer] Failed to summarize: {str(e)}")
            return state