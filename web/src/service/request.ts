import hooks from '@/hooks'
import axios, { AxiosRequestConfig } from 'axios'


const request = axios.create({
  timeout: 10 * 60 * 1000
})

request.interceptors.request.use((config) => hooks.request.requestHook(config))
request.interceptors.response.use((response) => {
  if (response.config.responseType === 'blob') {
    return Promise.resolve(response)
  }
  return hooks.request.responseHook(response)
}, (error) => hooks.request.responseError(error))

/**
 * 格式化disposition
 * @param str
 * @returns 
 */
function _parseDisposition (str:string) {
  let arr1 = str.split(';')
  let obj:any = {}
  for (let item of arr1) {
    let ar = item.replace(/"/g, '').split('=')
    obj[ar[0]] = ar[1] || ''
  }
  return obj
}

/**
 * 文件导出，异步请求方式
 * @param opts
 * @param fileName
 */
function _exportFileByAjax (opts: AxiosRequestConfig, fileName?: string) {
  return new Promise((resolve, reject) => {
    request({
      ...opts,
      responseType: 'blob'
    }).then(async res => {
      if (res.headers['content-type'] === 'application/json') { // 返回json时，接口处理有异常
        let text = await res.data.text()
        let data = JSON.parse(text)
        let msg = data.error || data.message || '未知错误'
        return reject(msg)
      } else { // 下载文件
        // 获取文件名
        const filename = fileName || decodeURIComponent(_parseDisposition(res.headers['content-disposition'])['filename'])
        const tmpUrl = URL.createObjectURL(res.data)
        const a = document.createElement('a')
        a.setAttribute('href', tmpUrl)
        a.setAttribute('download', filename)
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(tmpUrl)
      }
      return resolve('')
    }, error => {
      return reject(error)
    })
  })
}

/**
 * 导出文件
 */
export const exportFile = (opts: AxiosRequestConfig, fileName?: string, _type:string = 'async') => {
  if (_type === 'async') {
    return _exportFileByAjax(opts, fileName)
  }
  return Promise.resolve()
}
export default request
