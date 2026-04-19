<script setup lang="ts">
import { computed } from 'vue'
import type { DiagnosisCandidate } from '@/types/apiTypes'
import { formatConfidence } from '@/utils/formatters'
import { CheckCircle, AlertCircle } from 'lucide-vue-next'

const props = defineProps<{
  diagnosis: DiagnosisCandidate
  mode: 'DEFINITIVE' | 'FALLBACK' | 'INQUIRY_ONLY'
}>()

const isDefinitive = computed(() => props.mode === 'DEFINITIVE')

const cardClass = computed(() => {
  if (isDefinitive.value) {
    return 'bg-emerald-50 border-emerald-200 text-emerald-900'
  }
  return 'bg-amber-50 border-amber-200 text-amber-900'
})

const iconColor = computed(() => isDefinitive.value ? 'text-emerald-600' : 'text-amber-600')
</script>

<template>
  <div 
    class="border rounded-lg p-4 mb-3 transition-all hover:shadow-md"
    :class="cardClass"
  >
    <div class="flex items-start justify-between">
      <div class="flex items-center">
        <CheckCircle v-if="isDefinitive" class="w-5 h-5 mr-2" :class="iconColor" />
        <AlertCircle v-else class="w-5 h-5 mr-2" :class="iconColor" />
        
        <h4 class="font-bold text-lg">
          {{ diagnosis.disease_name }}
        </h4>
      </div>
      <span class="text-sm font-mono font-bold bg-white px-2 py-1 rounded border opacity-80">
        {{ formatConfidence(diagnosis.confidence) }}
      </span>
    </div>

    <!-- 規格書 7.2: 保底模式必顯示 Condition -->
    <div v-if="diagnosis.condition" class="mt-2 text-sm italic opacity-90 border-t border-dashed border-current pt-2">
      <span class="font-bold">成立條件：</span> {{ diagnosis.condition }}
    </div>
  </div>
</template>