import logging
from typing import Dict, Any
from app.core.orchestrator import WorkflowState

logger = logging.getLogger(__name__)

class VisualizationAdapter:
    """
    規格書 4.0 補充模組 2: 可解釋性視覺化轉接器
    負責清洗數據並轉換為 ECharts 格式。
    """
    
    @staticmethod
    def process(state: WorkflowState) -> Dict[str, Any]:
        """
        嘗試從 LLM 輸出或標準化特徵中提取八綱 (Eight Principles) 數據。
        """
        try:
            # 假設 reasoning agent 的輸出中包含了八綱的傾向分數
            # 這裡模擬數據清洗
            raw_data = state.standardized_features.get("eight_principles_score", {})
            
            # Log raw data for debugging
            logger.info(f"[Viz] Raw 8-Principles Data: {raw_data}")
            
            # 防呆機制 (Sanitization): 若無數據，回傳空
            if not raw_data:
                logger.info("[Viz] No eight principles data found, skipping chart.")
                return {}

            # Helper to safely get score (case-insensitive)
            def get_score(key: str) -> int:
                val = raw_data.get(key) or raw_data.get(key.capitalize()) or raw_data.get(key.upper()) or 0
                try:
                    return int(val)
                except:
                    return 0

            # 建構 ECharts 雷達圖 Option
            echarts_option = {
                "title": {"text": "八綱辨證傾向"},
                "radar": {
                    "indicator": [
                        {"name": "陰 (Yin)", "max": 10},
                        {"name": "陽 (Yang)", "max": 10},
                        {"name": "表 (Biao)", "max": 10},
                        {"name": "裡 (Li)", "max": 10},
                        {"name": "寒 (Han)", "max": 10},
                        {"name": "熱 (Re)", "max": 10},
                        {"name": "虛 (Xu)", "max": 10},
                        {"name": "實 (Shi)", "max": 10}
                    ]
                },
                "series": [{
                    "name": "辨證分數",
                    "type": "radar",
                    "data": [{
                        "value": [
                            get_score("yin"),
                            get_score("yang"),
                            get_score("biao"),
                            get_score("li"),
                            get_score("han"),
                            get_score("re"),
                            get_score("xu"),
                            get_score("shi")
                        ]
                    }]
                }]
            }
            return echarts_option

        except Exception as e:
            logger.error(f"[Viz] Processing failed: {str(e)}")
            return {}