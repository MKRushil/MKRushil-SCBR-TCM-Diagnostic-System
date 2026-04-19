from typing import List, Dict, Any

class WeaviateSchema:
    """
    規格書 3.2 資料庫 Schema (Weaviate - BYOV Mode) - V2.1 Hierarchical & Enriched
    完整版 (包含所有 4 個 Class)
    """
    
    @staticmethod
    def get_schema() -> List[Dict[str, Any]]:
        return [
            # -------------------------------------------------------
            # 1. TCM_Reference_Case (案例庫 - 層次化升級版)
            # -------------------------------------------------------
            {
                "class": "TCM_Reference_Case",
                "description": "Path A 檢索用的專家案例，包含指向術語庫的層次化連結",
                "vectorizer": "none",
                "properties": [
                    # --- ID 與 顯示用欄位 ---
                    {"name": "case_id", "dataType": ["text"], "tokenization": "field"},
                    {"name": "source_type", "dataType": ["text"]},
                    {"name": "chief_complaint", "dataType": ["text"]},
                    
                    # --- 層次化關聯 (Cross-References) ---
                    {
                        "name": "hasPrimarySymptoms",
                        "dataType": ["TCM_Standard_Ontology"],
                        "description": "指向術語庫的主症 (Cross-Reference)"
                    },
                    {
                        "name": "hasSecondarySymptoms",
                        "dataType": ["TCM_Standard_Ontology"],
                        "description": "指向術語庫的次症 (Cross-Reference)"
                    },

                    # --- 原始資料備份 ---
                    {"name": "original_tags", "dataType": ["text[]"], "description": "原始標籤備份"},

                    # --- 向量生成專用欄位 (內容增強) ---
                    {"name": "embedding_text", "dataType": ["text"], "description": "融合了術語定義與權重的向量文本"},

                    # --- 診斷結果 ---
                    {"name": "diagnosis_main", "dataType": ["text"]},
                    {"name": "diagnosis_syndrome", "dataType": ["text"]},
                    {"name": "treatment_principle", "dataType": ["text"]},
                    {"name": "pathology_analysis", "dataType": ["text"]},
                    {"name": "confidence_score", "dataType": ["number"]},
                ]
            },
            
            # -------------------------------------------------------
            # 2. TCM_Standard_Ontology (術語庫 - 底層知識)
            # -------------------------------------------------------
            {
                "class": "TCM_Standard_Ontology",
                "description": "Path B 語意標準化用的術語定義",
                "vectorizer": "none",
                "properties": [
                    {"name": "term_id", "dataType": ["text"], "tokenization": "field"},
                    {"name": "term_name", "dataType": ["text"]},
                    {"name": "category", "dataType": ["text"]},
                    {"name": "definition", "dataType": ["text"]},
                    {"name": "synonyms", "dataType": ["text[]"]},
                    # 術語本身也需要向量化，以便進行「概念檢索」
                    {"name": "embedding_text", "dataType": ["text"]},
                ]
            },
            
            # -------------------------------------------------------
            # 3. TCM_Session_Memory (對話記憶 - 完整定義)
            # -------------------------------------------------------
            {
                "class": "TCM_Session_Memory",
                "description": "螺旋上下文追溯與對話歷史記錄",
                "vectorizer": "none",
                "properties": [
                     # 識別資訊
                     {"name": "patient_id", "dataType": ["text"]},
                     {"name": "session_id", "dataType": ["text"], "tokenization": "field"},
                     {"name": "turn_index", "dataType": ["int"]},
                     {"name": "role", "dataType": ["text"]}, # 'user' or 'assistant'
                     
                     # 原始對話內容
                     {"name": "content", "dataType": ["text"]},
                     
                     # --- 結構化記憶 (可選：若要層次化也可指向 Ontology) ---
                     # 這裡暫存為文字陣列，方便快速讀取
                     {"name": "confirmed_symptoms", "dataType": ["text[]"], "description": "本回合確認的陽性症狀"},
                     {"name": "diagnosis_summary", "dataType": ["text"], "description": "AI 的階段性總結"},
                     
                     # --- 向量生成專用 (用於檢索相似歷史對話) ---
                     {"name": "embedding_text", "dataType": ["text"]},
                     
                     {"name": "timestamp", "dataType": ["date"]},
                ]
            },
            
            # -------------------------------------------------------
            # 4. TCM_Diagnostic_Rules (診斷規則庫 - 層次化升級版)
            # -------------------------------------------------------
            {
                "class": "TCM_Diagnostic_Rules",
                "description": "Path B 規則檢索，建立與術語庫的強關聯",
                "vectorizer": "none",
                "properties": [
                    {"name": "rule_id", "dataType": ["text"], "tokenization": "field"},
                    {"name": "syndrome_name", "dataType": ["text"]},
                    {"name": "category", "dataType": ["text"]},
                    
                    # --- 層次化關聯 (Cross-References) ---
                    {
                        "name": "hasMainSymptoms",
                        "dataType": ["TCM_Standard_Ontology"],
                        "description": "指向術語庫的主症 (Cross-Reference)"
                    },
                    {
                        "name": "hasSecondarySymptoms",
                        "dataType": ["TCM_Standard_Ontology"],
                        "description": "指向術語庫的次症 (Cross-Reference)"
                    },

                    # 其他特徵
                    {"name": "tongue_pulse", "dataType": ["text[]"]}, 
                    {"name": "exclusion", "dataType": ["text[]"]},
                    {"name": "treatment_principle", "dataType": ["text"]},
                    
                    # 規則的向量文本
                    {"name": "embedding_text", "dataType": ["text"]},
                ]
            }
        ]