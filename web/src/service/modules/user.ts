import request from '../request'
/**
 * 获取权限路由
 * @param params
 * @returns 
 */
export const getPermissionRoute = (params:any) => {
  return request.get('/rbac/system/menu/web_router/', {params})
}

/**
 * 登录
 * @param data
 * @returns 
 */
export const login = (data:any) => {
  return request.post('/rbac/login/', data)
}

/**
 * 退出登录
 * @param data
 * @returns 
 */
export const logout = (data:any) => {
  return request.post('/rbac/logout/', data)
}