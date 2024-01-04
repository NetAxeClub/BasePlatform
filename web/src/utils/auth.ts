import type { RouteLocationNormalized }  from 'vue-router'

import hooks from '@/hooks'
import { useUserStore } from '@/store'

/**
 * TODO 第三方鉴权时需要调整逻辑
 * 跳转至登录页
 */
export const redirectToLogin = (to?: RouteLocationNormalized):any => {
  const userStore = useUserStore()
  userStore.removeLoginInfo()
  if (to) {
    return {
      path: '/login',
      query: { redirect: to.fullPath }
    }
  } else {
    hooks.$router.push({
      path: '/login'
    })
  }
}