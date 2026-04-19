<script setup lang="ts">
import { ref } from 'vue'
import { usePatientStore } from '@/stores/patientStore'
import { Search, LogOut, User } from 'lucide-vue-next'

const patientStore = usePatientStore()
const inputId = ref('')

const handleLogin = () => {
  if (inputId.value.trim().length >= 4) {
    patientStore.setPatient(inputId.value)
    inputId.value = '' // Clear input after search
  }
}
</script>

<template>
  <div class="search-component">
    
    <!-- 狀態 A: 已登入 -->
    <div v-if="patientStore.isIdentified" class="user-badge">
        <User class="icon" />
        <span class="label">病患: <strong>{{ patientStore.patientName }}</strong></span>
        <span class="id-text">ID: {{ patientStore.currentPatientId }}</span>
        <button @click="patientStore.clearPatient" class="logout-btn">
          <LogOut class="icon-sm" /> 登出
        </button>
    </div>

    <!-- 狀態 B: 未登入 (搜尋框) -->
    <div v-else class="search-box">
      <input 
        id="idInput"
        v-model="inputId"
        type="text" 
        placeholder="請輸入 ID 調閱病歷..."
        @keyup.enter="handleLogin"
      />
      <button @click="handleLogin" title="調閱病歷">
        <Search class="icon" />
      </button>
    </div>

  </div>
</template>

<style scoped>
.search-component {
  display: flex;
  align-items: center;
}

/* --- User Badge Style --- */
.user-badge {
  display: flex;
  align-items: center;
  background-color: #f8fafc; /* Slate 50 */
  border: 1px solid var(--border);
  border-radius: 9999px; /* Pill shape */
  padding: 6px 16px;
  font-size: 0.875rem;
  color: #475569; /* Slate 600 */
}

.user-badge strong {
  color: #0f172a; /* Slate 900 */
  margin-left: 4px;
}

.user-badge .icon {
  width: 16px;
  height: 16px;
  margin-right: 8px;
  color: #64748b;
}

.id-text {
  font-size: 0.75rem;
  color: #94a3b8;
  border-left: 1px solid #cbd5e1;
  padding-left: 10px;
  margin-left: 10px;
}

.logout-btn {
  margin-left: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: #ef4444; /* Red 500 */
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.logout-btn:hover {
  background-color: #fef2f2; /* Red 50 */
}

.icon-sm {
  width: 12px;
  height: 12px;
}

/* --- Search Box Style (Pure CSS) --- */
.search-box {
  display: flex;
  align-items: center;
  width: 280px;
  background: white;
  border: 1px solid var(--border);
  border-radius: 8px; /* 圓角 */
  overflow: hidden; /* 確保內容不溢出圓角 */
  transition: border-color 0.2s, box-shadow 0.2s;
}

/* Focus 效果: 當內部的 input 被 focus 時，外層框變色 */
.search-box:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.1); /* Teal ring */
}

.search-box input {
  flex-grow: 1;
  border: none;
  outline: none;
  padding: 8px 12px;
  font-size: 0.875rem;
  color: #334155;
  background: transparent;
}

.search-box input::placeholder {
  color: #94a3b8;
}

.search-box button {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f8fafc;
  border: none;
  border-left: 1px solid var(--border);
  color: #64748b;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.search-box button:hover {
  background: var(--primary-bg);
  color: var(--primary);
}

.search-box button .icon {
  width: 16px;
  height: 16px;
}
</style>