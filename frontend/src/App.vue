<script setup lang="ts">
import { ref, computed } from 'vue'
import { usePatientStore } from '@/stores/patientStore'
import { useChatStore } from '@/stores/chatStore'
import { 
  LayoutDashboard, 
  Stethoscope, 
  User, 
  LogOut,
  MessageSquare,
  Activity,
  FileText,
  RotateCcw // Import Icon
} from 'lucide-vue-next'

// Components
import PatientSearch from '@/components/reception/PatientSearch.vue'
import ChatContainer from '@/components/chat/ChatContainer.vue'
import InputArea from '@/components/chat/InputArea.vue'
import DiagnosisCard from '@/components/dashboard/DiagnosisCard.vue'
import EvidencePanel from '@/components/dashboard/EvidencePanel.vue'
import RadarChart from '@/components/dashboard/RadarChart.vue'
import FeedbackActions from '@/components/interaction/FeedbackActions.vue'
import SafetyBanner from '@/components/layout/SafetyBanner.vue'
import GlobalDisclaimer from '@/components/layout/GlobalDisclaimer.vue'

const patientStore = usePatientStore()
const chatStore = useChatStore()

// Layout State
type LayoutMode = 'dashboard' | 'workbench'
const layoutMode = ref<LayoutMode>('workbench')

// Active Tab (for Workbench Right Panel / Dashboard Panel)
const activeTab = ref<'chat' | 'diagnosis' | 'reasoning' | 'report'>('diagnosis')

const setMode = (mode: LayoutMode) => {
  layoutMode.value = mode
  // 切換模式時重置 Tab
  if (mode === 'workbench') activeTab.value = 'diagnosis'
  else activeTab.value = 'chat'
}

const setTab = (tab: any) => {
  activeTab.value = tab
}

const handleGlobalReset = () => {
  if (confirm('確定要結束本輪診斷並開始新對話嗎？所有記錄將被清除。')) {
    chatStore.resetSession()
  }
}
</script>

<template>
  <!-- 頂層容器：透過 class 控制 CSS 變數與 Grid -->
  <div :class="layoutMode === 'dashboard' ? 'layout-dashboard' : 'layout-workbench'">
    
    <!-- 全域頂部 -->
    <header class="global-header">
      <div class="brand-area">
        <Stethoscope class="w-6 h-6" />
        SCBR 智慧醫療系統 <span class="text-xs bg-slate-100 text-slate-500 px-2 rounded ml-2">v8.0</span>
      </div>
      
      <!-- 中間：病患資訊 -->
      <div class="flex-1 flex justify-center">
        <div v-if="patientStore.isIdentified" class="flex items-center bg-slate-50 px-4 py-1.5 rounded-full space-x-3 text-sm border border-slate-200">
          <User class="w-4 h-4 text-slate-500" />
          <span class="text-slate-600">病患: <strong class="text-slate-900">{{ patientStore.patientName }}</strong></span>
          <span class="text-slate-400 text-xs border-l pl-3 border-slate-300">ID: {{ patientStore.currentPatientId }}</span>
          <button @click="patientStore.clearPatient" class="ml-2 text-red-500 hover:bg-red-50 px-2 py-0.5 rounded transition flex items-center">
            <LogOut class="w-3 h-3 mr-1" /> 登出
          </button>
        </div>
        <PatientSearch v-else />
      </div>

      <!-- 佈局切換器 -->
      <div class="layout-switcher">
        <button class="layout-btn" :class="{ active: layoutMode === 'dashboard' }" @click="setMode('dashboard')">
          <LayoutDashboard class="w-4 h-4" /> 儀表板
        </button>
        <button class="layout-btn" :class="{ active: layoutMode === 'workbench' }" @click="setMode('workbench')">
          <Stethoscope class="w-4 h-4" /> 工作台
        </button>
      </div>
    </header>

    <div class="app-container">
        
      <!-- 左側導航 (僅 Dashboard 模式顯示，透過 CSS margin-left 控制) -->
      <aside class="sidebar">
        <div class="sidebar-menu">
          <div class="menu-item" :class="{ active: activeTab === 'chat' }" @click="setTab('chat')">
            <MessageSquare class="w-4 h-4" /> 診斷對話
          </div>
          <div class="menu-item" :class="{ active: activeTab === 'diagnosis' }" @click="setTab('diagnosis')">
            <Activity class="w-4 h-4" /> 診斷建議
          </div>
          <div class="menu-item" :class="{ active: activeTab === 'reasoning' }" @click="setTab('reasoning')">
            <Activity class="w-4 h-4" /> 推導過程
          </div>
          <div class="menu-item" :class="{ active: activeTab === 'report' }" @click="setTab('report')">
            <FileText class="w-4 h-4" /> 診斷報告
          </div>
        </div>
      </aside>

      <!-- 主內容區 -->
      <main class="main-canvas">
          
        <!-- 1. Chat Panel -->
        <!-- 在 Workbench 模式下永遠顯示；在 Dashboard 模式下，只有 tab='chat' 時顯示 (透過 active class) -->
        <section id="panel-chat" class="panel" 
          v-show="layoutMode === 'workbench' || (layoutMode === 'dashboard' && activeTab === 'chat')"
          :class="{ 'active': activeTab === 'chat' }"
        >
          <div class="panel-header">
            <span><MessageSquare class="w-4 h-4 inline mr-2" /> 病史採集與對話</span>
            <button 
              class="ml-auto text-xs text-slate-500 hover:text-primary-600 px-2 py-1 rounded transition-colors flex items-center space-x-1"
              @click="handleGlobalReset"
              title="結束本輪診斷 (New Session)"
            >
              <RotateCcw class="w-3 h-3" />
              <span>結束本輪診斷</span>
            </button>
          </div>
          
          <div class="panel-content flex flex-col p-0"> 
            <SafetyBanner />
            <ChatContainer class="flex-1" />
          </div>
          
          <div class="border-t border-slate-200">
            <InputArea />
          </div>
        </section>

        <!-- Workbench 右側容器 (Wrapper) 
             在 Workbench 模式下作為右欄 Flex 容器；
             在 Dashboard 模式下使用 display: contents 讓子 Panel 能夠全螢幕顯示 -->
        <div class="workbench-right-col" :style="layoutMode === 'dashboard' ? 'display: contents' : ''">
            
          <!-- Tabs (僅 Workbench 顯示) -->
          <div class="workbench-tabs" v-if="layoutMode === 'workbench'">
            <div class="wb-tab" :class="{ active: activeTab === 'diagnosis' }" @click="setTab('diagnosis')">診斷建議</div>
            <div class="wb-tab" :class="{ active: activeTab === 'reasoning' }" @click="setTab('reasoning')">推導過程</div>
            <div class="wb-tab" :class="{ active: activeTab === 'report' }" @click="setTab('report')">診斷報告</div>
          </div>

          <!-- 2. Diagnosis Panel -->
          <section id="panel-diagnosis" class="panel" 
            v-show="activeTab === 'diagnosis'"
            :class="{ 'active': activeTab === 'diagnosis' }"
          >
             <div class="panel-header dashboard-only" v-if="layoutMode === 'dashboard'">
                <span><Activity class="w-4 h-4 inline mr-2"/> 診斷建議 (Suggestions)</span>
             </div>
             <div class="panel-content space-y-6">
                <RadarChart />
                
                <div v-if="chatStore.currentDiagnosis.length > 0" class="space-y-3">
                  <DiagnosisCard 
                    v-for="diag in chatStore.currentDiagnosis"
                    :key="diag.disease_name"
                    :diagnosis="diag"
                    :mode="chatStore.responseType"
                  />
                  <FeedbackActions />
                </div>
                <div v-else class="text-center py-12 text-slate-400 text-sm border-2 border-dashed border-slate-200 rounded-lg">
                  請輸入主訴以獲取建議。
                </div>
             </div>
          </section>

          <!-- 3. Reasoning Panel -->
          <section id="panel-reasoning" class="panel" 
            v-show="activeTab === 'reasoning'"
            :class="{ 'active': activeTab === 'reasoning' }"
          >
            <div class="panel-header dashboard-only" v-if="layoutMode === 'dashboard'">
              <span><Activity class="w-4 h-4 inline mr-2"/> 推導過程 (Trace)</span>
            </div>
            <div class="panel-content">
              <EvidencePanel />
            </div>
          </section>

          <!-- 4. Report Panel -->
          <section id="panel-report" class="panel" 
            v-show="activeTab === 'report'"
            :class="{ 'active': activeTab === 'report' }"
          >
            <div class="panel-header dashboard-only" v-if="layoutMode === 'dashboard'">
              <span><FileText class="w-4 h-4 inline mr-2"/> 最終報告 (Report)</span>
            </div>
            <div class="panel-content bg-slate-200 flex justify-center p-8">
               <div class="bg-white shadow-lg p-12 w-[210mm] min-h-[297mm] text-slate-800 text-sm leading-relaxed prose prose-slate">
                  <div v-if="chatStore.formattedReport" v-html="chatStore.formattedReport.replace(/\n/g, '<br>')"></div>
                  <div v-else class="text-center text-slate-400 py-20 italic">
                    尚未生成報告。
                  </div>
               </div>
            </div>
          </section>

        </div>

      </main>
    </div>

    <!-- Footer -->
    <GlobalDisclaimer />
  </div>
</template>
