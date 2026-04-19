from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from app.api.schemas import ChatRequest, UnifiedResponse, FeedbackRequest, PatientRequest, PatientResponse
from app.core.orchestrator import Orchestrator
from app.services.patient_manager import PatientManager
from app.evaluation.monitor import monitor
import logging
import time

router = APIRouter()
logger = logging.getLogger(__name__)

# 取得單例 Orchestrator
orchestrator = Orchestrator()
patient_manager = PatientManager()

@router.post("/patient", response_model=PatientResponse)
async def patient_endpoint(request: PatientRequest):
    """
    規格書 5.1: 病患身分識別與歷史調閱
    """
    logger.info(f"[API] Processing patient ID request")
    
    try:
        # 1. Generate Hash ID
        hashed_id = patient_manager.get_hashed_id(request.raw_id)
        
        # 2. Fetch History
        history = patient_manager.get_patient_history(hashed_id)
        
        return PatientResponse(
            hashed_id=hashed_id,
            history_summary=history
        )
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"[API] Patient processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/chat", response_model=UnifiedResponse)
async def chat_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    核心對話接口
    觸發 Orchestrator 的序列化管線。
    """
    logger.info(f"[API] Received chat request for Session: {request.session_id}")
    start_time = time.time()
    
    try:
        # 調用 Orchestrator，傳入 background_tasks 用於 Summarization
        response = await orchestrator.process_session(request, background_tasks)
        
        # Log Latency
        monitor.log_latency(request.session_id, "/chat", start_time)
        
        return response
    
    except ValueError as ve:
        # 輸入防禦攔截到的錯誤 (如 Injection)
        logger.warning(f"[API] Input validation failed: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
        
    except Exception as e:
        logger.error(f"[API] Internal Server Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="系統內部錯誤，請稍後再試。"
        )

@router.post("/feedback")
async def feedback_endpoint(request: FeedbackRequest):
    """
    規格書 7.3 學習閉環
    """
    logger.info(f"[API] Feedback received: {request.action} for Session: {request.session_id}")
    
    try:
        await orchestrator.process_feedback(request)
        
        # Log Feedback Metric
        monitor.log_feedback_score(request.session_id, request.action)
        
        return {"status": "success", "message": "Feedback processed"}
        
    except Exception as e:
        logger.error(f"[API] Feedback processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Feedback processing failed")

@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "v8.0"}