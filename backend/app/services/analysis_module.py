"""
AnalysisModule - 分析模組
V3.1+ Architecture

職責：
1. 眾數分析 (Mode Analysis)：計算候選案例的診斷分佈
2. 離群值檢測 (Outlier Detection)
3. 八綱傾向分析 (8-Principles Tendency)
"""

import logging
from typing import List, Dict, Any
from collections import Counter

logger = logging.getLogger(__name__)

class AnalysisModule:
    """
    AnalysisModule - 分析模組
    取代原 War Room 概念，負責對檢索結果進行統計分析。
    """
    
    def __init__(self, syndrome_8p_map: Dict[str, Dict[str, float]] = None):
        """
        Args:
            syndrome_8p_map: 證型到八綱屬性的映射表
        """
        self.syndrome_8p_map = syndrome_8p_map or {}

    def analyze(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        執行全域數據分析
        
        Args:
            cases: Rerank 後的候選案例列表 (通常是 Top-5)
            
        Returns:
            Dict: 分析結果 (眾數、離群值、八綱傾向)
        """
        if not cases:
            return {
                "total_samples": 0,
                "mode_diagnosis": "N/A",
                "mode_percentage": 0.0,
                "top1_diagnosis": "N/A",
                "is_outlier_suspect": False,
                "eight_principles_stats": {},
                "dominant_nature": []
            }

        diagnoses = [c.get("diagnosis_main", "Unknown") for c in cases]
        syndromes = [c.get("diagnosis_syndrome", "") for c in cases]
        top1_diag = diagnoses[0]
        
        # 1. 眾數分析
        counts = Counter(diagnoses)
        mode_diag, mode_count = counts.most_common(1)[0]
        total = len(diagnoses)
        mode_pct = mode_count / total
        
        # 2. 離群值檢測
        # 若 Top-1 診斷與眾數不同，且眾數佔比超過 40%，則視為離群值嫌疑
        is_outlier = (top1_diag != mode_diag) and (mode_pct >= 0.4)
        
        # 3. 八綱傾向分析
        principle_counter = Counter()
        for syn in syndromes:
            # 嘗試從映射表中獲取八綱屬性
            # 這裡假設 map 的 value 是一個 list，例如 ["寒", "虛"]
            # 如果 map 的結構不同 (例如是 dict)，需要調整邏輯
            if syn in self.syndrome_8p_map:
                principles = self.syndrome_8p_map[syn]
                # 兼容 list 或 dict 格式
                if isinstance(principles, list):
                    principle_counter.update(principles)
                elif isinstance(principles, dict):
                    principle_counter.update(principles.keys())
        
        # 計算統計數據
        eight_p_stats = {}
        dominant_nature = []
        
        # 這裡的 total 應該是有效映射到的案例數，還是總案例數？通常用總數。
        # 但如果有些案例沒對應到八綱，會導致分母偏大。
        # 為了穩健，我們用 len(cases) 作為分母。
        
        if total > 0:
            for p, count in principle_counter.items():
                pct = count / total
                eight_p_stats[p] = pct
                if pct >= 0.5: # 顯著傾向閾值 (50% 以上)
                    dominant_nature.append(p)
        
        return {
            "total_samples": total,
            "mode_diagnosis": mode_diag,
            "mode_percentage": mode_pct,
            "top1_diagnosis": top1_diag,
            "is_outlier_suspect": is_outlier,
            "eight_principles_stats": eight_p_stats,
            "dominant_nature": dominant_nature
        }
