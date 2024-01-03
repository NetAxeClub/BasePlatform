import hooks from '@/hooks'
import {defineStore} from 'pinia'
import { RouteRecordRaw, RouteLocationNormalized } from 'vue-router'
import Cookie from 'js-cookie'
import { TOKEN_KEY } from '@/enums'
import { rmDefaultRoute } from '@/hooks/utils/route'

const _removeRoute = (routes: RouteRecordRaw[]) => {
  rmDefaultRoute(hooks.$router)
  routes.forEach(route => {
    hooks.$router.removeRoute(route.name as string)
  })
}

export const useUserStore = defineStore('user', {
  state: () => {
    return {
      userInfo: {} as any,
      permissionRoute: [] as RouteRecordRaw[],
      remoteRoute: [] as RouteRecordRaw[],
      isAddDynamicRoute: false
    }
  },
  actions: {
    async getOriginPermissionRoute () {
      // 获取权限路由
      const data = await hooks.api.permissionRoute()
      this.isAddDynamicRoute = true
      return data.results
    },
    async login (data:any) {
      const res = await hooks.api.login(data)
      this.userInfo = res.data
      Cookie.set(TOKEN_KEY, 'Bearer ' + this.userInfo.token)
      return res.data
    },
    removeLoginInfo () {
      const commonStore = useCommonStore()
      commonStore.clearHistory()
      this.userInfo = {}
      // 移除权限路由
      _removeRoute(this.remoteRoute)
      this.permissionRoute = []
      this.isAddDynamicRoute = false
      Cookie.remove(TOKEN_KEY)
    },
    async logout (data: any) {
      const res =  await hooks.api.logout(data)
      this.removeLoginInfo()
      return res
    }
  }
})

export type HistoryRoute = {
  path: string
  name: string
  title: string
}

const _isInPermissionRoute = (routes:RouteRecordRaw[], to:RouteLocationNormalized) => {
  let result = false
  const fn = (rs:RouteRecordRaw[]) => {
    for (let r of rs) {
      if (r.name === to.name && !(r.meta && r.meta.hidden)) {
        result = true
      }
      if (!result && r.children && r.children.length) {
        fn(r.children)
      }
    }
  }
  fn(routes)
  return result
}

export const useCommonStore = defineStore('common', {
  state: () => {
    return {
      historyRoutes: [] as HistoryRoute[]
    }
  },
  actions: {
    addHistoy (route:RouteLocationNormalized) { // 添加历史记录
      const userStore = useUserStore()
      if (!this.historyRoutes.some(el => el.name === route.name) && _isInPermissionRoute(userStore.permissionRoute, route)) {
        this.historyRoutes.push({
          path: route.fullPath,
          name: route.name as string,
          title: (route.meta && route.meta.title ? route.meta.title : route.name) as string
        })
      }
    },
    removeHistory (index:number) { // 删除历史记录
      this.historyRoutes.splice(index, 1)
    },
    clearHistory () {
      this.historyRoutes = []
    }
  }
})