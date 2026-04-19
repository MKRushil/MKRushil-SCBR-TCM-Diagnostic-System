<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import { usePatientStore } from '@/stores/patientStore'
import { scbrService } from '@/api/scbrService'
import { ThumbsUp, Edit, ThumbsDown, Check } from 'lucide-vue-next'

const chatStore = useChatStore()
const patientStore = usePatientStore()
const isSubmitted = ref(false)
const feedbackStatus = ref('')

const sendFeedback = async (action: 'ACCEPT' | 'MODIFY' | 'REJECT') => {
  if (isSubmitted.value) return

  let modifiedContent = undefined

  // 處理修改邏輯
  if (action === 'MODIFY') {
    // 簡單實作：使用 prompt 獲取修改意見
    // 進階實作：應顯示 Modal，帶入當前診斷讓醫師編輯
    const userInput = prompt('請輸入修正後的診斷建議與治則：', `診斷：${chatStore.currentDiagnosis[0]?.disease_name || ''}\n治則：`)
    
    if (userInput === null) return // 使用者取消
    if (!userInput.trim()) {
      alert('修改內容不能為空')
      return
    }
    modifiedContent = userInput
  }

  try {
    await scbrService.sendFeedback({
      session_id: chatStore.sessionId,
      patient_id: patientStore.currentPatientId || 'anonymous', // 確保有值
      action: action,
      modified_content: modifiedContent
    })
    isSubmitted.value = true
    
    if (action === 'ACCEPT') feedbackStatus.value = '已採納並寫入案例庫 (Learning Loop)'
    else if (action === 'MODIFY') feedbackStatus.value = '已提交修正並更新學習 (Learning Loop)'
    else feedbackStatus.value = '已拒絕此建議'
    
  } catch (e) {
    console.error(e)
    alert('回饋發送失敗，請稍後再試')
  }
}
</script>

<template>
  <div v-if="chatStore.currentDiagnosis.length > 0 && !isSubmitted" class="flex justify-end space-x-2 mt-4 pt-4 border-t border-slate-200">
    <button 
      @click="sendFeedback('ACCEPT')"
      class="flex items-center px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded hover:bg-emerald-200 text-xs transition"
    >
      <ThumbsUp class="w-3 h-3 mr-1" /> 採納
    </button>
    <button 
      @click="sendFeedback('MODIFY')"
      class="flex items-center px-3 py-1.5 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 text-xs transition"
    >
      <Edit class="w-3 h-3 mr-1" /> 修改
    </button>
    <button 
      @click="sendFeedback('REJECT')"
      class="flex items-center px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-xs transition"
    >
      <ThumbsDown class="w-3 h-3 mr-1" /> 拒絕
    </button>
  </div>
  
  <div v-else-if="isSubmitted" class="mt-4 pt-2 text-right text-xs text-slate-500 flex justify-end items-center">
    <Check class="w-3 h-3 mr-1 text-emerald-500" />
    {{ feedbackStatus }}
  </div>
</template>