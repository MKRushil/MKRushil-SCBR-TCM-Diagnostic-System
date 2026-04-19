from sentence_transformers import CrossEncoder
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class Reranker:
    """
    SCBR V3.0+ Re-Ranking Service
    Uses Cross-Encoder to refine retrieval results from Weaviate.
    Implements Soft Prior logic for body system weighting.
    """
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        try:
            self.model = CrossEncoder(model_name)
            logger.info(f"[Reranker] 模型載入成功: {model_name}")
        except Exception as e:
            logger.error(f"[Reranker] 模型載入失敗: {e}")
            self.model = None

    def rerank(self, query: str, documents: List[Dict[str, Any]], primary_location: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Rerank a list of documents based on query relevance using Cross-Encoder.
        Apply Soft Prior boost if primary_location matches document category.
        """
        if not self.model or not documents:
            return documents[:top_k]

        # Prepare pairs for Cross-Encoder
        pairs = []
        for doc in documents:
            content = doc.get('embedding_text') or f"{doc.get('chief_complaint', '')} {doc.get('diagnosis_main', '')}"
            pairs.append([query, content])

        try:
            # Predict scores
            scores = self.model.predict(pairs)

            # Apply Soft Prior Boost
            BOOST_SCORE = 0.3
            
            scored_results = []
            boost_count = 0
            
            for doc, score in zip(documents, scores):
                final_score = float(score)
                
                # Soft Prior Logic
                doc_category = doc.get('category')
                is_boosted = False
                if primary_location and doc_category and primary_location in doc_category: 
                    # simple substring match, e.g. "肺系" in "肺系病"
                    final_score += BOOST_SCORE
                    is_boosted = True
                    boost_count += 1
                
                # Store scores for debugging
                doc['rerank_score'] = final_score
                doc['cross_encoder_score'] = float(score)
                doc['is_boosted'] = is_boosted
                
                scored_results.append(doc)

            # Sort by final score descending
            scored_results.sort(key=lambda x: x['rerank_score'], reverse=True)
            
            top_results = scored_results[:top_k]
            
            # Log summary
            top_scores = [f"{d.get('diagnosis_main')}({d['rerank_score']:.2f}{'[Boost]' if d['is_boosted'] else ''})" for d in top_results]
            logger.debug(f"[Reranker] 重排序完成 (Boosted: {boost_count}/{len(documents)}). Top-{top_k}: {top_scores}")
            
            return top_results

        except Exception as e:
            logger.error(f"[Reranker] 重排序執行失敗: {e}")
            return documents[:top_k] # Fallback to original order