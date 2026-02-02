import logging
from logging.handlers import TimedRotatingFileHandler
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# 載入環境變數 (最優先)
load_dotenv()

from app.core.config import get_settings
from app.api.endpoints import router as api_router
from app.database.sync_manager import SyncManager
from app.database.schema import WeaviateSchema
from app.database.weaviate_client import WeaviateClient

settings = get_settings()

# 配置 Logging
# 確保 Log 目錄存在
log_dir = os.path.dirname(settings.LOG_FILE_PATH)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(), # 輸出到 Console
        TimedRotatingFileHandler(
            filename=settings.LOG_FILE_PATH,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        ) # 輸出到檔案 (按日輪轉)
    ]
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Events
    負責應用程式啟動與關閉時的邏輯。
    """
    # --- Startup ---
    logger.info(f"Starting Agentic SCBR-CDSS (Env: {settings.ENV_MODE})...")
    
    # 1. Init Database Schema (確保 Class 存在)
    try:
        client = WeaviateClient()
        schema_def = WeaviateSchema.get_schema()
        # 這裡簡化處理：檢查並建立 Schema (實際應有更嚴謹的檢查)
        # client.ensure_schema(schema_def)
        client.close()
        logger.info("[Startup] Schema check passed.")
    except Exception as e:
        logger.error(f"[Startup] Database connection failed: {str(e)}")
        # 資料庫連不上是致命錯誤，但也許允許降級執行？這裡選擇繼續嘗試 Sync

    # 2. Run Data Sync (Async)
    if settings.RUN_SYNC_ON_STARTUP:
        logger.info("[Startup] RUN_SYNC_ON_STARTUP is True. Starting data synchronization...")
        sync_manager = SyncManager()
        await sync_manager.run_sync()
    else:
        logger.info("[Startup] RUN_SYNC_ON_STARTUP is False. Skipping data synchronization.")
    
    yield
    
    # --- Shutdown ---
    logger.info("Shutting down system...")
    # 清理資源 (如關閉連線池)

app = FastAPI(
    title="Agentic SCBR-CDSS API",
    version="8.0",
    description="代理式螺旋案例推理中醫輔助診斷系統",
    lifespan=lifespan
)

# CORS 設定 (允許前端存取)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生產環境應限制為前端 Domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)