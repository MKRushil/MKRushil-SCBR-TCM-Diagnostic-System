import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css' // Tailwind (if exists)
import './assets/main.css' // Custom Theme
import App from './App.vue'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.mount('#app')

console.log(`[System] SCBR-CDSS Frontend v8.0 Started.`)