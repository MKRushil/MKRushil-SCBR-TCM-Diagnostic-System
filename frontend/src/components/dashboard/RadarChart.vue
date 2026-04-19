<script setup lang="ts">
import { ref, onMounted, watch, computed, nextTick } from 'vue'
import * as echarts from 'echarts'
import { useChatStore } from '@/stores/chatStore'

const chatStore = useChatStore()
const chartRef = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const hasData = computed(() => {
  const data = chatStore.visualizationData
  return data && Object.keys(data).length > 0 && data.series
})

const renderChart = async () => {
  if (!hasData.value) return
  
  // 等待 DOM 更新
  await nextTick()
  
  if (!chartRef.value) return

  // 確保容器有寬高
  if (chartRef.value.clientWidth === 0) {
    console.warn('[RadarChart] Container width is 0, retrying in 100ms...')
    setTimeout(renderChart, 100)
    return
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  // 強制設定字體大小以適應 Dashboard
  const option = {
    ...chatStore.visualizationData,
    radar: {
      ...chatStore.visualizationData.radar,
      axisName: {
        color: '#64748b',
        fontSize: 12
      }
    }
  }
  
  chartInstance.setOption(option)
  chartInstance.resize()
}

// 監聽數據變化
watch(() => chatStore.visualizationData, () => {
  if (hasData.value) {
    renderChart()
  }
}, { deep: true })

// 監聽視窗大小變化
window.addEventListener('resize', () => {
  chartInstance?.resize()
})
</script>

<template>
  <div v-if="hasData" class="bg-white p-4 rounded-lg shadow-sm border border-slate-200 mt-4">
    <h3 class="text-sm font-bold text-slate-700 mb-2 border-l-4 border-emerald-500 pl-2">
      辨證視覺化分析
    </h3>
    <div ref="chartRef" class="w-full h-64"></div>
  </div>
  <!-- 無數據時不顯示 (規格書 7.2) -->
</template>