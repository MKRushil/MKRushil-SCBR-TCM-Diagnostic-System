import weaviate
import numpy as np
from ingest import mock_get_embedding # 引用 ingest 的向量函數

class SpiralEngine:
    def __init__(self, client: weaviate.Client):
        self.client = client
        # Session State (會話狀態)
        self.slices_history = []     # 歷史切片 (User Inputs)
        self.confirmed_vectors = []  # 正向特徵向量 (User Feedback +)
        self.rejected_vectors = []   # 負向特徵向量 (User Feedback -)

    def add_slice(self, text_slice):
        """步驟 1: 接收新的切片輸入"""
        print(f"\n[Engine] 接收切片: '{text_slice}'")
        self.slices_history.append(text_slice)

    def add_feedback(self, concept_text, is_positive=True):
        """步驟 2: 接收使用者回饋 (用於推動向量)"""
        # 這裡應該去 Ontology 查該概念的精確向量，此處簡化為重新生成
        vec = mock_get_embedding(concept_text)
        if is_positive:
            print(f"[Engine] 正向鎖定: {concept_text}")
            self.confirmed_vectors.append(vec)
        else:
            print(f"[Engine] 負向排除: {concept_text}")
            self.rejected_vectors.append(vec)

    def _calculate_rocchio_vector(self, current_text):
        """
        [核心算法] Rocchio Algorithm
        Q_new = alpha * Q_orig + beta * Avg(Pos) - gamma * Avg(Neg)
        """
        # 取得當前輸入的原始向量
        q_vec = np.array(mock_get_embedding(current_text))
        
        # 參數設定 (可調整)
        alpha = 1.0  # 當前查詢權重
        beta = 0.8   # 正向歷史權重
        gamma = 0.5  # 排除條件權重

        # 計算平均向量
        pos_vec = np.mean(self.confirmed_vectors, axis=0) if self.confirmed_vectors else np.zeros_like(q_vec)
        neg_vec = np.mean(self.rejected_vectors, axis=0) if self.rejected_vectors else np.zeros_like(q_vec)

        # 向量加減 (螺旋移動)
        new_vec = (alpha * q_vec) + (beta * pos_vec) - (gamma * neg_vec)
        return new_vec.tolist()

    def search(self):
        """步驟 3: 執行螺旋檢索"""
        # A. 聚合歷史上下文
        context_text = " ".join(self.slices_history)
        
        # B. 計算動態向量
        spiral_vector = self._calculate_rocchio_vector(context_text)
        
        # C. 執行 Hybrid Search (混合 關鍵字 + 向量)
        print(f"[Engine] 正在執行螺旋檢索... (Context len: {len(context_text)})")
        
        response = (
            self.client.query
            .get("TCM_Reference_Case", [
                "case_id",
                "diagnosis_disease", 
                "diagnosis_syndrome", 
                "treatment_principle",
                # 透過層次化關聯取出症狀名稱，用於顯示
                "hasPrimarySymptoms {... on TCM_Standard_Ontology { term_name }}"
            ])
            .with_hybrid(
                query=context_text, 
                vector=spiral_vector, 
                alpha=0.5 # 0.5 表示關鍵字與向量同等重要
            )
            .with_limit(3)
            .do()
        )
        
        return response.get('data', {}).get('Get', {}).get('TCM_Reference_Case', [])