<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import ChatBubble from './ChatBubble.vue'
import InquiryForm from '@/components/interaction/InquiryForm.vue'

const chatStore = useChatStore()
const containerRef = ref<HTMLElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (containerRef.value) {
    containerRef.value.scrollTop = containerRef.value.scrollHeight
  }
}

// 監聽訊息列表變化，自動捲動
watch(() => chatStore.messages.length, scrollToBottom)

onMounted(() => {
  // 初始歡迎訊息
  if (chatStore.messages.length === 0) {
    chatStore.addMessage('assistant', `您好，我是 Agentic SCBR-CDSS。請輸入病患的主訴與詳細症狀，我將協助您進行診斷分析。\n\n**免責聲明:** 本系統為學術研究用輔助診斷系統，AI 輸出可能包含錯誤或幻覺。所有醫療決策請務必由合格中醫師確認。本系統不承擔任何醫療責任。`)
  }
})
</script>

<template>
  <div ref="containerRef" class="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50">
    <div v-if="chatStore.messages.length === 0" class="text-center text-slate-400 mt-10 text-sm">
      <p>請輸入病患主訴開始診斷...</p>
    </div>
    
    <ChatBubble 
      v-for="msg in chatStore.messages" 
      :key="msg.id" 
      :role="msg.role" 
      :content="msg.content"
      :timestamp="msg.timestamp"
    />
    
    <div v-if="chatStore.isProcessing" class="flex justify-start">
      <div class="bg-white p-3 rounded-2xl rounded-tl-none shadow-sm border border-slate-100 flex items-center space-x-2">
        <div class="w-2 h-2 bg-primary-400 rounded-full animate-bounce"></div>
        <div class="w-2 h-2 bg-primary-400 rounded-full animate-bounce delay-75"></div>
        <div class="w-2 h-2 bg-primary-400 rounded-full animate-bounce delay-150"></div>
      </div>
    </div>
  </div>
</template>