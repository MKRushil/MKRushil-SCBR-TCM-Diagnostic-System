<script setup lang="ts">
import { useChatStore } from '@/stores/chatStore'
import { AlertTriangle } from 'lucide-vue-next'

const chatStore = useChatStore()
</script>

<template>
  <div 
    v-if="chatStore.safetyWarning" 
    class="bg-red-50 border-l-4 border-red-500 p-4 mb-4 rounded shadow-sm animate-pulse"
  >
    <div class="flex items-start">
      <div class="flex-shrink-0">
        <AlertTriangle class="h-5 w-5 text-red-500" />
      </div>
      <div class="ml-3">
        <h3 class="text-sm font-medium text-red-800">
          安全警示 (Safety Rule Triggered)
        </h3>
        <div class="mt-1 text-sm text-red-700">
          {{ chatStore.safetyWarning }}
        </div>
      </div>
    </div>
  </div>
</template>