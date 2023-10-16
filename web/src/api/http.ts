import { AxiosResponse } from 'axios'
import { App } from 'vue'
import request from './axios.config'

export interface HttpOption {
  url: string
  data?: any
  method?: string
  headers?: any
  beforeRequest?: () => void
  afterRequest?: () => void
}

export interface Response<T = any> {
  totalSize: number | 0
  count: number | 0
  code: number
  msg: string
  message: string
  data: any
  results: any
  result: any
  length: number | 0
  now: any
  path: any
  sub_net: any
  ip_used: any
  subnet_used: any
  crontab_data: any
  interval_data: any
}

function http<T = any>({
  url,
  data,
  method,
  headers,
  beforeRequest,
  afterRequest
}: HttpOption) {
  const successHandler = (res: AxiosResponse<Response<T>>) => {
    if (res.data.code === 200) {
      return res.data
    }
    if (res.data.code === 204) {
      return res.data
    }
    if (res.data.code === 401) {
      // router.push('/login')
      throw new Error('认证失败请重新登录一下')
      // throw new Error('认证失败请重新登录一下')
    }
    if (res.data.code === 404) {
      // throw new Error(res.data.msg + '请求失败，未知异常')
      return res.data
    }
    if (res.data.code === 400) {
      return res.data
    }
    if (res.data.code === 500) {
      return res.data
    }
    if (res.data.code === 201) {
      return res.data
    }
    // throw new Error(res.data.msg || '请求失败，未知异常')
    return res.data
  }
  const failHandler = (error: Response<Error>) => {
    afterRequest && afterRequest()
    throw new Error(error.msg || '请求失败，未知异常')
  }
  beforeRequest && beforeRequest()
  method = method || 'GET'
  const params = Object.assign(
    typeof data === 'function' ? data() : data || {},
    {}
  )
  return method === 'GET'
    ? request.get(url, { params }).then(successHandler, failHandler)
    : method === 'POST'
    ? request
        .post(url, params, { headers: headers })
        .then(successHandler, failHandler)
    : method === 'PUT'
    ? request
        .put(url, params, { headers: headers })
        .then(successHandler, failHandler)
    : method === 'PATCH'
    ? request
        .patch(url, params, { headers: headers })
        .then(successHandler, failHandler)
    : request.delete(url, params).then(successHandler, failHandler)
}

export function get<T = any>({
  url,
  data,
  method = 'GET',
  beforeRequest,
  afterRequest
}: HttpOption): Promise<Response<T>> {
  return http<T>({
    url,
    method,
    data,
    beforeRequest,
    afterRequest
  })
}

export function post<T = any>({
  url,
  data,
  method = 'POST',
  headers,
  beforeRequest,
  afterRequest
}: HttpOption): Promise<Response<T>> {
  return http<T>({
    url,
    method,
    data,
    headers,
    beforeRequest,
    afterRequest
  })
}

export function put({
  url,
  data,
  method = 'PUT',
  headers,
  beforeRequest,
  afterRequest
}: HttpOption): Promise<Response> {
  // @ts-ignore
  return http({
    url,
    method,
    data,
    headers,
    beforeRequest,
    afterRequest
  })
}

export function patch({
  url,
  data,
  method = 'PATCH',
  headers,
  beforeRequest,
  afterRequest
}: HttpOption): Promise<Response> {
  // @ts-ignore
  return http({
    url,
    method,
    data,
    headers,
    beforeRequest,
    afterRequest
  })
}

export function delete_fun({
  url,
  data,
  method = 'DELETE',
  headers,
  beforeRequest,
  afterRequest
}: HttpOption): Promise<Response> {
  // @ts-ignore
  return http({
    url,
    method,
    data,
    headers,
    beforeRequest,
    afterRequest
  })
}

function install(app: App): void {
  app.config.globalProperties.$http = http

  app.config.globalProperties.$get = get

  app.config.globalProperties.$post = post
}

export default {
  install,
  get,
  post
}
