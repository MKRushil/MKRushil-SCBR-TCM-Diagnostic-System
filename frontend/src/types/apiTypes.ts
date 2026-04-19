/**
 * 規格書 7.0 前後端溝通 JSON 結構
 * 對應後端 schemas.py
 */

export interface DiagnosisCandidate {
  rank: number;
  disease_name: string;
  confidence: number;
  condition: string | null; // 用於保底模式
}

export interface FollowUpQuestion {
  required: boolean;
  question_text: string | null;
  options: string[];
}

// 核心回應結構
export interface ChatResponse {
  response_type: 'DEFINITIVE' | 'FALLBACK' | 'INQUIRY_ONLY';
  diagnosis_list: DiagnosisCandidate[];
  follow_up_question: FollowUpQuestion | null; // Nullable
  evidence_trace: string; // LLM09: 必須檢查
  safety_warning: string | null; // 規格書 5.2 安全規則產出
  visualization_data: Record<string, any> | null; // Nullable
  formatted_report: string | null; // HTML/Markdown
}

// 請求結構
export interface ChatRequest {
  session_id: string;
  patient_id: string; // Raw ID
  message: string; // Max 1000 chars
}

export interface FeedbackRequest {
  session_id: string;
  patient_id: string; // Required by backend
  action: 'ACCEPT' | 'MODIFY' | 'REJECT';
  modified_content?: string;
}