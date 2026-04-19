<script setup lang="ts">
import { computed } from 'vue'
import { User, Bot } from 'lucide-vue-next' // 引入圖標

const props = defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date // 新增 timestamp prop
}>()

const isUser = computed(() => props.role === 'user')
const isSystem = computed(() => props.role === 'system')

// 計算訊息列的佈局方向 (使用者靠右，系統靠左)
const messageRowClass = computed(() => ({
  'flex-row-reverse': isUser.value,
  'justify-start': !isUser.value
}))

// 計算氣泡樣式
const bubbleClass = computed(() => ({
  'bg-primary-600 text-white rounded-tr-sm': isUser.value, // 使用者訊息
  'bg-white border border-slate-200 text-slate-700 rounded-tl-sm': !isUser.value // 系統/助手訊息
}))

// 計算頭像樣式
const avatarClass = computed(() => ({
  'bg-primary-600 text-white': isUser.value, // 使用者頭像
  'bg-white border border-slate-200 text-primary-600': !isUser.value // 系統/助手頭像
}))

const formattedTime = computed(() => {
  return props.timestamp.toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' })
})
</script>

<template>
  <div class="flex items-start gap-3" :class="messageRowClass">
    <!-- 頭像 -->
    <div class="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm" :class="avatarClass">
      <User v-if="isUser" class="w-5 h-5" />
      <Bot v-else class="w-5 h-5" />
    </div>

    <!-- 訊息內容 -->
    <div class="flex flex-col max-w-[70%]">
      <div class="px-4 py-3 rounded-xl shadow-sm text-base" :class="bubbleClass">
        <span v-html="content"></span>
      </div>
      <div class="text-xs text-slate-400 mt-1" :class="{ 'text-right': isUser }">
        {{ isUser ? '您' : (isSystem ? '系統' : 'AI 助手') }} ・ {{ formattedTime }}
      </div>
    </div>
  </div>
</template>