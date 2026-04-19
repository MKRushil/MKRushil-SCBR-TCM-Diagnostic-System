import weaviate
import logging
from typing import Dict, Any, List, Optional
from app.core.config import get_settings
from weaviate.classes.query import Filter, MetadataQuery, QueryReference
import re

logger = logging.getLogger(__name__)
settings = get_settings()

class WeaviateClient:
    """
    規格書 3.2 資料庫 Schema 設計 (BYOV Mode)
    Updated for V2.1 Hierarchical Schema (Reference Resolving)
    Implemented robust reference resolution with fallback to embedding_text parsing.
    [Update V3.0] Support for Metadata Filtering.
    """
    def __init__(self):
        try:
            self.client = weaviate.connect_to_local(
                host=settings.WEAVIATE_URL.replace("http://", "").split(":")[0],
                port=int(settings.WEAVIATE_URL.split(":")[-1]),
            )
            logger.info(f"Connected to Weaviate at {settings.WEAVIATE_URL}")
        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {str(e)}")
            raise e

    def close(self):
        self.client.close()

    def get_all_ids(self, class_name: str) -> set:
        existing_ids = set()
        try:
            collection = self.client.collections.get(class_name)
            for obj in collection.iterator():
                if class_name == "TCM_Reference_Case":
                    if obj.properties.get("case_id"):
                        existing_ids.add(obj.properties["case_id"])
                elif class_name == "TCM_Standard_Ontology":
                    if obj.properties.get("term_id"):
                        existing_ids.add(obj.properties["term_id"])
                elif class_name == "TCM_Diagnostic_Rules":
                    if obj.properties.get("rule_id"):
                        existing_ids.add(obj.properties["rule_id"])
            logger.info(f"[Weaviate] Retrieved {len(existing_ids)} existing IDs for {class_name}.")
        except Exception as e:
            logger.error(f"[Weaviate] Failed to retrieve IDs for {class_name}: {str(e)}")
        return existing_ids

    def _extract_symptoms_from_embedding_text(self, embedding_text: str, section_keyword: str) -> List[str]:
        # Known section headers based on Ingestion.py
        headers = ["證型:", "必要主症:", "次要症狀:", "排除條件:", "主訴:", "關鍵症狀:", "病機分析:", "診斷:"]
        
        start_marker = f"{section_keyword}:"
        start_idx = embedding_text.find(start_marker)
        if start_idx == -1:
            return []
        
        start_idx += len(start_marker)
        
        # Find the end index: the position of the nearest next header
        end_idx = len(embedding_text)
        for h in headers:
            idx = embedding_text.find(h, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx
                
        content = embedding_text[start_idx:end_idx].strip()
        
        if not content:
            return []

        # Split by common delimiters
        symptoms = re.split(r'[，、,\s]+', content)
        
        # Clean up definitions like "(肺氣上逆...)" and remove duplicates
        cleaned_symptoms = []
        seen = set()
        for s in symptoms:
            if not s.strip():
                continue
            # Remove content in parens
            clean_s = re.sub(r'\s*\(.*?\)\s*', '', s).strip()
            if clean_s and clean_s not in seen:
                cleaned_symptoms.append(clean_s)
                seen.add(clean_s)
                
        return cleaned_symptoms

    def _resolve_references(self, obj: Any, case_type: str) -> Dict[str, Any]:
        props = obj.properties
        embedding_text = props.get("embedding_text", "")

        if case_type == "case":
            ref_names = {
                "hasPrimarySymptoms": "關鍵症狀",
                "hasSecondarySymptoms": "次要症狀"
            }
        elif case_type == "rule":
            ref_names = {
                "hasMainSymptoms": "必要主症",
                "hasSecondarySymptoms": "次要症狀"
            }
        else:
            return props

        for ref_prop_name, keyword in ref_names.items():
            resolved_names = []
            if hasattr(obj.references, ref_prop_name) and getattr(obj.references, ref_prop_name):
                ref_objects = getattr(obj.references, ref_prop_name)
                for ref_obj in ref_objects.objects:
                    if 'term_name' in ref_obj.properties:
                        resolved_names.append(ref_obj.properties['term_name'])
            
            # Fallback to embedding_text if references are empty
            if not resolved_names and embedding_text:
                resolved_names = self._extract_symptoms_from_embedding_text(embedding_text, keyword)

            props[ref_prop_name] = resolved_names
                
        return props

    def search_similar_cases(self, vector: List[float], query_text: str = None, limit: int = 5, where_filter: Optional[Filter] = None) -> List[Dict[str, Any]]:
        """
        Path A: 檢索相似案例 (Hybrid Search with alpha=0.5)
        [V3.1] Switched to Hybrid Search for better keyword matching.
        """
        try:
            collection = self.client.collections.get("TCM_Reference_Case")
            
            if query_text:
                # Hybrid Search (Vector + Keyword)
                response = collection.query.hybrid(
                    query=query_text,
                    vector=vector,
                    alpha=0.5, # Balance between keyword (0) and vector (1)
                    limit=limit,
                    filters=where_filter,
                    return_metadata=MetadataQuery(score=True, distance=True), # Hybrid returns score
                    return_references=[
                        QueryReference(
                            link_on="hasPrimarySymptoms",
                            return_properties=["term_name"]
                        ),
                        QueryReference(
                            link_on="hasSecondarySymptoms",
                            return_properties=["term_name"]
                        )
                    ]
                )
            else:
                # Fallback to pure Vector Search if no text provided
                response = collection.query.near_vector(
                    near_vector=vector,
                    limit=limit,
                    filters=where_filter,
                    return_metadata=MetadataQuery(distance=True),
                    return_references=[
                        QueryReference(
                            link_on="hasPrimarySymptoms",
                            return_properties=["term_name"]
                        ),
                        QueryReference(
                            link_on="hasSecondarySymptoms",
                            return_properties=["term_name"]
                        )
                    ]
                )
            
            results = []
            for obj in response.objects:
                props = self._resolve_references(obj, "case")
                # Hybrid score is not cosine distance, but we map it to 'similarity' for compatibility
                similarity = obj.metadata.score if query_text else (1 - obj.metadata.distance)
                results.append({
                    **props,
                    "similarity": similarity,
                    "id": str(obj.uuid)
                })
            return results
            
        except Exception as e:
            logger.error(f"[Weaviate] Search cases failed: {str(e)}")
            return []

    def search_diagnostic_rules(self, vector: List[float], query_text: str = None, limit: int = 5, where_filter: Optional[Filter] = None) -> List[Dict[str, Any]]:
        """
        Path B: 檢索診斷規則 (Hybrid Search)
        """
        try:
            collection = self.client.collections.get("TCM_Diagnostic_Rules")
            
            if query_text:
                response = collection.query.hybrid(
                    query=query_text,
                    vector=vector,
                    alpha=0.5,
                    limit=limit,
                    filters=where_filter,
                    return_metadata=MetadataQuery(score=True, distance=True),
                    return_references=[
                        QueryReference(
                            link_on="hasMainSymptoms",
                            return_properties=["term_name"]
                        ),
                        QueryReference(
                            link_on="hasSecondarySymptoms",
                            return_properties=["term_name"]
                        )
                    ]
                )
            else:
                response = collection.query.near_vector(
                    near_vector=vector,
                    limit=limit,
                    filters=where_filter,
                    return_metadata=MetadataQuery(distance=True),
                    return_references=[
                        QueryReference(
                            link_on="hasMainSymptoms",
                            return_properties=["term_name"]
                        ),
                        QueryReference(
                            link_on="hasSecondarySymptoms",
                            return_properties=["term_name"]
                        )
                    ]
                )
            
            results = []
            for obj in response.objects:
                props = self._resolve_references(obj, "rule")
                similarity = obj.metadata.score if query_text else (1 - obj.metadata.distance)
                results.append({
                    **props,
                    "similarity": similarity,
                    "id": str(obj.uuid)
                })
            return results
            
        except Exception as e:
            logger.error(f"[Weaviate] Search rules failed: {str(e)}")
            return []

    def insert_generic(self, class_name: str, properties: Dict[str, Any], vector: List[float]):
        try:
            collection = self.client.collections.get(class_name)
            collection.data.insert(properties=properties, vector=vector)
        except Exception as e:
            logger.error(f"Insert generic failed: {e}")

    def get_session_history(self, patient_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        try:
            collection = self.client.collections.get("TCM_Session_Memory")
            response = collection.query.fetch_objects(
                filters=Filter.by_property("patient_id").equal(patient_id),
                limit=limit
            )
            results = []
            for obj in response.objects:
                results.append(obj.properties)
            return results
        except Exception as e:
            logger.error(f"[Weaviate] Get session history failed: {str(e)}")
            return []

    def add_session_memory(self, memory_data: Dict[str, Any]):
        try:
            collection = self.client.collections.get("TCM_Session_Memory")
            collection.data.insert(properties=memory_data)
            logger.info(f"[Weaviate] Added session memory for {memory_data.get('session_id')}")
        except Exception as e:
            logger.error(f"[Weaviate] Add session memory failed: {str(e)}")
            raise e
