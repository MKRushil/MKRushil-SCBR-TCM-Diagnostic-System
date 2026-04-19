import apiClient from './axiosClient'
import type { ChatRequest, ChatResponse, FeedbackRequest } from '@/types/apiTypes'

export const scbrService = {
  /**
   * 發送對話請求
   * 對應後端 POST /api/v1/chat
   */
  async sendChat(payload: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/chat', payload)
    return response.data
  },

  /**
   * 發送學習閉環回饋
   * 對應後端 POST /api/v1/feedback
   */
  async sendFeedback(payload: FeedbackRequest): Promise<void> {
    await apiClient.post('/feedback', payload)
  },

  /**
   * 系統健康檢查
   */
  async checkHealth(): Promise<{ status: string }> {
    const response = await apiClient.get('/health')
    return response.data
  }
}