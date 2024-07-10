import { RouteRecordRaw } from 'vue-router'
import naDemo from './na-demo'

export default [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login.vue'),
    meta: {
      notToRoot: true
    }
  },
  ...naDemo,
  {
    path: '/404',
    name: '404',
    component: () => import('@/views/exception/404.vue'),
    meta: {
      notToRoot: true
    }
  }
] as RouteRecordRaw[]