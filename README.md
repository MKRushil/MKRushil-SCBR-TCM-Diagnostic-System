
# TCM-SCBR-Agent (V3.1)
**Spiral Case-Based Reasoning Clinical Decision Support System**
(螺旋案例協商推理中醫輔助診斷系統)

本專案實現了一個結合「案例推理 (CBR)」與「螺旋式協商 (Spiral Negotiation)」的智慧中醫診斷代理系統。系統包含三個主要微服務：前端 (React/Vite)、後端 (FastAPI + Agentic Workflow) 以及向量資料庫 (Weaviate)。

---

## 🚀 快速啟動指南 (Quick Start)

本專案支援使用 Docker Compose 進行全端一鍵部署。

### 1. 環境準備 (Prerequisites)
*   **Docker Desktop**: 請確保已安裝並啟動 (Windows/Mac/Linux)。
*   **NVIDIA API Keys**: 需具備 NIVDIA NIM 的 API Key (用於 Llama-3 3 模型與 Embedding)。

### 2. 設定環境變數 (.env)
請在專案根目錄下建立 `.env` 檔案，並填入以下核心設定 (請替換為您的真實 Key)：

```properties
# System Configuration
ENV_MODE=development
LOG_LEVEL=INFO

# Feature Flags
USE_V31_PIPELINE=true
RUN_SYNC_ON_STARTUP=True  # 啟動時自動同步/向量化資料

# NVIDIA NIM (Required)
NVIDIA_LLM_API_KEY=nvapi-xxxx...
NVIDIA_EMBEDDING_API_KEY=nvapi-xxxx...
LLM_MODEL_NAME=nvidia/llama-3.3-nemotron-super-49b-v1.5
EMBEDDING_MODEL_NAME=baai/bge-m3

# Database
WEAVIATE_URL=http://weaviate:8080
```

### 3. 啟動系統 (Start with Docker)
在專案根目錄執行以下指令：

```bash
# 啟動所有服務 (背景執行)
docker-compose up -d

# 若需要查看啟動過程的 Logs
docker-compose logs -f
```

系統將會依序啟動：
1.  **Weaviate**: 向量資料庫初始化。
2.  **Backend**: 連線資料庫並執行 `SyncManager` (若 `RUN_SYNC_ON_STARTUP=True`，此時會自動載入 `data/` 下的 JSON 進行向量化)。
3.  **Frontend**: 網頁介面啟動。

###  驗證服務 (Verification)
啟動完成後，您可以透過瀏覽器訪問以下服務：

| 服務名稱 | 網址 | 功能說明 |
| :--- | :--- | :--- |
| **Frontend UI** | [http://localhost:3000](http://localhost:3000) | 系統操作主介面 (問診、診斷展示)。 |
| **Backend API** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger API 文件，可直接測試 API。 |
| **Weaviate** | [http://localhost:8080/v1/meta](http://localhost:8080/v1/meta) | 查看向量資料庫版本與狀態。 |

---

## 🛠️ 開發與維護 (Development)

### 常見 Docker 指令
*   **查看後端 Log (含 Agent 思考過程)**:
    ```bash
    docker-compose logs -f backend
    ```
*   **重啟特定服務** (例如修改了 Python 程式碼，雖然有 Hot Reload 但有時需重啟):
    ```bash
    docker-compose restart backend
    ```
    ```bash
    docker-compose restart frontend
    ```
*   **完全停止並移除容器**:
    ```bash
    docker-compose down
    ```

### 資料同步 (Data Sync)
若您修改了 `data/tcm_expert_cases.json` 或其他資料檔：
1.  確保 `.env` 中 `RUN_SYNC_ON_STARTUP=True`。
2.  執行 `docker-compose restart backend`，系統啟動時會自動比對並增量更新向量庫。

### 手動執行實驗腳本
若需進入容器內執行實驗腳本 (如 `run_100_case_experiment.py`)：
```bash
docker exec -it scbr_backend bash
# 進入容器後
cd test_workspace_v31
python run_100_case_experiment.py
```

---

## 📂 專案結構簡介
*   `backend/`: FastAPI 後端核心代碼
    *   `app/agents/`: 核心 Agent 邏輯 (Diagnosis, Critic, Safety...)
    *   `app/database/`: Weaviate 連線與同步管理
*   `frontend/`: React 前端代碼
*   `data/`: 原始中醫案例與規則資料 (JSON)
*   `test_workspace_v31/`: 實驗腳本與評估結果輸出區

## 📖 系統操作指南 (System Usage Guide)

本系統以「螺旋式協商推理」為核心，模擬真實中醫師的問診流程。操作流程分為以下三個階段：

### 1. 初始問診 (Initial Consultation)
*   **進入首頁**：打開瀏覽器訪問 [http://localhost:3000](http://localhost:3000)。
*   **輸入主訴**：在對話框中輸入您的主要不適症狀。
    *   *範例*：「最近常常失眠，覺得心煩口乾，晚上這幾天特別嚴重。」
*   **送出訊息**：按下 Enter 或發送按鈕。

### 2. 互動式追問 (Interactive Inquiry)
*   系統會根據您的主訴，啟動 **Symptom Analysis** 與初步推理。
*   若資訊不足以確診，系統會扮演醫師角色，提出針對性的 **追問 (Follow-up Questions)**。
    *   *系統提問*：「請問您是否有伴隨便秘或小便黃的情況？」
    *   *您的回應*：「有，大便比較乾硬，小便顏色深。」
*   此過程可能會進行 1~3 回合，直到系統收集足夠的證據 。

### 3. 診斷報告 (Analysis & Decision)
*   當系統收集齊全資訊後，會進行最終推理並生成完整報告。
*   **診斷結果 (Diagnosis)**：顯示辨證結果 (如「心火亢盛」)。
*   **病機分析 (Pathology)**：解釋病因、病機與症狀的關聯。
*   **治則建議 (Treatment)**：提供相應的治法原則 (如「清心瀉火，養陰安神」)。
*   **信心分數 (Confidence)**：若分數過低 (<0.6)，系統可能會建議「由真人醫師診斷」。

> **💡 小提示**：這是輔助診斷系統，所有建議僅供參考，實際醫療行為請諮詢合格中醫師。
