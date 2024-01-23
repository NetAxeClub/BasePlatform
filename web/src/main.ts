import {createApp} from 'vue'
import './style.scss'
import './project-init'
import App from './App.vue'
import initRouter from './router'
import request from './service/request'
import { createPinia } from 'pinia'
import '@/assets/font/na-icon.css'
import service from './hooks/service'
import directive from './directive'

declare global {
  interface Window {
    // 是否存在无界
    __POWERED_BY_WUJIE__?: boolean;
    // 子应用mount函数
    __WUJIE_MOUNT: () => void;
    // 子应用unmount函数
    __WUJIE_UNMOUNT: () => void;
    // 子应用无界实例
    __WUJIE: { mount: () => void };
  }
}

const initApp = () => {
  const app = createApp(App)
  const router = initRouter()
  app.use(router)
  app.use(createPinia())
  app.use(service)
  app.use(directive)
  app.config.globalProperties.$http = request
  app.mount('#app')
  return app
}

// if (window.__POWERED_BY_WUJIE__) {
//   let instance:any
//   window.__WUJIE_MOUNT = () => {
//     instance = initApp()
//   }
//   window.__WUJIE_UNMOUNT = () => {
//     instance.unmount()
//   }
// } else {
//   initApp()
// }
initApp()

