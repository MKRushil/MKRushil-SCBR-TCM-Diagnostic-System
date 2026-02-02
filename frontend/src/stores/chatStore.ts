import { defineStore } from 'pinia'
import { ref } from 'vue' // 移除了 computed
import { scbrService } from '@/api/scbrService'
import type { ChatResponse, ChatRequest, DiagnosisCandidate } from '@/types/apiTypes'
import { generateSessionId } from '@/utils/formatters'
import { usePatientStore } from './patientStore'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

export const useChatStore = defineStore('chat', () => {
  const patientStore = usePatientStore()

  // State
  const sessionId = ref<string>(generateSessionId())
  const messages = ref<ChatMessage[]>([])
  const isProcessing = ref<boolean>(false)
  
  // 診斷狀態 (Dashboard Data)
  const currentDiagnosis = ref<DiagnosisCandidate[]>([])
  const responseType = ref<'DEFINITIVE' | 'FALLBACK' | 'INQUIRY_ONLY'>('INQUIRY_ONLY')
  const evidenceTrace = ref<string>('')
  const safetyWarning = ref<string | null>(null)
  const visualizationData = ref<Record<string, any>>({})
  const followUpQuestion = ref<{ required: boolean; options: string[] }>({ required: false, options: [] })
  const formattedReport = ref<string | null>(null)

  // Actions
  const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
    messages.value.push({
      id: Date.now().toString(),
      role,
      content,
      timestamp: new Date()
    })
  }

  /**
   * 發送訊息給後端 Or chestrator
   */
  const sendMessage = async (text: string) => {
    if (!text.trim() || isProcessing.value) return

    // 1. User Message
    addMessage('user', text)
    isProcessing.value = true

    // 清空上一輪的 Dashboard 狀態，避免混淆
    safetyWarning.value = null
    
    try {
      // 2. API Call
      const payload: ChatRequest = {
        session_id: sessionId.value,
        patient_id: patientStore.currentPatientId,
        message: text
      }
      
      const response: ChatResponse = await scbrService.sendChat(payload)

      // 3. Update State from Response
      responseType.value = response.response_type
      currentDiagnosis.value = response.diagnosis_list || []
      evidenceTrace.value = response.evidence_trace || ''
      safetyWarning.value = response.safety_warning || null
      
      // Handle Nullable Fields safely
      visualizationData.value = response.visualization_data || {}
      formattedReport.value = response.formatted_report || null
      
      if (response.follow_up_question) {
        followUpQuestion.value = response.follow_up_question
      } else {
        followUpQuestion.value = { required: false, question_text: null, options: [] }
      }

      // 4. Assistant Message
      // 若有反問，優先顯示反問；否則顯示診斷摘要
      let replyContent = ""
      if (followUpQuestion.value.required && followUpQuestion.value.question_text) {
        replyContent = followUpQuestion.value.question_text
      } else if (response.diagnosis_list.length > 0) {
        const topDiag = response.diagnosis_list[0]
        replyContent = `根據分析，主要考慮為【${topDiag.disease_name}】。已生成詳細診斷報告與治則建議。`
      } else {
        replyContent = "收到您的描述，但資訊不足以形成診斷，請參考右側面板。"
      }
      
      addMessage('assistant', replyContent)

    } catch (error: any) {
      console.error(error)
      
      // [Safety] Handle InputGuard 400 Errors
      if (error.response && error.response.status === 400) {
        const detail = error.response.data?.detail || ''
        if (typeof detail === 'string' && detail.includes('非法指令')) {
          addMessage('system', '偵測到非法指令，請稍後再試')
          isProcessing.value = false
          return
        }
      }

      addMessage('system', '系統連線錯誤或後端忙碌中，請稍後再試。')
    } finally {
      isProcessing.value = false
    }
  }

  const resetSession = () => {
    sessionId.value = generateSessionId()
    messages.value = []
    currentDiagnosis.value = []
    responseType.value = 'INQUIRY_ONLY'
    evidenceTrace.value = ''
    safetyWarning.value = null
    visualizationData.value = {}
    followUpQuestion.value = { required: false, options: [] }
    formattedReport.value = null
    
    // Add Welcome Message
    addMessage('assistant', `您好，我是 Agentic SCBR-CDSS。請輸入病患的主訴與詳細症狀，我將協助您進行診斷分析。\n\n**免責聲明:** 本系統為學術研究用輔助診斷系統，AI 輸出可能包含錯誤或幻覺。所有醫療決策請務必由合格中醫師確認。本系統不承擔任何醫療責任。`)
  }

  return {
    sessionId,
    messages,
    isProcessing,
    currentDiagnosis,
    responseType,
    evidenceTrace,
    safetyWarning,
    visualizationData,
    followUpQuestion,
    formattedReport,
    sendMessage,
    resetSession,
    addMessage
  }
})