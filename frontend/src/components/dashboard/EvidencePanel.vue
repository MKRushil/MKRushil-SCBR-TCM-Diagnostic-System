<script setup lang="ts">
import { computed } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import { 
  GitBranch, 
  BrainCircuit, 
  Database, 
  ArrowRight,
  Lightbulb
} from 'lucide-vue-next'

const chatStore = useChatStore()

const traceLines = computed(() => {
  if (!chatStore.evidenceTrace) return []
  // Split trace by newlines and filter empty
  return chatStore.evidenceTrace.split('\n').filter(line => line.trim())
})

const pathType = computed(() => {
  if (!chatStore.evidenceTrace) return null
  if (chatStore.evidenceTrace.includes('Path A')) return 'PATH_A'
  if (chatStore.evidenceTrace.includes('Path B')) return 'PATH_B'
  return null
})
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-base font-bold text-slate-700 flex items-center">
        <GitBranch class="w-5 h-5 text-primary-600 mr-2" />
        推理路徑追溯 (Trace)
      </h3>
      <span 
        v-if="pathType" 
        class="text-xs font-mono px-2 py-1 rounded border"
        :class="pathType === 'PATH_A' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'"
      >
        {{ pathType === 'PATH_A' ? 'Path A: Memory Recall' : 'Path B: Logical Inference' }}
      </span>
    </div>

    <!-- Empty State -->
    <div v-if="traceLines.length === 0" class="text-center py-12 bg-white rounded-lg border border-dashed border-slate-200 text-slate-400 text-sm">
      尚無推理數據
    </div>

    <!-- Trace Cards (Timeline Style) -->
    <div v-else class="relative pl-4 pt-2 pb-2">
      <!-- Vertical Line -->
      <div class="absolute left-6 top-0 bottom-0 w-0.5 bg-slate-200"></div>
      
      <div 
        v-for="(line, idx) in traceLines" 
        :key="idx"
        class="relative mb-6 pl-10"
      >
        <!-- Connector Dot -->
        <div class="absolute left-[1.35rem] top-3 w-3 h-3 rounded-full border-2 border-white shadow-sm z-10"
          :class="idx === 0 ? 'bg-primary-500' : 'bg-slate-400'"
        ></div>

        <div class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 text-sm leading-relaxed text-slate-700 hover:shadow-md transition-shadow">
          <div class="flex items-start">
            <component 
              :is="line.includes('檢索') ? Database : line.includes('分析') ? BrainCircuit : ArrowRight" 
              class="w-4 h-4 text-slate-400 mt-0.5 mr-3 shrink-0" 
            />
            <span>{{ line }}</span>
          </div>
        </div>
      </div>

      <!-- Conclusion Node -->
      <div class="relative pl-10">
        <div class="absolute left-[1.35rem] top-3 w-3 h-3 rounded-full bg-slate-800 border-2 border-white shadow-sm z-10"></div>
        <div class="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs text-slate-500 flex items-center">
          <Lightbulb class="w-3 h-3 mr-2" />
          推導結束，等待回饋。
        </div>
      </div>

    </div>
  </div>
</template>