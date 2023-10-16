import { createApp } from 'vue'
import App from './App.vue'
import './styles'
import useGlobalComponents from './components'
import { useAppRouter } from './router'
import useRouterGuard from './router/guard'
import useAppPinia from './store'

function vawBoot() {
  const app = createApp(App)
  useAppPinia(app)
  useAppRouter(app)
  useGlobalComponents(app)
  useRouterGuard()
  app.mount('#app')
}

vawBoot()
