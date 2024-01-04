import request, { exportFile } from '@/service/request'
import { AxiosRequestConfig, AxiosResponse } from 'axios'
import { App, inject } from 'vue'

const requestKey = Symbol()

type RequestType = {
  get<T = any, R = AxiosResponse<T>, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
  delete<T = any, R = AxiosResponse<T>, D = any>(url: string, config?: AxiosRequestConfig<D>): Promise<R>;
  post<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
  put<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>;
  patch<T = any, R = AxiosResponse<T>, D = any>(url: string, data?: D, config?: AxiosRequestConfig<D>): Promise<R>
  exportFile(opts: AxiosRequestConfig, fileName?: string, _type?: string):Promise<any>
}

const install = (app: App<Element>) => {
  app.provide(requestKey, {
    post: request.post,
    get: request.get,
    put: request.put,
    delete: request.delete,
    patch: request.patch,
    exportFile: exportFile
  } as RequestType)
}

export const useRequest = () => {
  return inject(requestKey) as RequestType
}


export default {
  install
}