import json
import logging
import os
from typing import List, Dict, Any
from app.core.config import get_settings
from app.database.weaviate_client import WeaviateClient
from app.services.nvidia_client import NvidiaClient

settings = get_settings()
logger = logging.getLogger(__name__)

class SyncManager:
    """
    規格書 8.0: 資料同步策略 (Startup Sync)
    邏輯:
    1. 讀取 data/*.json (Single Source of Truth)
    2. 讀取 Weaviate 現有 IDs
    3. 計算差集 (Diff)
    4. 呼叫 NVIDIA Embedding 並寫入 Weaviate
    """
    
    DATA_DIR = "./data"
    FILES_MAPPING = {
        "TCM_Reference_Case": "tcm_expert_cases.json",
        "TCM_Standard_Ontology": "tcm_ontology.json",
        "TCM_Diagnostic_Rules": "tcm_diagnostic_rules.json"
    }

    def __init__(self):
        self.weaviate_client = WeaviateClient()
        self.nvidia_client = NvidiaClient()

    async def run_sync(self):
        logger.info("[Sync] Starting data synchronization...")
        
        try:
            for class_name, filename in self.FILES_MAPPING.items():
                file_path = os.path.join(self.DATA_DIR, filename)
                if not os.path.exists(file_path):
                    logger.warning(f"[Sync] File not found: {file_path}, skipping.")
                    continue

                # 1. Load JSON
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)
                    # 假設 JSON 是一個 List
                    if not isinstance(file_data, list):
                        logger.error(f"[Sync] Invalid JSON format in {filename}, expected List.")
                        continue

                # 2. Get Existing IDs from Weaviate
                existing_ids = self.weaviate_client.get_all_ids(class_name)
                
                # 3. Calculate Diff & Insert
                new_items = []
                for item in file_data:
                    item_id = item.get("case_id") or item.get("term_id") or item.get("rule_id")
                    if item_id and item_id not in existing_ids:
                        new_items.append(item)

                if new_items:
                    logger.info(f"[Sync] Found {len(new_items)} new items for {class_name}.")
                    await self._process_batch(class_name, new_items)
                else:
                    logger.info(f"[Sync] {class_name} is up to date.")

        except Exception as e:
            logger.error(f"[Sync] Critical Error during sync: {str(e)}")
            # 不拋出錯誤，讓 App 繼續啟動，但記錄 Log
        finally:
            self.weaviate_client.close()

    async def _process_batch(self, class_name: str, items: List[Dict]):
        """
        序列化處理 Embedding 並寫入，避免觸發 API Rate Limit
        Updated to match Ingestion.py embedding_text format for consistency.
        """
        for item in items:
            try:
                # 準備 Embedding Text 與 屬性轉換 (ETL)
                properties = {}
                text_to_embed = "" # This will be the rich embedding text
                
                if class_name == "TCM_Reference_Case":
                    # Logic from Ingestion.py: resolve_symptoms logic simplified here (no ontology lookup for enrichment in sync for now)
                    # To keep it simple but compatible, we construct the text structure.
                    symptoms_text = " ".join(item.get('symptom_tags', []))
                    
                    # Aggressive Weighting: Repeat chief_complaint 5 times
                    weighted_chief_complaint = (item.get('chief_complaint') + " ") * 5
                    
                    text_to_embed = (
                        f"主訴: {weighted_chief_complaint}\n"
                        f"關鍵症狀: {symptoms_text}\n" 
                        f"病機分析: {item.get('pathology_analysis')}\n"
                        f"診斷: {item.get('diagnosis_disease')} {item.get('diagnosis_syndrome')}"
                    )
                    
                    # ETL: Map JSON fields to Schema
                    properties = {
                        "case_id": item.get("case_id"),
                        "source_type": item.get("type"), 
                        "chief_complaint": item.get("chief_complaint"),
                        "original_tags": item.get("symptom_tags"), # Mapped to original_tags
                        "diagnosis_main": item.get("diagnosis_disease"),
                        "diagnosis_syndrome": item.get("diagnosis_syndrome"),
                        "treatment_principle": item.get("treatment_principle"),
                        "pathology_analysis": item.get("pathology_analysis"),
                        "confidence_score": item.get("confidence_score"),
                        "embedding_text": text_to_embed # Store the rich text
                    }
                    
                elif class_name == "TCM_Standard_Ontology":
                    # Logic from Ingestion.py
                    enrich_text = f"{item.get('term_name')} ({item.get('category')}): {item.get('definition')} 同義詞:{' '.join(item.get('synonyms', []))}"
                    text_to_embed = enrich_text
                    
                    properties = item
                    properties["embedding_text"] = enrich_text
                    
                elif class_name == "TCM_Diagnostic_Rules":
                    # Logic from Ingestion.py
                    main_text = " ".join(item.get('main_symptoms', []))
                    sec_text = " ".join(item.get('secondary_symptoms', []))
                    
                    text_to_embed = (
                        f"證型: {item.get('syndrome_name')}\n"
                        f"必要主症: {main_text}\n" 
                        f"次要症狀: {sec_text}\n"
                        f"排除條件: {' '.join(item.get('exclusion', []))}"
                    )
                    
                    properties = {
                        "rule_id": item.get("rule_id"),
                        "syndrome_name": item.get("syndrome_name"),
                        "category": item.get("category"),
                        # Note: Ingestion.py doesn't store main/sec symptoms in properties, only in refs or embedding_text.
                        # But we can't easily add refs in sync without ontology lookup.
                        # Storing them in embedding_text is sufficient for the fallback logic.
                        "tongue_pulse": item.get("tongue_pulse"), 
                        "exclusion": item.get("exclusion"),
                        "treatment_principle": item.get("treatment_principle"),
                        "embedding_text": text_to_embed
                    }

                # 呼叫 Embedding API
                vector = await self.nvidia_client.get_embedding(text_to_embed)
                
                # 寫入 Weaviate
                self.weaviate_client.insert_generic(class_name, properties, vector)
                
            except Exception as e:
                logger.error(f"[Sync] Failed to process item in {class_name}: {str(e)}")