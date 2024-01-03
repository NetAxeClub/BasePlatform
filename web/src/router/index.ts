import hooks from '@/hooks'
import {createRouter} from 'vue-router'
import {routes as projectRoutes} from '@/project-init'
import moduleRoutes from './modules'

const initRouter = () => {
  const router  = createRouter({
    history: hooks.router.history,
    scrollBehavior (_to, _from, _savedPosition) {
      return {top: 0}
    },
    routes: [
      ...moduleRoutes,
      ...projectRoutes
    ]
  })
  hooks.$router = router
  hooks.router.excRoute(router)
  router.beforeEach(hooks.router.beforeHook(router))
  router.afterEach(hooks.router.afterHook(router))
  return router
}

export default initRouter
