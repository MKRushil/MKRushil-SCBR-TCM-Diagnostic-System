<script setup lang="ts">
import { useChatStore } from '@/stores/chatStore'
import { HelpCircle } from 'lucide-vue-next'

const chatStore = useChatStore()

const handleOptionClick = (option: string) => {
  chatStore.sendMessage(option)
}
</script>

<template>
  <div 
    v-if="chatStore.followUpQuestion.options.length > 0" 
    class="bg-blue-50 p-3 rounded-lg border border-blue-100 mt-2"
  >
    <div class="flex items-center text-blue-800 text-sm font-medium mb-2">
      <HelpCircle class="w-4 h-4 mr-1" />
      建議補充資訊：
    </div>
    
    <div class="flex flex-wrap gap-2">
      <button
        v-for="option in chatStore.followUpQuestion.options"
        :key="option"
        @click="handleOptionClick(option)"
        :disabled="chatStore.isProcessing"
        class="bg-white text-blue-600 border border-blue-200 px-3 py-1 rounded-full text-xs hover:bg-blue-100 hover:border-blue-300 transition shadow-sm"
      >
        {{ option }}
      </button>
    </div>
  </div>
</template>