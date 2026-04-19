import logging
from jinja2 import Template
from app.core.orchestrator import WorkflowState

logger = logging.getLogger(__name__)

class ReportGenerator:
    """
    規格書 4.0 補充模組 3: 結構化報告生成器
    """
    
    TEMPLATE_STR = """
    ## 中醫輔助診斷報告
    **病患 ID:** {{ patient_id }}
    **主訴:** {{ chief_complaint }}
    
    ### 診斷建議
    {% for diag in diagnosis_list %}
    - **{{ diag.disease_name }}** (信心度: {{ "%.2f"|format(diag.confidence) }})
      {% if diag.condition %}
      > *條件: {{ diag.condition }}*
      {% endif %}
    {% endfor %}
    
    ### 治療策略 (僅供參考)
    {{ treatment_principle }}
    
    ---
    *本報告由 AI 輔助生成，具體處方請依醫師臨床判斷為準。*
    """

    @staticmethod
    def generate(state: WorkflowState) -> str:
        try:
            if not state.final_response:
                return ""

            template = Template(ReportGenerator.TEMPLATE_STR)
            
            # 準備 context
            context = {
                "patient_id": state.patient_id,
                "chief_complaint": state.user_input_raw, # 簡單起見用 Raw
                "diagnosis_list": state.final_response.diagnosis_list,
                "treatment_principle": state.final_response.formatted_report or "未提供詳細治則"
            }
            
            report_md = template.render(context)
            return report_md

        except Exception as e:
            logger.error(f"[ReportGen] Generation failed: {str(e)}")
            return "無法生成結構化報告。"