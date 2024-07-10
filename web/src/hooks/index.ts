import {createWebHistory, RouterHistory, NavigationGuardWithThis, NavigationHookAfter, Router, RouteRecordRaw} from 'vue-router'
import {InternalAxiosRequestConfig, AxiosResponse} from 'axios'
import Cookie from 'js-cookie'
import './utils/route'
import { user } from '@/service'
import { redirectToLogin } from '@/utils/auth'
import { useCommonStore, useUserStore } from '@/store'
import { projectNames } from '@/project-init'
import { getDefaultRoute, transformRoute } from './utils/route'
import { RESPONSE_STATUS_MSG, TOKEN_KEY } from '@/enums'
import { Message } from '@/utils'

interface RouterHook {
  history: RouterHistory
  /**不需要鉴权的路由白名单 */
  whiteRoutes: string[]
  /**不需要鉴权的额外路由白名单 */
  extraWhiteRoutes?: string[]
  /**项目基础路由，在开发中，可做路由配置使用 */
  projectBaseRoutes?: RouteRecordRaw[]
  /**是否请求动态路由*/
  useRomoteRoute: boolean
  layout: () => Promise<unknown>
  excRoute: (router:Router) => any
  beforeHook: (router:Router) => NavigationGuardWithThis<undefined>
  afterHook: (router:Router) => NavigationHookAfter
}

interface Request {
  // 成功code状态取值
  SUCESS_CODE_KEY: String,
  SUCESS_CODE: (number | string | undefined )[],
  requestHook: (value: InternalAxiosRequestConfig) => any
  responseHook: (value: AxiosResponse<any, any>) => any
  responseError: (error:any) => any
}

interface Hooks {
  $router: Router
  /*LayoutCommon组件底部文案*/
  footerText:string
  title: string,
  router: RouterHook
  request: Request
  api: {
    /**获取项目id */
    getProjectId?: () => Promise<any>
    /**获取web路由权限 */
    permissionRoute: () => Promise<any>
    userInfo?: (data:any) => Promise<any>
    /**登录 */
    login: (data:any) => Promise<any>
    /**退出登录 */
    logout: (data:any) => Promise<any>
  }
}

/**
 * 路由拦截钩子
 * 请求拦截钩子
 */
const hooks:Hooks = {
  $router: null as any,
  footerText: '',
  title: '',
  router: {
    useRomoteRoute: true,
    history: createWebHistory(),
    whiteRoutes: ['/login', '/404', '/403', '/500', '/na-demo/icon', '/na-demo/component'],
    layout: () => import('@/layout/LayoutCommon.vue'),
    beforeHook: (router) => async (to, _from) => {
      // 判断是否登录
      const whiteRoute = hooks.router.whiteRoutes.concat(hooks.router.extraWhiteRoutes || [])
      if (whiteRoute.includes(to.path)) { // 白名单
        return true
      }
      if (!Cookie.get(TOKEN_KEY)) { // 未鉴权
        return redirectToLogin(to)
      }
      const userStore = useUserStore()
      const commonStore = useCommonStore()
      if (!userStore.isAddDynamicRoute) {
        const tmp:RouteRecordRaw[] = []
        if (hooks.router.projectBaseRoutes) {
          tmp.unshift(...hooks.router.projectBaseRoutes)
        }
        userStore.permissionRoute = tmp
        if (hooks.router.useRomoteRoute) { // 动态加载权限路由
          const routeRes = await userStore.getOriginPermissionRoute()
          for (let projectName of projectNames) { // TODO支持多项目时此处需变逻辑
            const {mapRoutes, rmenus} = transformRoute(projectName, routeRes, hooks.router.layout)
            mapRoutes.forEach(it => {
              router.addRoute(it)
            })
            tmp.push(...rmenus)
            userStore.remoteRoute = [...mapRoutes]
          }
        } else {
          userStore.isAddDynamicRoute = true
        }
        getDefaultRoute(router.getRoutes(), router)
        // 添加历史路由
        commonStore.addHistoy(to)
        return { ...to, replace: true }
      }
      commonStore.addHistoy(to)
      return true
    },
    afterHook: (_router) => (_to, _from) => {},
    excRoute: (_router) => {
      // 动态增加路由等
    }
  },
  request: {
    SUCESS_CODE_KEY: 'code',
    SUCESS_CODE: [200, 201, 20000],
    requestHook: (config: InternalAxiosRequestConfig) => {
      config.headers.Authorization = Cookie.get(TOKEN_KEY) || ''
      return config
    },
    responseHook: (response: AxiosResponse<any, any>) => {
      const data = response.data
      if (data && hooks.request.SUCESS_CODE.includes(data[hooks.request.SUCESS_CODE_KEY as any])) {
        return Promise.resolve(response.data)
      } else {
        Message.error(response.data.msg || response.data.message)
        return Promise.reject(response.data)
      }
    },
    responseError: (error:any) => {
      if (error && error.response) {
        let response = error.response
        if (response.status === 401) { // 跳转至登录
          Cookie.remove(TOKEN_KEY)
          return redirectToLogin()
        }
        Message.error(response.data.msg || response.data.message || RESPONSE_STATUS_MSG[response.status] || `${response.status}-未知异常`)
      }
      return Promise.reject(error)
    }
  },
  api: {
    permissionRoute: async () => { // 获取权限路由
      let navigateId:any
      if (hooks.api.getProjectId) {
        navigateId = await hooks.api.getProjectId()
      } else {
        navigateId = localStorage.getItem('netops-work-tenant')
      }
      // 获取项目id
      return user.getPermissionRoute({
        parent__isnull: true,
        navigate__id: navigateId
      })
    },
    login: async (data) => { // 登录
      return user.login(data)
    },
    logout: async (data) => {
      return user.logout(data)
    }
  }
}

export default hooks
