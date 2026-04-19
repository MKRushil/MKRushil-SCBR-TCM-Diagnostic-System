<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chatStore'
import { Send } from 'lucide-vue-next'

const chatStore = useChatStore()
const inputText = ref('')

const handleSend = () => {
  if (!inputText.value.trim() || chatStore.isProcessing) return
  chatStore.sendMessage(inputText.value)
  inputText.value = ''
}
</script>

<template>
  <div class="input-area">
    <div class="input-wrapper">
      <textarea 
        id="chatTextarea"
        v-model="inputText"
        placeholder="請輸入病患主訴或回答問題..."
        :disabled="chatStore.isProcessing"
        @keydown.enter.prevent="handleSend"
      ></textarea>
      
      <button 
        class="send-btn"
        @click="handleSend"
        :disabled="!inputText.trim() || chatStore.isProcessing"
        title="發送訊息"
      >
        <Send class="icon" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-area {
  padding: 20px;
  background: white;
  border-top: 1px solid var(--border);
}

.input-wrapper {
  position: relative; /* 關鍵：讓按鈕可以絕對定位 */
  width: 100%;
}

textarea {
  width: 100%;
  height: 100px; /* 固定高度 */
  padding: 12px 16px;
  padding-right: 60px; /* 右側留出空間給按鈕，避免文字被遮住 */
  
  font-size: 1rem;
  line-height: 1.5;
  color: #334155;
  
  background: white;
  border: 1px solid var(--border);
  border-radius: 12px; /* 圓角 */
  resize: none; /* 禁止使用者拖拉大小 */
  outline: none;
  
  transition: border-color 0.2s, box-shadow 0.2s;
  font-family: inherit; /* 繼承 Noto Sans TC */
}

textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1);
}

textarea:disabled {
  background: #f1f5f9;
  cursor: not-allowed;
}

.send-btn {
  position: absolute;
  bottom: 12px; /* 距離底部 */
  right: 12px;  /* 距離右側 */
  
  width: 36px;
  height: 36px;
  border-radius: 50%;
  
  background-color: var(--primary);
  color: white;
  border: none;
  
  display: flex;
  align-items: center;
  justify-content: center;
  
  cursor: pointer;
  transition: background-color 0.2s, transform 0.1s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.send-btn:hover:not(:disabled) {
  background-color: #115e59; /* Teal 800 */
  transform: translateY(-1px);
}

.send-btn:active:not(:disabled) {
  transform: translateY(0);
}

.send-btn:disabled {
  background-color: #cbd5e1; /* Slate 300 */
  cursor: not-allowed;
  box-shadow: none;
}

.icon {
  width: 18px;
  height: 18px;
  margin-left: 2px; /* 視覺微調，讓紙飛機看起來置中 */
}
</style>