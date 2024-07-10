import type { RouteRecordRaw, Router } from 'vue-router'

const pageComponets = import.meta.glob('/src/project/**/views/**/*.vue')

/**
 * 获取格式化后的页面对象
 * @param prjName 项目目录
 * @returns 
 */
export const getPages = (prjName: string) => {
  if (!prjName) {
    throw new Error('项目根目录必传!')
  }
  const result:Record<string, () => Promise<unknown>> = {}
  for (let key in pageComponets) {
    const path = key.replace(`/src/project/${prjName}/views`, '').replace('.vue', '')
    result[path] = pageComponets[key]
  }
  return result
}

type ApiRoutes = {
  name: string,
  hidden: boolean
  icon?: string
  id: number
  is_catalog: boolean
  is_link: boolean
  key?: string
  link_path: string
  parent: number
  sort:  number
  web_path: string
  children: ApiRoutes[]
}
const _getRouteNameByUrl = (url: string) => {
  return url.replace(/\//, '').replace(/\//g, '-')
}

/**
 * 生成单个路由对象
 * @param item
 * @param component
 * @returns 
 */
const _generatorRouteItem = (item:ApiRoutes, component:()=> Promise<unknown>):RouteRecordRaw => {
  return {
    path: item.web_path,
    name: _getRouteNameByUrl(item.web_path),
    component,
    meta: {
      title: item.name,
      icon: item.icon || '',
      hidden: item.hidden,
      id: item.id,
      is_catalog: item.is_catalog,
      is_link: item.is_link,
      key: item.key || '',
      link_path: item.link_path || '',
      parent: item.parent,
      sort: item.sort,
    }
  }
}
/**
 * 将api配置转换成页面路由
 */
export const transformRoute = (prjName:string, apiRoutes:ApiRoutes[], layout: ()=> Promise<any>):{mapRoutes: RouteRecordRaw[], rmenus: RouteRecordRaw[]} => {
  let routes:RouteRecordRaw[] = []
  const comps = getPages(prjName)
  const fn = (aRoutes: ApiRoutes[], layout: ()=> Promise<any>, tRoutes:any[], isFirst = false) => {
    const menusTemp:any[] = []
    aRoutes.forEach(item => {
      let route: RouteRecordRaw
      let menu: RouteRecordRaw
      if (item.children && item.children.length) {
        menu = _generatorRouteItem(item, layout)
        if (isFirst) {
          route = _generatorRouteItem(item, layout)
          tRoutes.push(route)
          route.children = []
          menu.children = fn(item.children, layout, route.children)
        } else {
          menu.children = fn(item.children, layout, tRoutes)
        }
      } else {
        menu = _generatorRouteItem(item, layout)
        tRoutes.push(_generatorRouteItem(item, comps[item.web_path]))
      }
      menusTemp.push(menu)
    })
    return menusTemp
  }
  const rmenus = fn(apiRoutes, layout, routes, true)
  return {mapRoutes: routes, rmenus}
}

const findFirstUnHideRoutePath = (routes: RouteRecordRaw[]):string => {
  let str = ''
  const fn = (rs:RouteRecordRaw[]) => {
    for (let r of  rs) {
      if ((!r.children || !r.children.length) && !str) {
        if (!(r.meta && r.meta.notToRoot)) {
          str = r.path
        }
      }
      if (r.children && r.children.length && !str && !(r.meta && r.meta.notToRoot)) {
        fn(r.children)
      }
    }
  }
  fn(routes)
  return str
}

/**
 * 获取默认跳转路由
 * @param routes
 * @returns 
 */
export const getDefaultRoute = (routes: RouteRecordRaw[], router:Router) => {
  const hasRootRoute = routes.some(route => route.path === '/')
  if (!hasRootRoute) {
    router.addRoute({
      path: '/',
      redirect: findFirstUnHideRoutePath(routes),
      name: '_root',
      meta: {
        hidden: true,
        unAuth: true
      },
    })
  }
  router.addRoute({
    path: '/:pathMatch(.*)*',
    redirect: '/404',
    name: '_error',
    meta: {
      hidden: true,
      unAuth: true
    },
  })
}
/**
 * 移除默认跳转路由
 * @param router
 */
export const rmDefaultRoute = (router:Router) => {
  router.removeRoute('_root')
  router.removeRoute('_error')
}