import useUserStore from '@/store/modules/user'
import usePermissionStore from '@/store/modules/permission'
import router from '..'

const whiteRoutes: string[] = ['/login', '/404', '/403', '/500']

function usePermissionGuard() {
  router.beforeEach(async (to) => {
    if (whiteRoutes.includes(to.path)) {
      return true
    }
    const userStore = useUserStore()
    // console.log(userStore)
    // console.log(userStore.isTokenExpire())
    // if (userStore.isTokenExpire()) {
    //   return {
    //     path: '/login',
    //     query: { redirect: to.fullPath },
    //   }
    // }
    const permissionStore = usePermissionStore()
    // 判断是否空路由
    const isEmptyRoute = permissionStore.isEmptyPermissionRoute()
    if (isEmptyRoute && to.path!='/ssh') {
      await permissionStore.initPermissionRoute()
      return { ...to, replace: true }
    }
    return true
  })
}

export default usePermissionGuard
