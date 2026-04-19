import requests
import json
from typing import List, Set, Tuple

def calculate_accuracy(predicted: str, expected: str) -> float:
    """
    計算診斷準確率 (Exact Match or Partial Match)
    這裡使用簡單的字串包含檢查
    """
    if not predicted or not expected:
        return 0.0
    
    predicted = predicted.strip()
    expected = expected.strip()
    
    if predicted == expected:
        return 1.0
    
    # Partial match: 如果預測包含預期，或預期包含預測 (例如 "感冒" vs "風寒感冒")
    if expected in predicted or predicted in expected:
        return 0.8 # 給予部分分數
        
    return 0.0

def _llm_check_match(prompt: str, api_key: str) -> bool:
    """Helper for LLM API call"""
    if not api_key: return False
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1, "max_tokens": 5
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip().lower()
            return "yes" in content
    except:
        pass
    return False

def calculate_semantic_match_llm(predicted: str, expected: str, api_key: str) -> float:
    """LLM-as-a-Judge Semantic Accuracy"""
    if not predicted or not expected: return 0.0
    if not api_key: return calculate_accuracy(predicted, expected)

    prompt = f"""
    你是中醫診斷評估專家。
    請判斷以下兩個診斷結果在臨床意義上是否相符或高度相關：
    專家標準診斷: "{expected}"
    系統預測診斷: "{predicted}"
    規則：
    1. 若兩者指同一病症 (如: 不寐=失眠)，視為相符。
    2. 若預測診斷包含標準診斷 (如: 風寒感冒 包含 感冒)，視為相符。
    3. 若預測診斷更具體且正確 (如: 脾胃虛寒胃痛 vs 胃痛)，視為相符。
    4. 若兩者明顯不同 (如: 胃痛 vs 頭痛)，視為不符。
    請只回答 "Yes" 或 "No"。
    """
    return 1.0 if _llm_check_match(prompt, api_key) else 0.0

def calculate_semantic_recall_precision_llm(candidates: List[str], expected: str, api_key: str) -> Tuple[float, float]:
    """
    計算語意 Recall (GT 是否在候選中) 與 Precision (候選中相關的比例)
    Returns: (Recall, Precision)
    """
    if not candidates or not expected: return 0.0, 0.0
    if not api_key: return (1.0 if any(expected in c for c in candidates) else 0.0, 0.0) # Fallback

    # Batch check efficiency is tricky with simple prompt, iterating top-k (usually small, e.g., 3)
    relevant_count = 0
    hit_expected = False
    
    for cand in candidates:
        match_score = calculate_semantic_match_llm(cand, expected, api_key)
        if match_score > 0.5:
            relevant_count += 1
            hit_expected = True
            
    recall = 1.0 if hit_expected else 0.0
    precision = relevant_count / len(candidates) if candidates else 0.0
    
    return recall, precision

def calculate_f1_score(precision: float, recall: float) -> float:
    """Standard F1 Score"""
    if precision + recall == 0: return 0.0
    return 2 * (precision * recall) / (precision + recall)

def calculate_symptom_recall(retrieved_symptoms: List[str], expected_symptoms: List[str]) -> float:
    """
    計算症狀召回率 (Recall)
    Recall = (正確檢索到的症狀數) / (預期總症狀數)
    """
    if not expected_symptoms:
        return 1.0 # 如果沒有預期症狀，算滿分
    
    if not retrieved_symptoms:
        return 0.0
        
    # 簡單的集合比對 (需注意同義詞，這裡暫時假設完全匹配)
    retrieved_set = set(retrieved_symptoms)
    expected_set = set(expected_symptoms)
    
    # 計算交集
    # 為了增加容錯，可以加入模糊比對，這裡先做精確比對
    match_count = 0
    for exp in expected_set:
        for ret in retrieved_set:
            if exp in ret or ret in exp: # 簡單的子字串匹配
                match_count += 1
                break
    
    return match_count / len(expected_set)

def calculate_latency_score(latency_ms: float, threshold_ms: float = 2000.0) -> float:
    """
    計算延遲分數 (回應時間是否達標)
    """
    if latency_ms <= threshold_ms:
        return 1.0
    else:
        # 超過越多分數越低，最低 0
        score = 1.0 - ((latency_ms - threshold_ms) / threshold_ms)
        return max(0.0, score)