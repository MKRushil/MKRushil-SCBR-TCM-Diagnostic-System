import hashlib
import logging
from typing import List, Dict
from app.core.config import get_settings
from app.database.weaviate_client import WeaviateClient

logger = logging.getLogger(__name__)
settings = get_settings()

class PatientManager:
    """
    規格書 5.1 & 3.2: 病患身分與歷史管理
    """
    
    def __init__(self):
        self.salt = settings.PATIENT_ID_SALT

    def get_hashed_id(self, raw_id: str) -> str:
        """
        LLM02: PII 遮罩 - 生成 Hash ID
        """
        try:
            if not raw_id:
                return "anonymous"
            combined = f"{raw_id}{self.salt}".encode('utf-8')
            hashed = hashlib.sha256(combined).hexdigest()
            # 取前 16 碼即可，兼顧長度與衝突機率
            return hashed[:16]
        except Exception as e:
            logger.error(f"[PatientManager] Hashing failed: {str(e)}")
            raise ValueError("ID Processing Error")

    def get_patient_history(self, patient_id_hash: str) -> List[Dict]:
        """
        從 Weaviate (Class: TCM_Session_Memory) 撈取歷史對話
        """
        client = None
        try:
            client = WeaviateClient()
            history = client.get_session_history(patient_id_hash)
            logger.info(f"[PatientManager] Retrieved {len(history)} records for {patient_id_hash}")
            return history
        except Exception as e:
            logger.error(f"[PatientManager] Failed to fetch history: {str(e)}")
            return []
        finally:
            if client:
                client.close()
        
    def save_session_turn(self, patient_id_hash: str, session_id: str, content: str, diagnosis_summary: str):
        """
        將當前回合寫入 DB (螺旋記憶)
        """
        # TODO: 實作 Weaviate 寫入邏輯
        pass