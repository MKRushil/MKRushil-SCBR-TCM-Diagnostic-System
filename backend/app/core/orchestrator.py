# backend/app/core/orchestrator.py

import asyncio
import logging
import json
import os
from collections import Counter
from typing import Dict, Any, List, Optional
from uuid import uuid4
from datetime import datetime

from app.core.config import settings
from app.api.schemas import WorkflowState, PathSelected, UnifiedResponse, ResponseType
from app.services.nvidia_client import NvidiaClient
from app.database.weaviate_client import WeaviateClient
from app.api.schemas import DiagnosisItem, FollowUpQuestion
from app.agents.reasoning import ReasoningAgent
from app.agents.summarizer import SummarizerAgent
from app.agents.memory import MemoryAgent
from app.agents.translator import TranslatorAgent
from app.services.visualization import VisualizationAdapter
from app.evaluation.monitor import monitor
from app.guardrails.input_guard import InputGuard
from app.guardrails.output_guard import OutputGuard
from app.services.reranker import Reranker # [V3.0+] Import Reranker
from app.services.analysis_module import AnalysisModule # [V3.1+] Import AnalysisModule
from app.core.pss import (  # [V3.1+] PSS Module
    ProvisionalSyndromeState,
    determine_stage,
    build_pss,
    build_fallback_pss,
    is_anchor_valid,
    DiagnosisStage
)

logger = logging.getLogger(__name__)

class Orchestrator:
    """
    SCBR V3.0 Orchestrator
    核心調度器：執行 [感知 -> 混合檢索 -> 分析 -> 推理] 的單一管線。
    [Update V3.0+] Implemented Re-Ranking & Soft Prior.
    [Update V3.1+] Added Analysis Module (8-Principles).
    """
    
    def __init__(self):
        self._global_lock = asyncio.Lock()
        self.nvidia_client = NvidiaClient() # NvidiaClient now loads settings internally
        # 强制更新 nvidia_client 的 embed_model, 确保使用最新的环境变量
        # 即使 settings 可能被缓存，这里的 os.getenv() 也会拿到最新的值
        if os.getenv("EMBEDDING_MODEL_NAME"):
            self.nvidia_client.embed_model = os.getenv("EMBEDDING_MODEL_NAME")
        self.weaviate_client = WeaviateClient()
        self.reranker = Reranker() # [V3.0+] Initialize Reranker
        
        # === Legacy Agents (for backward compatibility) ===
        self.reasoning_agent = ReasoningAgent(self.nvidia_client, self.weaviate_client)
        self.memory_agent = MemoryAgent(self.nvidia_client)
        self.summarizer_agent = SummarizerAgent(self.nvidia_client)
        self.translator_agent = TranslatorAgent(self.nvidia_client, self.weaviate_client)
        
        # === V3.1 New Agents: 8-Agent Architecture ===
        # Import here to avoid circular dependency issues
        from app.agents.safety import InputSafetyAgent
        from app.agents.perception import SymptomExtractor, FeatureValidator, QueryBuilder
        from app.agents.diagnosis import DiagnosisAgent
        from app.agents.critic import CriticAgent
        
        self.safety_agent = InputSafetyAgent(self.nvidia_client)
        self.extractor = SymptomExtractor(self.nvidia_client)
        self.validator = FeatureValidator(self.nvidia_client)
        self.builder = QueryBuilder(self.nvidia_client)
        self.diagnosis_agent = DiagnosisAgent(self.nvidia_client)
        self.critic_agent = CriticAgent(self.nvidia_client)
        # memory_agent and summarizer_agent are already initialized above (reuse)
        
        logger.info("[Orchestrator] V3.1 架構：8 個 Agent 已初始化")
        logger.info(f"[Orchestrator] Embedding Model Loaded: {self.nvidia_client.embed_model}")
        
        self._session_histories: Dict[str, Dict[str, Any]] = {}
        
        # [V3.1] Load 8-Principles Mapping & Initialize AnalysisModule
        self.syndrome_8p_map = {}
        try:
            # Assuming running from backend root or project root. Try project root first.
            data_path = "backend/data/tcm_diagnostic_rules.json"
            if not os.path.exists(data_path):
                data_path = "data/tcm_diagnostic_rules.json" # If running from backend/
            
            if os.path.exists(data_path):
                with open(data_path, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                    for r in rules:
                        if "syndrome_name" in r and "eight_principles" in r:
                            self.syndrome_8p_map[r["syndrome_name"]] = r["eight_principles"]
                logger.info(f"[Orchestrator] 已載入 {len(self.syndrome_8p_map)} 條八綱映射規則")
            else:
                logger.warning(f"[Orchestrator] 找不到規則檔: {data_path}，八綱統計功能將無法使用")
        except Exception as e:
            logger.error(f"[Orchestrator] 載入八綱規則失敗: {e}")
            
        self.analysis_module = AnalysisModule(self.syndrome_8p_map)

    async def process_session(self, request: Any, background_tasks: Any = None) -> UnifiedResponse:
        """
        Entry point for session processing.
        Feature Flag: Use USE_V31_PIPELINE=true in .env to enable V3.1 architecture.
        """
        # Feature Flag: V3.1 Pipeline
        use_v31 = os.getenv('USE_V31_PIPELINE', 'false').lower() == 'true'
        
        if use_v31:
            logger.info("[Orchestrator] Feature Flag: 使用 V3.1 Pipeline")
            return await self.process_session_v31(request, background_tasks)
        else:
            logger.info("[Orchestrator] Feature Flag: 使用 V3.0 Pipeline (舊版)")
            return await self.process_session_v30(request, background_tasks)
    
    async def process_session_v30(self, request: Any, background_tasks: Any = None) -> UnifiedResponse:
        """
        V3.0 舊版流程（向下相容）
        """
        session_id = request.session_id
        patient_id = request.patient_id
        
        logger.info(f"[Orchestrator] 收到請求 (Session: {session_id})，開始執行 SCBR 診斷流程...")
        
        try:
            user_input_current_turn = InputGuard.validate(request.message)
        except ValueError as ve:
            logger.warning(f"🔴 [Orchestrator] 輸入防護攔截: {ve}")
            raise ve

        session_data = self._session_histories.setdefault(session_id, {"messages": [], "summary": {}, "previous_diagnosis_candidates": []})
        session_history = session_data["messages"]
        current_summary = session_data["summary"]
        previous_diagnosis_candidates = session_data["previous_diagnosis_candidates"]
        
        session_history.append({"role": "user", "content": user_input_current_turn})

        full_conversation_context = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in session_history])

        state = WorkflowState(
            session_id=session_id,
            patient_id=patient_id,
            user_input_raw=full_conversation_context,
            diagnosis_summary=current_summary,
            previous_diagnosis_candidates=previous_diagnosis_candidates
        )

        async with self._global_lock:
            try:
                # --- Step 1: Perception (Translation & Weighted Query & Primary Location) ---
                logger.info(f"🔍 [Orchestrator] 進入感知層 (Translator): 正在標準化輸入並推斷病位...")
                state = await self.translator_agent.run(state)
                logger.info(f"✅ [Orchestrator] 感知完成。核心病位: {state.primary_location}, 風險等級: {state.standardized_features.get('risk_level')}")
                
                if state.standardized_features.get("is_emergency"):
                    warning_msg = state.standardized_features.get("emergency_warning", "偵測到危急重症徵兆，請立即就醫！")
                    logger.warning(f"[Orchestrator] 急症熔斷觸發！內容: {warning_msg}")
                    return UnifiedResponse(
                        response_type=ResponseType.INQUIRY_ONLY,
                        diagnosis_list=[],
                        evidence_trace="系統攔截：偵測到危急重症關鍵字。",
                        safety_warning=warning_msg,
                        formatted_report=f"### 緊急警示\n\n系統偵測到危急徵兆：**{warning_msg}**"
                    )

                # [Safety Check - High Risk / Blocked]
                risk_level = state.standardized_features.get("risk_level", "LOW")
                if risk_level in ["BLOCKED", "HIGH"]:
                    refusal_msg = "系統判定輸入內容包含潛在風險或無法處理，請重新輸入。"
                    logger.warning(f"[Orchestrator] 風險攔截觸發！等級: {risk_level}")
                    return UnifiedResponse(
                        response_type=ResponseType.FALLBACK,
                        diagnosis_list=[],
                        evidence_trace="系統攔截：輸入內容風險過高或無效。",
                        safety_warning=refusal_msg,
                        formatted_report=f"### 系統攔截\n\n{refusal_msg}"
                    )

                # --- Step 2: Integrated Retrieval with Re-Ranking (Logic-Aware Hybrid RAG) ---
                query_text = state.weighted_query_string or state.user_input_raw
                logger.info(f"[Orchestrator] 啟動混合檢索: 正在為加權查詢生成向量...")
                query_vector = await self.nvidia_client.get_embedding(query_text)

                
                # [Baseline-Combined] 跳過檢索 (Pure Context -> Diagnosis)
                if current_baseline_mode == "simple_rag":
                    logger.info("[Baseline: Simple RAG] 跳過向量檢索 (Direct Input -> Diagnosis)")
                    state.retrieved_context = [] # 空上下文
                    ranked_cases = []
                else:
                    # [V3.0+] Strategic Shift: Broad Retrieval + Cross-Encoder Re-Ranking + Soft Prior
                    # 1. Broad Retrieval (Top-20, No Hard Filter)
                    broad_limit = 20 # Always retrieve a broad set for reranking
                    logger.info(f"[Orchestrator] Weaviate 廣度搜尋: 檢索 Top-{broad_limit} 候選案例...")
                    raw_cases_weaviate = self.weaviate_client.search_similar_cases(
                        vector=query_vector, 
                        query_text=query_text,
                        limit=broad_limit
                    )
                    
                    # Convert Weaviate objects to plain dictionaries for serialization and reranking
                    # The WeaviateClient already returns dictionaries, so direct assignment
                    raw_cases = raw_cases_weaviate
    
                    
                    # 2. Re-Ranking (Top-20 -> Top-5)
                    if settings.ENABLE_RERANK and self.reranker.model: # Check if reranker is enabled and model loaded
                        logger.info(f"[Orchestrator] 執行 Re-Ranking: 應用 Soft Prior (病位: {state.primary_location}) 進行重排序...")
                        # Apply Soft Prior using state.primary_location
                        ranked_cases = self.reranker.rerank(
                            query=query_text,
                            documents=raw_cases,
                            primary_location=state.primary_location,
                            top_k=settings.CASE_TOPK
                        )
                    else:
                        # Fallback to original order if reranker is disabled or model not loaded
                        ranked_cases = raw_cases[:settings.CASE_TOPK]
    
                    logger.debug(f"[Orchestrator] Ranked cases count (after re-ranking): {len(ranked_cases)}")
    
                    state.retrieved_context = ranked_cases
                    logger.debug(f"[Orchestrator] Retrieved Context (after rerank): {state.retrieved_context}")
                
                # 3. Retrieve Rules (Keep Broad, Re-rank if needed, but Top-3 usually fine)
                broad_rule_limit = 10 
                logger.info(f"[Orchestrator] 檢索診斷規則 (Top-{broad_rule_limit})...")
                raw_rules_weaviate = self.weaviate_client.search_diagnostic_rules(
                    vector=query_vector, 
                    query_text=query_text,
                    limit=broad_rule_limit
                )
                # The WeaviateClient already returns dictionaries, so direct assignment
                raw_rules = raw_rules_weaviate

                if settings.ENABLE_RERANK and self.reranker.model:
                    ranked_rules = self.reranker.rerank(
                        query=query_text,
                        documents=raw_rules,
                        primary_location=state.primary_location, # Soft Prior applies here too if rules have category
                        top_k=settings.RULE_TOPK
                    )
                else:
                    ranked_rules = raw_rules[:settings.RULE_TOPK]
                
                # --- Step 3: War Room Analysis (Distribution Pool) ---
                distribution_pool = self._build_distribution_pool(ranked_cases)
                state.distribution_pool = distribution_pool 
                
                logger.info(f"[Orchestrator] 戰情室分析: 眾數={distribution_pool['mode_diagnosis']}, 離群值嫌疑={distribution_pool['is_outlier_suspect']}")

                # Generate Visualization Data
                viz_data = VisualizationAdapter.process(state)

                # --- Step 4: Reasoning (Cluster-CBR) ---
                state.retrieved_rules = ranked_rules
                logger.info(f"[Orchestrator] 進入推理層 (Reasoning): 啟動 Cluster-CBR 決策與修補...")
                state = await self.reasoning_agent.run(state)
                
                if state.final_response:
                    state.final_response.visualization_data = viz_data
                    
                    # [V3.0/V2.1 Metrics Support] Populate debug/eval fields
                    state.final_response.retrieved_context = state.retrieved_context
                    state.final_response.standardized_features = state.standardized_features
                    state.final_response.risk_level = state.standardized_features.get('risk_level')
                
                assistant_response_content = "..."
                if state.final_response.follow_up_question and state.final_response.follow_up_question.question_text:
                    assistant_response_content = state.final_response.follow_up_question.question_text
                elif state.final_response.diagnosis_list:
                    assistant_response_content = f"主要考慮為：{state.final_response.diagnosis_list[0].disease_name}"
                
                session_history.append({"role": "assistant", "content": assistant_response_content})

                if background_tasks:
                     background_tasks.add_task(self.trigger_async_summarization, state)

                monitor.log_detailed_metrics(state)
                
                if state.final_response:
                    state.final_response = OutputGuard.validate_response(state.final_response)
                
                if state.final_response and state.final_response.diagnosis_list:
                    self._session_histories[session_id]["previous_diagnosis_candidates"] = state.final_response.diagnosis_list

                logger.info(f"🏁 [Orchestrator] 流程結束。 সন")
                return state.final_response

            except Exception as e:
                logger.error(f"[Orchestrator] 流程發生錯誤: {e}")
                raise e

    async def trigger_async_summarization(self, state: WorkflowState):
        try:
            new_state = await self.summarizer_agent.run(state)
            if state.session_id in self._session_histories:
                self._session_histories[state.session_id]["summary"] = new_state.diagnosis_summary
        except Exception as e:
            logger.error(f"[Orchestrator] Background summarization failed: {str(e)}")

    async def process_feedback(self, request: Any):
        pass

    # ==================== V3.1.1 Helper Functions (Phase 1) ====================
    
    def _split_session_history(self, session_history: List[Dict]) -> Dict:
        """
        分離 user 和 assistant turns (Phase 1A)
        
        Args:
            session_history: 完整的對話歷史
            
        Returns:
            Dict containing:
                - user_context_text: 只含 user turns 的文本（用於 Perception）
                - assistant_prior: 從 assistant 提取的 prior（用於 soft prior）
                - user_turns_count: user turns 數量
                - assistant_turns_count: assistant turns 數量
        """
        user_turns = [msg for msg in session_history if msg.get('role') == 'user']
        assistant_turns = [msg for msg in session_history if msg.get('role') == 'assistant']
        
        # 建立 user_context_text（只含 user 訊息）
        user_context_text = "\n".join([f"患者: {msg['content']}" for msg in user_turns])
        
        # 提取 assistant prior（從結構化欄位）
        assistant_prior = self._extract_prior_from_assistant(assistant_turns)
        
        logger.info(f"[Orchestrator] Session History 分離: user_turns={len(user_turns)}, assistant_turns={len(assistant_turns)}")
        
        return {
            "user_context_text": user_context_text,
            "assistant_prior": assistant_prior,
            "user_turns_count": len(user_turns),
            "assistant_turns_count": len(assistant_turns)
        }
    
    def _extract_prior_from_assistant(self, assistant_turns: List[Dict]) -> Dict:
        """
        從 assistant 的結構化輸出提取 prior (Phase 1A)
        
        注意：不使用文字解析，而是從 session_data["last_diagnosis"] 讀取
        這個方法主要用於向下相容，實際 prior 應從 session_data 直接讀取
        
        Args:
            assistant_turns: assistant 的對話歷史
            
        Returns:
            Dict containing prior_syndrome and prior_confidence
        """
        if not assistant_turns:
            return {"prior_syndrome": None, "prior_confidence": 0.0}
        
        # 從 metadata 提取（如果有保存）
        last_turn = assistant_turns[-1]
        if 'metadata' in last_turn:
            return {
                "prior_syndrome": last_turn['metadata'].get('provisional_syndrome'),
                "prior_confidence": last_turn['metadata'].get('confidence', 0.0),
                "diagnosis_stage": last_turn['metadata'].get('diagnosis_stage', 'hypothesis')
            }
        
        # Fallback: 返回空 prior
        return {"prior_syndrome": None, "prior_confidence": 0.0}

    # ==================== V3.1 New Pipeline ====================
    
    async def process_session_v31(self, request: Any, background_tasks: Any = None) -> UnifiedResponse:
        """
        V3.1 四步驟螺旋流程 (4-Step Spiral Process)
        整合 8 個 Agent 的完整診斷流程
        """
        session_id = request.session_id
        patient_id = request.patient_id
        
        # [V3.1] Dynamic Configuration Override (Test Mode)
        # 允許測試腳本透過 API 參數覆蓋 settings.BASELINE_MODE
        # 優先級: Request > Settings
        current_baseline_mode = settings.BASELINE_MODE
        if hasattr(request, 'test_mode_flags') and request.test_mode_flags:
            if "BASELINE_MODE" in request.test_mode_flags:
                current_baseline_mode = request.test_mode_flags["BASELINE_MODE"]
                logger.info(f"[Orchestrator] 測試模式覆蓋生效: BASELINE_MODE -> {current_baseline_mode}")
        
        # 1. [輸入]
        logger.info(f"[輸入] [Orchestrator] 接收到原始訊息 (Session: {session_id}): \"{request.message[:50]}...\"")
        
        # 2. [安全防護]
        logger.info("[安全防護] [InputSafetyAgent] 正在檢查輸入安全性...")
        safety_result = await self.safety_agent.run(request.message)
        await asyncio.sleep(1.5) # 加入延遲 (確保符合 40 rpm 速率限制)
        
        if not safety_result.is_safe:
            logger.warning(f"[安全防護] [InputSafetyAgent] 檢查結果: FAIL (風險等級: {safety_result.risk_level}, 原因: {safety_result.block_reason})")
            return self._build_block_response(safety_result)
        
        if safety_result.is_emergency_trigger:
            logger.warning(f"[安全防護] [InputSafetyAgent] 檢查結果: EMERGENCY (急症熔斷: {safety_result.emergency_message})")
            return self._build_emergency_response(safety_result.emergency_message)
        
        logger.info("[安全防護] [InputSafetyAgent] 檢查結果: PASS")
        
        user_input_sanitized = safety_result.sanitized_input
        
        # Session History Management
        # [實驗組別控制: Baseline-Combined 簡單上下文模式]
        if current_baseline_mode == "simple_rag":
            # [Baseline-Combined] 簡單上下文 - 保留「問題+前一輸出」
            logger.info("[Baseline: Simple RAG] 簡單上下文模式 - 保留問題+前一輸出")
            session_data = self._session_histories.setdefault(
                session_id, 
                {
                    "messages": [],  # 會累積簡單的問題+輸出
                    "summary": {},
                    "previous_diagnosis_candidates": [],
                    "sticky_chief_complaint": None
                }
            )
            session_history = session_data["messages"]
            current_summary = session_data["summary"]
            previous_diagnosis_candidates = session_data["previous_diagnosis_candidates"]
            
            session_history.append({"role": "user", "content": user_input_sanitized})
        else:
            # [SCBR-Standard] 正常累積歷史
            session_data = self._session_histories.setdefault(
                session_id, 
                {
                    "messages": [], 
                    "summary": {}, 
                    "previous_diagnosis_candidates": [],
                    "sticky_chief_complaint": None,  # [V3.1] Persist chief complaint
                    "cumulative_features": {},       # [V3.1.1] 累積特徵池 (session-scoped)
                    "last_diagnosis": {}             # [V3.1.1] 上次診斷結果 (用於 prior)
                }
            )
            session_history = session_data["messages"]
            current_summary = session_data["summary"]
            previous_diagnosis_candidates = session_data["previous_diagnosis_candidates"]
            
            session_history.append({"role": "user", "content": user_input_sanitized})
        
        # Initialize WorkflowState
        state = WorkflowState(
            session_id=session_id,
            patient_id=patient_id,
            user_input_raw=user_input_sanitized,
            diagnosis_summary=current_summary,
            previous_diagnosis_candidates=previous_diagnosis_candidates,
            safety_result=safety_result.__dict__ if hasattr(safety_result, '__dict__') else {}
        )
        
        async with self._global_lock:
            try:
                # [實驗組別控制: Baseline-Combined 跳過感知層]
                # [實驗組別控制: Simple RAG 跳過感知層]
                if current_baseline_mode == "simple_rag":
                    logger.info("[Baseline: Simple RAG] 跳過感知層 (Extractor/Validator/QueryBuilder)，直接使用原始輸入")
                    # 直接使用 user_input，不做任何特徵提取、累積、過濾
                    state.raw_symptoms_extracted = {}
                    state.validated_features = {
                        'validated_features': {},
                        'conflicts': [],
                        'missing_keys': []
                    }
                    state.weighted_query_string = user_input_sanitized  # 直接用原始輸入
                    state.primary_location = None
                    logger.info(f"[Baseline: Simple RAG] Query: '{user_input_sanitized[:50]}...'")
                else:
                    # [SCBR-Standard 模式] - 完整感知層處理
                    # 3. [問題分析與加權] - 症狀提取
                    logger.info("[問題分析與加權] [Orchestrator] 啟動症狀提取...")
                    
                    # [V3.1.1 Phase 1] 分離 user/assistant turns
                    split_history = self._split_session_history(session_history)
                    user_context_text = split_history["user_context_text"]
                    
                    # [V3.1.1 Phase 1] 載入累積特徵池和 prior
                    cumulative_features = session_data.get("cumulative_features", {})
                    
                    # [V3.1.1 Phase 1] 從 session_data 讀取 prior（優先於 assistant_turns）
                    if session_data.get("last_diagnosis"):
                        assistant_prior = {
                            "prior_syndrome": session_data["last_diagnosis"].get("syndrome"),
                            "prior_confidence": session_data["last_diagnosis"].get("confidence", 0.0),
                            "diagnosis_stage": session_data["last_diagnosis"].get("stage", "hypothesis")
                        }
                    else:
                        assistant_prior = split_history["assistant_prior"]
                    
                    logger.info(f"[Orchestrator] 累積池載入: {len(cumulative_features.get('symptoms', []))} 症狀, Prior: {assistant_prior.get('prior_syndrome', 'None')}")
                    
                    # 調用 SymptomExtractor（傳入 user_context_text 和 cumulative_features）
                    state.raw_symptoms_extracted = await self.extractor.run(
                        user_input_sanitized,
                        user_context_only=user_context_text,
                        cumulative_features=cumulative_features
                    )
                    await asyncio.sleep(1.5) # 加入延遲 (確保符合 40 rpm 速率限制)

                    # 4. [問題分析與加權] - 特徵驗證
                    patient_profile = {"gender": "未知", "age": "未知"}  # TODO: 從患者檔案讀取
                    state.validated_features = await self.validator.run(
                        state.raw_symptoms_extracted,
                        session_history,
                        patient_profile,
                        cumulative_features=cumulative_features,  # [V3.1.1 Phase 1] 傳入累積池
                        assistant_prior=assistant_prior           # [V3.1.1 Phase 1] 傳入 prior
                    )
                    await asyncio.sleep(1.5) # 加入延遲 (確保符合 40 rpm 速率限制)
                
                    # [V3.1] Sticky Chief Complaint Logic
                    # [實驗組別控制: Baseline-Combined 跳過主訴繼承]
                    if current_baseline_mode != "simple_rag":
                        features_dict = state.validated_features.get('validated_features', {})
                        current_cc = features_dict.get('chief_complaint')
                    
                        if current_cc and current_cc.strip():
                            session_data["sticky_chief_complaint"] = current_cc
                        elif session_data.get("sticky_chief_complaint"):
                            features_dict['chief_complaint'] = session_data["sticky_chief_complaint"]
                            state.validated_features['validated_features'] = features_dict
                            logger.info(f"[問題分析與加權] [Orchestrator] 主訴繼承: '{session_data['sticky_chief_complaint']}'  (本輪未提供主訴)")
                
                    # 5. [問題分析與加權] - 查詢構建
                    query_result = await self.builder.run(
                        state.validated_features,
                        assistant_prior=assistant_prior  # [V3.1.1 Phase 2E] 傳入 prior
                    )
                    await asyncio.sleep(1.5) # 加入延遲 (確保符合 40 rpm 速率限制)
                    state.weighted_query_string = query_result.get('weighted_query_string', '')
                    state.primary_location = query_result.get('primary_location')
                
                    # 更新 standardized_features（向下相容）
                    state.standardized_features = state.validated_features.get('validated_features', {})
                
                    if state.primary_location:
                        logger.info(f"[問題分析與加權] [Orchestrator] 分析完成。核心病位: {state.primary_location}")
                    else:
                        logger.warning("[問題分析與加權] [Orchestrator] 分析完成。核心病位: 未知")
                
                # 6. [Step 1: 找尋最相關案例] - 檢索與重排序
                logger.info("[Step 1: 找尋最相關案例] [Orchestrator] 啟動混合檢索與重排序...")
                
                query_text = state.weighted_query_string or user_input_sanitized
                
                # [實驗組別控制: Pure LLM]
                if current_baseline_mode == "pure_llm":
                    logger.info("[Baseline: Pure LLM] 跳過向量檢索與規則獲取")
                    ranked_cases = []
                    ranked_rules = []
                    query_vector = []
                # [實驗組別控制: Simple RAG - Baseline-Combined]
                elif current_baseline_mode == "simple_rag":
                    logger.info("[Baseline: Simple RAG] 極簡檢索模式 - 僅取 Top-1，無重排序，無案例池分析")
                    query_vector = await self.nvidia_client.get_embedding(query_text)
                    
                    # 直接檢索 Top-1 案例
                    raw_cases = self.weaviate_client.search_similar_cases(
                        vector=query_vector, 
                        query_text=query_text,
                        limit=1  # 僅取 Top-1
                    )
                    ranked_cases = raw_cases  # 不進行重排序
                    ranked_rules = []  # 不檢索規則
                    
                    logger.info(f"[Baseline: Simple RAG] 檢索完成，取得 Top-1 案例: {ranked_cases[0].get('diagnosis_main', 'Unknown') if ranked_cases else 'None'}")
                else:
                    # [SCBR-Standard 模式]
                    query_vector = await self.nvidia_client.get_embedding(query_text)
                    
                    # 廣度檢索 Top-20
                    broad_limit = 20
                    raw_cases = self.weaviate_client.search_similar_cases(
                        vector=query_vector, 
                        query_text=query_text, # [V3.1] Pass text for Hybrid Search
                        limit=broad_limit
                    )
                    
                    logger.info(f"[Step 1: 找尋最相關案例] [WeaviateService] 初步檢索完成，候選案例數: {len(raw_cases)}")
                    
                    # Re-Ranking
                    if settings.ENABLE_RERANK and self.reranker.model:
                        ranked_cases = self.reranker.rerank(
                            query=query_text,
                            documents=raw_cases,
                            primary_location=state.primary_location,
                            top_k=settings.CASE_TOPK
                        )
                    else:
                        ranked_cases = raw_cases[:settings.CASE_TOPK]
                
                    # 檢索規則
                    broad_rule_limit = 10
                    raw_rules = self.weaviate_client.search_diagnostic_rules(
                        vector=query_vector, 
                        query_text=query_text, 
                        limit=broad_rule_limit
                    )
                    if settings.ENABLE_RERANK and self.reranker.model:
                        ranked_rules = self.reranker.rerank(
                            query=query_text,
                            documents=raw_rules,
                            primary_location=state.primary_location,
                            top_k=settings.RULE_TOPK
                        )
                    else:
                        ranked_rules = raw_rules[:settings.RULE_TOPK]
                
                state.retrieved_rules = ranked_rules
                state.retrieved_context = ranked_cases
                state.anchor_case = ranked_cases[0] if ranked_cases else None
                state.reference_pool = ranked_cases  # 用於降級
                
                if ranked_cases:
                    top1_case_name = ranked_cases[0].get('diagnosis_main', 'Unknown')
                    logger.info(f"[Step 1: 找尋最相關案例] [RerankerService] 重排序完成，鎖定 Top-{len(ranked_cases)} 案例 (Top-1: {top1_case_name})")
                elif current_baseline_mode != "pure_llm":
                    logger.warning("[Step 1: 找尋最相關案例] [RerankerService] 重排序後無可用案例")
                
                # 8. [Step 2: 協商與修補] - 戰情分析
                # [實驗組別控制: Simple RAG 跳過案例池分析]
                if current_baseline_mode == "simple_rag":
                    logger.info("[Baseline: Simple RAG] 跳過案例池分析 (WarRoom)，直接使用 Top-1 案例")
                    state.analysis_result = {
                        'mode_diagnosis': ranked_cases[0].get('diagnosis_main', 'Unknown') if ranked_cases else 'N/A',
                        'is_outlier_suspect': False,
                        'eight_principles_tendency': {},
                        'eight_principles_stats': {}
                    }
                else:
                    state.analysis_result = self.analysis_module.analyze(ranked_cases)
                    mode_diag = state.analysis_result.get('mode_diagnosis', 'N/A')
                    is_outlier = state.analysis_result.get('is_outlier_suspect', False)
                    eight_p_stats = state.analysis_result.get('eight_principles_stats', {})
                    # Format 8P stats for log: "寒:0.5, 熱:0.2"
                    eight_p_log = ", ".join([f"{k}:{v:.1f}" for k,v in eight_p_stats.items()]) if eight_p_stats else "無數據"
                    
                    logger.info(f"[Step 2: 協商與修補] [WarRoomAnalyzer] 全局分析: 眾數診斷='{mode_diag}', 離群值風險={is_outlier}")
                    logger.info(f"[Step 2: 協商與修補] [WarRoomAnalyzer] 八綱傾向: {eight_p_log}")
                
                # 可視化
                viz_data = VisualizationAdapter.process(state)
                
                # === Step 3: Validation Loop (Diagnosis + Critic + Downgrade) ===
                # 進入迴圈，首先是 Diagnosis (流程 9)，屬於 [Step 2: 協商與修補]
                logger.info("[Step 2: 協商與修補] [Orchestrator] 啟動螺旋協商迴圈 (Diagnosis <-> Critic)...")
                
                if not state.anchor_case and current_baseline_mode != "pure_llm":
                    logger.error("[Step 2: 協商與修補] [Orchestrator] 錯誤: 無可用 Anchor Case，直接降級為 FALLBACK")
                    return self._build_fallback_response(state)
                
                if current_baseline_mode in ["pure_llm", "single_turn"]:
                    max_retries = 1
                    logger.info(f"[Baseline: {current_baseline_mode}] 強制單次生成，不啟用 Critic 評判")
                # === Step 3: 適配與驗證 (Validation Loop) ===
                logger.info("[Step 3: 適配與驗證] [Orchestrator] 進入 Actor-Critic 協商迴圈...")
                
                # [V3.1] 限制降級次數 - 只允許 Top-1 → Top-2
                max_retries = 2  # [V3.1] 限制降級次數 - 只允許 Top-1 → Top-2
                final_draft = None
                final_critique = {}
                failed_attempts = [] # Track failures for feedback loop
                
                for attempt in range(max_retries):
                    anchor_name = state.anchor_case.get('diagnosis_main', 'Unknown')
                    logger.info(f"[Step 2: 協商與修補] [Orchestrator] 第 {attempt + 1}/{max_retries} 次嘗試 (使用 Anchor: '{anchor_name}')...")
                    
                    draft_diagnosis = await self.diagnosis_agent.run(
                        user_features=state,
                        anchor_case=state.anchor_case,
                        analysis_result=state.analysis_result,
                        retrieved_rules=state.retrieved_rules,
                        baseline_mode=current_baseline_mode # [V3.1] Explicitly pass mode
                    )
                    await asyncio.sleep(1.5) # 加入延遲 (確保符合 40 rpm 速率限制)
                    
                    # 3.2 評判審核 (流程 10) - 進入 [Step 3: 適配與驗證]
                    # [實驗組別控制: 跳過 Critic]
                    if current_baseline_mode in ["pure_llm", "single_turn", "simple_rag"]:
                        from app.agents.critic import CriticResult, CriticDecision
                        # [Baseline Correction] Use actual confidence from diagnosis, do not fix at 0.7
                        # DiagnosisAgent returns 'confidence_level' or 'confidence' in the result dict
                        start_confidence = 0.5
                        if draft_diagnosis:
                            # Try multiple keys
                            val = draft_diagnosis.get('confidence_level') or draft_diagnosis.get('confidence')
                            if val is not None:
                                try:
                                    start_confidence = float(val)
                                except:
                                    pass
                        
                        critic_result = CriticResult(
                            decision=CriticDecision.PASS,
                            confidence_score=start_confidence, # Use dynamic confidence
                            critique="[Baseline Mode] 跳過專家評判，使用診斷原始信心度。",
                            correction_suggestion=None,
                            check_results={}
                        )
                    else:
                        critic_result = await self.critic_agent.run(
                            draft_diagnosis=draft_diagnosis,
                            user_features=state,
                            analysis_result=state.analysis_result
                        )
                        await asyncio.sleep(1.5) # 加入延遲 (確保符合 40 rpm 速率限制)
                    
                    # 保存結果
                    state.draft_diagnosis = draft_diagnosis
                    state.critique_result = {
                        "decision": critic_result.decision.value,
                        "confidence_score": critic_result.confidence_score,
                        "critique": critic_result.critique,
                        "check_results": critic_result.check_results
                    }
                    final_critique = state.critique_result # Update final_critique in every iteration
                    
                    # 3.3 判斷是否通過
                    from app.agents.critic import CriticDecision
                    if critic_result.decision == CriticDecision.PASS:
                        logger.info(f"[Step 3: 適配與驗證] [Orchestrator] 審核通過 (PASS)! 信心分數: {critic_result.confidence_score:.2f}")
                        final_draft = draft_diagnosis
                        # 如果之前有失敗，記錄這次的修正
                        if failed_attempts:
                            self._log_critic_feedback(session_id, failed_attempts, final_draft)
                        break
                    else:
                        # 記錄失敗嘗試
                        failed_attempts.append({
                            "draft": draft_diagnosis,
                            "critique": state.critique_result
                        })
                        
                        # 降級機制
                        rejection_reason = critic_result.correction_suggestion or "未提供原因"
                        logger.warning(f"[Step 3: 適配與驗證] [Orchestrator] 審核未通過 ({critic_result.decision.value})。原因: {rejection_reason[:100]}...")
                        
                        if attempt + 1 < len(state.reference_pool):
                            next_case = state.reference_pool[attempt + 1]
                            next_case_name = next_case.get('diagnosis_main', 'Unknown')
                            state.anchor_case = next_case
                            logger.info(f"[Step 3: 適配與驗證] [Orchestrator] 觸發降級機制 -> 切換至 Top-{attempt+2} 案例 ('{next_case_name}')")
                        else:
                            logger.error("[Step 3: 適配與驗證] [Orchestrator] 所有候選案例均被駁回，停止協商")
                            break
                
                # === Step 4: 決定與保存 (Decision & Memory) ===
                logger.info("[Step 4: 決定與保存] [Orchestrator] 進入最終決策階段...")
                
                # If no draft passed, use the last one as fallback
                if final_draft is None:
                    final_draft = state.draft_diagnosis if hasattr(state, 'draft_diagnosis') else {}
                
                # 4.1 決定回應類型 (流程 11)
                # [V3.1] Critic-ResponseType 一致性規則:
                # - critic_pass=True 時禁止 FALLBACK
                # - ResponseType 決策依賴 critic_decision + stage + retries
                confidence = final_critique.get('confidence_score', 0.5)
                critic_decision = final_critique.get('decision', 'PASS')
                diagnosis_stage = final_draft.get('diagnosis_stage', 'hypothesis') if final_draft else 'hypothesis'
                
                # 使用 PSS 模組的 determine_stage 如果有完整 features
                if hasattr(state, 'validated_features') and state.validated_features:
                    features = state.validated_features.get('standardized_features', {})
                    if features:
                        diagnosis_stage = determine_stage(features)
                
                # Critic-ResponseType 一致性邏輯
                if critic_decision == 'PASS':
                    # critic_pass=True 時禁止 FALLBACK
                    if diagnosis_stage == 'finalize' and confidence >= 0.65:
                        response_type = ResponseType.DEFINITIVE
                    else:
                        response_type = ResponseType.INQUIRY_ONLY  # 暫定假說，繼續追問
                elif critic_decision in ['WARNING', 'RETRY']:
                    response_type = ResponseType.INQUIRY_ONLY
                else:  # FAIL
                    # 僅當 Critic 明確 FAIL 且所有重試耗盡時才 FALLBACK
                    if attempt >= max_retries - 1:  # 最後一次嘗試
                        response_type = ResponseType.FALLBACK
                    else:
                        response_type = ResponseType.INQUIRY_ONLY
                
                logger.info(f"[Step 4: 決定與保存] [Orchestrator] 最終判定回應類型: {response_type.value} (最終信心: {confidence:.2f})")

                # 4.2 構建最終回應
                # 如果 final_draft 仍為 None (所有嘗試都失敗)，則傳入一個空字典
                final_draft_for_response = final_draft if final_draft is not None else {}
                
                # [V3.1] 提取生理矛盾警告
                bio_check = state.validated_features.get('biological_check', {})
                bio_warning = None
                if bio_check.get('issues'):
                    issues_str = "、".join(bio_check['issues'])
                    bio_warning = f"提示：偵測到症狀與生理特徵不符（{issues_str}），系統依據「症狀優先」原則進行分析。"

                state.final_response = self._build_unified_response(
                    draft_diagnosis=final_draft_for_response,
                    critique_result=final_critique,
                    response_type=response_type,
                    visualization_data=viz_data,
                    biological_warning=bio_warning
                )
                
                # Populate debug fields
                state.final_response.retrieved_context = state.retrieved_context
                state.final_response.standardized_features = state.standardized_features
                state.final_response.risk_level = "SAFE"  # 已通過安全檢查
                
                # 4.3 記錄到 Session History
                assistant_response_content = state.final_response.diagnosis_list[0].disease_name if state.final_response.diagnosis_list else "診斷完成"
                session_history.append({"role": "assistant", "content": assistant_response_content})
                
                # 4.4 觸發背景摘要
                if background_tasks:
                    # 每 3 輪對話 (User+Assistant=2 msg) 觸發一次，即 msg count % 6 == 0
                    current_turn_count = len(session_history) // 2
                    if len(session_history) > 0 and current_turn_count % 3 == 0:
                        logger.info(f"[Step 4: 決定與保存] [Orchestrator] 觸發週期性摘要更新 (SummarizerAgent) - 第 {current_turn_count} 輪")
                        background_tasks.add_task(self.trigger_async_summarization, state)
                
                # 4.5 監控與驗證
                monitor.log_detailed_metrics(state)
                state.final_response = OutputGuard.validate_response(state.final_response)
                
                # 4.6 保存診斷候選
                if state.final_response.diagnosis_list:
                    self._session_histories[session_id]["previous_diagnosis_candidates"] = state.final_response.diagnosis_list
                
                # [V3.1.1 Phase 1C] 回寫累積池（每輪結束時）
                if state.validated_features:
                    session_data["cumulative_features"] = state.validated_features.get('validated_features', {})
                    logger.info(f"[Orchestrator] 累積池已更新: {len(session_data['cumulative_features'].get('symptoms', []))} 症狀")
                
                # [V3.1.1 Phase 1C] 回寫診斷結果（用於下輪 prior）
                if state.final_response.diagnosis_list:
                    first_diagnosis = state.final_response.diagnosis_list[0]
                    session_data["last_diagnosis"] = {
                        "syndrome": first_diagnosis.disease_name,
                        "confidence": first_diagnosis.confidence,
                        "stage": response_type.value if response_type else "hypothesis",
                        "timestamp": __import__('datetime').datetime.now().isoformat()
                    }
                    logger.info(f"[Orchestrator] Prior 已更新: {session_data['last_diagnosis']['syndrome']} (confidence={session_data['last_diagnosis']['confidence']:.2f})")
                
                logger.info("[Orchestrator] Pipeline finished successfully")
                return state.final_response
                
            except Exception as e:
                logger.error(f"🔴 [Orchestrator V3.1] 流程發生錯誤: {e}")
                raise e


    # ==================== V3.1 Helper Functions ====================
    
    def _build_unified_response(
        self,
        draft_diagnosis: Dict[str, Any],
        critique_result: Dict[str, Any],
        response_type: ResponseType,
        visualization_data: Dict = None,
        biological_warning: str = None
    ) -> UnifiedResponse:
        """
        整合 DiagnosisAgent 的草稿與 CriticAgent 的審核結果
        Layout Reference: 11.md
        """
        # 確保 draft_diagnosis 和 critique_result 至少為空字典
        draft_diagnosis = draft_diagnosis if draft_diagnosis is not None else {}
        critique_result = critique_result if critique_result is not None else {}
        
        # 1. 診斷建議 (Diagnosis Suggestion)
        disease_name = draft_diagnosis.get('disease_name', '分析中...')
        confidence = critique_result.get('confidence_score', 0.0)
        
        # Determine Confidence Level & Status
        if confidence >= 0.8:
            conf_level = "高"
            status = "已確診 (Final)"
        elif confidence >= 0.6:
            conf_level = "中"
            status = "可修正 (Non-final)"
        else:
            conf_level = "低"
            status = "資料不足 (Insufficient)"

        # Condition field used for "Confidence Info" display
        condition_text = f"信心層級：{conf_level} | 判斷狀態：{status}"
        
        diagnosis_list = [
            DiagnosisItem(
                rank=1,
                disease_name=disease_name,
                confidence=confidence,
                condition=condition_text 
            )
        ] if disease_name != '分析中...' else []
        
        # 2. 推導路徑 (Evidence Trace)
        # Extract reasoning parts
        raw_reasoning = draft_diagnosis.get('reasoning_path', '尚無推導資料')
        critic_feedback = critique_result.get('critique', '尚無審核意見')
        
        # Construct the structured trace as per 11.md
        evidence_trace = f"""
### 【當前辯證狀態摘要】
*   **主要證候方向**：{disease_name}
*   **支持證據**：請參閱對話歷史與症狀提取結果
*   **系統推導邏輯**：
    {raw_reasoning}

### 【專家評判與修正】
{critic_feedback}
"""

        # 3. 診斷報告 (Diagnosis Report)
        pathogenesis = draft_diagnosis.get('pathogenesis', '分析中...')
        treatment_principle = draft_diagnosis.get('treatment_principle', '分析中...')
        
        formatted_report_content = f"""
### 證候方向
{disease_name}

### 病機分析
{pathogenesis}

### 治療原則
{treatment_principle}
"""
        
        # 4. Question & Warnings
        follow_up_data = draft_diagnosis.get('follow_up_question')
        follow_up_question = None
        if follow_up_data and follow_up_data.get('required'):
            follow_up_question = FollowUpQuestion(
                required=True,
                question_text=follow_up_data.get('question_text', ''),
                options=follow_up_data.get('options', [])
            )

        final_warning = critique_result.get('safety_warning')
        if biological_warning:
            if final_warning:
                final_warning = f"{final_warning}\n\n{biological_warning}"
            else:
                final_warning = biological_warning
        
        return UnifiedResponse(
            response_type=response_type,
            diagnosis_list=diagnosis_list,
            follow_up_question=follow_up_question,
            evidence_trace=evidence_trace,
            formatted_report=formatted_report_content,
            safety_warning=final_warning,
            visualization_data=visualization_data
        )
    
    def _build_fallback_response(self, state: WorkflowState) -> UnifiedResponse:
        """
        當所有案例被駁回或流程中斷時的保底回應
        """
        last_critique = state.critique_result if hasattr(state, 'critique_result') else {}
        last_draft = state.draft_diagnosis if hasattr(state, 'draft_diagnosis') else {}
        
        evidence_trace_content = last_draft.get('reasoning_path', '無推導過程。')
        critique_content = last_critique.get('critique', '無評判意見。')
        
        evidence_trace = f"""
### 🧠 診斷推導路徑 (最近一次失敗)
{evidence_trace_content}

### ⚖️ 專家評判意見 (最近一次失敗)
{critique_content}
"""
        
        return UnifiedResponse(
            response_type=ResponseType.FALLBACK,
            diagnosis_list=[],
            follow_up_question=FollowUpQuestion(
                required=True,
                question_text="系統目前無法給出明確診斷，能否提供更多資訊？如：舌象、脈象、病程時間等。",
                options=[]
            ),
            evidence_trace=evidence_trace,
            formatted_report="### 無法確診\n\n請補充更多資訊以協助診斷。",
            safety_warning=last_critique.get('safety_warning') # 如果有安全警告，也回傳
        )
    
    def _build_block_response(self, safety_result) -> UnifiedResponse:
        """
        輸入被攔截時的回應
        """
        from app.agents.safety import RiskLevel
        
        if safety_result.risk_level == RiskLevel.MALICIOUS:
            message = "系統判定輸入內容包含潛在風險，請重新輸入。"
        else:
            message = "輸入內容無效，請提供有效的醫療諮詢問題。"
        
        return UnifiedResponse(
            response_type=ResponseType.FALLBACK,
            diagnosis_list=[],
            evidence_trace="系統攔截：輸入內容風險過高或無效。",
            safety_warning=message,
            formatted_report=f"### 🛑 系統攔截\n\n{message}"
        )
    
    def _build_emergency_response(self, emergency_message: str) -> UnifiedResponse:
        """
        急症熔斷時的回應
        """
        return UnifiedResponse(
            response_type=ResponseType.INQUIRY_ONLY,
            diagnosis_list=[],
            evidence_trace="系統攔截：偵測到危急重症徵兆。",
            safety_warning=emergency_message,
            formatted_report=f"### ⚠️ 緊急警示\n\n{emergency_message}\n\n**請立即就醫，不要延誤！**"
        )

    def _log_critic_feedback(self, session_id: str, failed_attempts: List[Dict], successful_diagnosis: Dict):
        """
        [V3.1] 記錄 Critic 的自我修正路徑 (Self-Correction Log)
        當系統經歷了 RETRY/FAIL 但最終找到更好的答案時，記錄這個過程作為「錯題本」。
        """
        if not failed_attempts or not successful_diagnosis:
            return

        feedback_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "failed_attempts": [
                {
                    "diagnosis": f.get("draft", {}).get("disease_name"),
                    "critic_decision": f.get("critique", {}).get("decision"),
                    "correction_suggestion": f.get("critique", {}).get("correction_suggestion")
                }
                for f in failed_attempts
            ],
            "successful_diagnosis": successful_diagnosis.get("disease_name"),
            "learning_point": "Critic 成功引導系統修正了診斷方向"
        }
        
        try:
            log_path = "backend/data/feedback_log.json"
            if not os.path.exists("backend/data"):
                os.makedirs("backend/data", exist_ok=True)
                
            # Append to file (load, append, save)
            # 為了效能，這裡簡單用 append mode 寫入 jsonl 格式 (每一行一個 json)
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(feedback_entry, ensure_ascii=False) + "\n")
                
            logger.info(f"[Step 4: 決定與保存] [Orchestrator] 已記錄 Critic 自我修正案例 ({len(failed_attempts)} failures -> Success)")
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to log feedback: {e}")

orchestrator = Orchestrator()
