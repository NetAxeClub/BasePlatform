import Axios, { AxiosRequestConfig, AxiosResponse } from 'axios'
import qs from 'qs'
import Cookies from 'js-cookie'
import { ADMIN_WORK_USER_INFO_KEY } from '@/store/keys'
export const baseURL = '/base_platform'

export const CONTENT_TYPE = 'Content-Type'

export const FORM_URLENCODED =
  'application/x-www-form-urlencoded; charset=UTF-8'

export const APPLICATION_JSON = 'application/json; charset=UTF-8'

export const TEXT_PLAIN = 'text/plain; charset=UTF-8'

const service = Axios.create({
  // baseURL,
  timeout: 10 * 60 * 1000
})
const userInfo = localStorage.getItem(ADMIN_WORK_USER_INFO_KEY)
if (userInfo !== null) {
  const parsedUserInfo = JSON.parse(userInfo)

  const userName = parsedUserInfo['userName']
  service.interceptors.request.use(
    (config: AxiosRequestConfig) => {
      !config.headers && (config.headers = {})
      if (!config.headers.Authorization && Cookies.get('netops-token')) {
        config.headers.Authorization = Cookies.get('netops-token')
          ? Cookies.get('netops-token')
          : ''
      }
      if (!config.headers.UserName) {
        config.headers.UserName = userName ? userName : ''
      }

      if (!config.headers[CONTENT_TYPE]) {
        config.headers[CONTENT_TYPE] = APPLICATION_JSON
      }
      if (config.headers[CONTENT_TYPE] === FORM_URLENCODED) {
        config.data = qs.stringify(config.data)
      }
      return config
    },
    (error) => {
      return Promise.reject(error.response)
    }
  )
} else {
  service.interceptors.request.use(
    (config: AxiosRequestConfig) => {
      !config.headers && (config.headers = {})
      if (!config.headers.Authorization && Cookies.get('netops-token')) {
        config.headers.Authorization = Cookies.get('netops-token')
          ? Cookies.get('netops-token')
          : ''
      }
      if (!config.headers.UserName) {
        config.headers.UserName = ''
      }

      if (!config.headers[CONTENT_TYPE]) {
        config.headers[CONTENT_TYPE] = APPLICATION_JSON
      }
      if (config.headers[CONTENT_TYPE] === FORM_URLENCODED) {
        config.data = qs.stringify(config.data)
      }
      return config
    },
    (error) => {
      return Promise.reject(error.response)
    }
  )
  // 处理 userInfo 为 null 的情况，例如设置默认值或显示提示信息
}
// const user_name = JSON.parse(localStorage.getItem(ADMIN_WORK_USER_INFO_KEY))['userName']

service.interceptors.response.use(
  (response: AxiosResponse): AxiosResponse => {
    if (response.status === 200) {
      return response
    }
    if (response.status === 201) {
      return response
    }
    if (response.status === 204) {
      return response
    } else {
      throw new Error(response.status.toString())
    }
  },
  (error) => {
    // 如何在全局解决这个阶段的报错呢？给前端用户以友好提示
    if (import.meta.env.MODE === 'development') {
      console.log(error)
    }
    alert('发生了一个错误，请稍后重试')
    return Promise.reject({ code: 500, msg: '服务器异常，请稍后重试…' })
  }
)

export default service
