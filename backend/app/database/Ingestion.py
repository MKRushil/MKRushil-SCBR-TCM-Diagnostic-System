import asyncio
import json
import logging
import os
import sys
from typing import List, Dict, Any
from weaviate.util import generate_uuid5
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ingestion")

current_dir = os.path.dirname(os.path.abspath(__file__))
# Load .env
env_path = os.path.join(current_dir, "..", "..", ".env")
if os.path.exists(env_path):
    logger.info(f"Loading .env from {env_path}")
    load_dotenv(env_path)

# Add backend to sys.path
grand_parent_dir = os.path.dirname(os.path.dirname(current_dir))
if grand_parent_dir not in sys.path:
    sys.path.append(grand_parent_dir)

try:
    from app.database.weaviate_client import WeaviateClient
    from app.services.nvidia_client import NvidiaClient
except ImportError as e:
    logger.error(f"Failed to import app modules: {e}")
    sys.exit(1)

# DISEASE_CATEGORY_MAP: Mapping from disease name to category
DISEASE_CATEGORY_MAP = {
    "感冒": "肺系", "咳嗽": "肺系", "哮病": "肺系", "喘證": "肺系", "肺癰": "肺系", "肺脹": "肺系", "肺癆": "肺系",
    "心悸": "心系", "胸痺": "心系", "不寐": "心系",
    "胃痛": "脾胃", "痞滿": "脾胃", "嘔吐": "脾胃", "噎膈": "脾胃", "呃逆": "脾胃", "腹痛": "脾胃", "泄瀉": "脾胃", "便秘": "脾胃",
    "脅痛": "肝膽", "黃疸": "肝膽", "積聚": "肝膽", "鼓脹": "肝膽",
    "水腫": "腎系", "淋證": "腎系", "癃閉": "腎系", "陽痿": "腎系", "遺精": "腎系",
    "鬱證": "氣血津液", "血證": "氣血津液", "痰飲": "氣血津液", "消渴": "氣血津液", "內傷發熱": "氣血津液", "虛勞": "氣血津液",
    "頭痛": "肢體經絡", "眩暈": "肢體經絡", "中風": "肢體經絡", "痺證": "肢體經絡", "痿證": "肢體經絡", "腰痛": "肢體經絡",
    "癮疹": "肢體經絡", # 或皮膚，暫歸此類以對應filter_config
    "遺尿": "腎系"
}

class IngestionManager:
    def __init__(self):
        self.weaviate = WeaviateClient()
        self.nvidia = NvidiaClient()
        self.data_dir = os.path.join(grand_parent_dir, "data")
        
        # Cache for term UUIDs to build references
        self.term_uuid_map = {}
        self.term_def_map = {}

    def load_json(self, filename: str) -> List[Dict]:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def get_embedding(self, text: str) -> List[float]:
        try:
            # [V3.1 Fix] Use 'passage' input type for ingestion to align with E5 model requirements
            return await self.nvidia.get_embedding(text, input_type="passage")
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []

    async def ingest_ontology(self):
        filename = "tcm_ontology.json"
        data = self.load_json(filename)
        if not data: return

        logger.info(f"Ingesting {len(data)} ontology terms...")
        collection = self.weaviate.client.collections.get("TCM_Standard_Ontology")
        
        # Batch insert
        with collection.batch.dynamic() as batch:
            for term in data:
                term_id = term['term_id']
                term_name = term['term_name']
                definition = term['definition']
                synonyms = term.get('synonyms', [])
                
                # Enrich text for embedding
                enrich_text = f"{term_name} ({term['category']}): {definition} 同義詞:{' '.join(synonyms)}"
                
                # Generate deterministic UUID
                uuid = generate_uuid5(term_id)
                
                # Cache for later use (Reference linking)
                self.term_uuid_map[term_name] = uuid
                self.term_def_map[term_name] = definition
                for syn in synonyms:
                    self.term_uuid_map[syn] = uuid
                    self.term_def_map[syn] = definition

                # Generate vector
                vector = await self.get_embedding(enrich_text)
                
                batch.add_object(
                    properties={
                        "term_id": term_id,
                        "term_name": term_name,
                        "category": term['category'],
                        "definition": definition,
                        "synonyms": synonyms,
                        "embedding_text": enrich_text
                    },
                    uuid=uuid,
                    vector=vector
                )
        
        if collection.batch.failed_objects:
             logger.error(f"Ontology batch errors: {collection.batch.failed_objects}")
        else:
             logger.info("Ontology ingestion complete.")

    def resolve_symptoms(self, tags: List[str], weight_multiplier: int = 1):
        """
        Resolve symptom tags to UUIDs (for references) and enriched text.
        """
        uuids = []
        enriched_texts = []
        
        for tag in tags:
            if tag in self.term_uuid_map:
                # Found in ontology
                uuids.append(self.term_uuid_map[tag])
                
                definition = self.term_def_map.get(tag, "")
                desc = f"{tag}({definition})"
                # Weighting by repetition
                repeated_text = " ".join([desc] * weight_multiplier)
                enriched_texts.append(repeated_text)
            else:
                # Not found, keep as text
                enriched_texts.append(tag)
        
        return uuids, " ".join(enriched_texts)

    async def ingest_cases(self):
        filename = "tcm_expert_cases.json"
        data = self.load_json(filename)
        if not data: return

        logger.info(f"Ingesting {len(data)} cases...")
        collection = self.weaviate.client.collections.get("TCM_Reference_Case")

        with collection.batch.dynamic() as batch:
            for case in data:
                case_id = case['case_id']
                symptoms = case.get('symptom_tags', [])
                
                # Resolve references and text
                # Increase weight multiplier for symptoms to 3 (Aggressive Weighting)
                prim_uuids, prim_text = self.resolve_symptoms(symptoms, weight_multiplier=3)
                
                # Infer Category from Disease Name using Map
                diagnosis_disease = case.get('diagnosis_disease', '')
                category = DISEASE_CATEGORY_MAP.get(diagnosis_disease, "其他") # Default to "其他" if not found

                # Construct super embedding text with Aggressive Weighting
                # Repeat chief_complaint 5 times to dominate the vector direction
                weighted_chief_complaint = (case['chief_complaint'] + " ") * 5
                
                embedding_text = (
                    f"主訴: {weighted_chief_complaint}\n"
                    f"關鍵症狀: {prim_text}\n" 
                    f"病機分析: {case['pathology_analysis']}\n"
                    f"診斷: {case['diagnosis_disease']} {case['diagnosis_syndrome']}"
                )

                vector = await self.get_embedding(embedding_text)
                
                batch.add_object(
                    properties={
                        "case_id": case_id,
                        "source_type": case.get('type', 'SEEDED'),
                        "chief_complaint": case['chief_complaint'],
                        "original_tags": symptoms,
                        "diagnosis_main": case['diagnosis_disease'],
                        "diagnosis_syndrome": case['diagnosis_syndrome'],
                        "treatment_principle": case['treatment_principle'],
                        "pathology_analysis": case['pathology_analysis'],
                        "confidence_score": case.get('confidence_score', 1.0),
                        "category": category, # [V3.0] Added category for whitelist filtering
                        "embedding_text": embedding_text
                    },
                    # Add references
                    references={
                        "hasPrimarySymptoms": prim_uuids
                    },
                    vector=vector
                )

        if collection.batch.failed_objects:
             logger.error(f"Case batch errors: {collection.batch.failed_objects}")
        else:
             logger.info("Case ingestion complete.")

    async def ingest_rules(self):
        filename = "tcm_diagnostic_rules.json"
        data = self.load_json(filename)
        if not data: return

        logger.info(f"Ingesting {len(data)} rules...")
        collection = self.weaviate.client.collections.get("TCM_Diagnostic_Rules")

        with collection.batch.dynamic() as batch:
            for rule in data:
                # Resolve references
                # Increase weight multiplier for main symptoms to 4
                main_uuids, main_text = self.resolve_symptoms(rule.get('main_symptoms', []), weight_multiplier=4)
                sec_uuids, sec_text = self.resolve_symptoms(rule.get('secondary_symptoms', []), weight_multiplier=1)

                embedding_text = (
                    f"證型: {rule['syndrome_name']}\n"
                    f"必要主症: {main_text}\n" 
                    f"次要症狀: {sec_text}\n"
                    f"排除條件: {' '.join(rule.get('exclusion', []))}"
                )

                vector = await self.get_embedding(embedding_text)
                
                batch.add_object(
                    properties={
                        "rule_id": rule['rule_id'],
                        "syndrome_name": rule['syndrome_name'],
                        "category": rule['category'], # Already exists in rules
                        "tongue_pulse": rule.get('tongue_pulse', []),
                        "exclusion": rule.get('exclusion', []),
                        "treatment_principle": rule.get('treatment_principle', ""),
                        "embedding_text": embedding_text
                    },
                    references={
                        "hasMainSymptoms": main_uuids,
                        "hasSecondarySymptoms": sec_uuids
                    },
                    vector=vector
                )

        if collection.batch.failed_objects:
             logger.error(f"Rules batch errors: {collection.batch.failed_objects}")
        else:
             logger.info("Rules ingestion complete.")

    async def run(self):
        logger.info("Starting ingestion process...")
        
        # 1. Ontology first (to build cache for references)
        await self.ingest_ontology()
        
        # 2. Cases (depend on Ontology)
        await self.ingest_cases()
        
        # 3. Rules (depend on Ontology)
        await self.ingest_rules()
        
        logger.info("All ingestion tasks finished.")
        self.weaviate.close()

if __name__ == "__main__":
    manager = IngestionManager()
    asyncio.run(manager.run())