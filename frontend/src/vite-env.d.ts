/// <reference types="vite/client" />

// 解決 Cannot find module './App.vue' 或其他 .vue 檔案的錯誤
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/ban-types
  const component: DefineComponent<{}, {}, any>
  export default component
}

// 解決環境變數 import.meta.env 的型別提示
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_MAX_INPUT_LENGTH: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}