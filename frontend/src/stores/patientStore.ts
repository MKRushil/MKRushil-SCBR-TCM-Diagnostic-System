import { defineStore } from 'pinia'
import { ref } from 'vue'

export const usePatientStore = defineStore('patient', () => {
  // 規格書 2.0: 管理 CurrentPatient
  const currentPatientId = ref<string>('') // Raw ID (輸入時暫存)
  const isIdentified = ref<boolean>(false)
  const patientName = ref<string>('') // 模擬顯示用

  /**
   * 設定當前病患
   * @param id 身分證字號
   */
  const setPatient = (id: string) => {
    currentPatientId.value = id
    // 簡單模擬姓名遮罩顯示
    patientName.value = "王XX" 
    isIdentified.value = true
  }

  const clearPatient = () => {
    currentPatientId.value = ''
    patientName.value = ''
    isIdentified.value = false
  }

  return {
    currentPatientId,
    patientName,
    isIdentified,
    setPatient,
    clearPatient
  }
})