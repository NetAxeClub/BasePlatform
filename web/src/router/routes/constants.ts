import { LAYOUT } from '@/store/keys'

export const constantRoutes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: {
      hidden: true,
    },
  },
  {
    path: '/redirect',
    component: LAYOUT,
    meta: {
      hidden: true,
      noShowTabbar: true,
    },
    children: [
      {
        path: '/redirect/:path(.*)*',
        component: () => import('@/views/redirect/index.vue'),
      },
    ],
  },
  {
    path: '/personal',
    name: 'personal',
    component: LAYOUT,
    meta: {
      title: '个人中心',
      hidden: true,
    },
    children: [
      {
        path: 'info',
        component: () => import('@/views/personal/index.vue'),
        meta: {
          title: '个人中心',
        },
      },
    ],
  },
  {
    path: '/404',
    name: '404',
    component: () => import('@/views/exception/404.vue'),
    meta: {
      hidden: true,
    },
  },
  {
    path: '/500',
    name: '500',
    component: () => import('@/views/exception/500.vue'),
    meta: {
      hidden: true,
    },
  },
  {
    path: '/403',
    name: '403',
    component: () => import('@/views/exception/403.vue'),
    meta: {
      hidden: true,
    },
  },
    {
        path: '/ssh',
        name: 'ssh',
        component: () => import('@/views/ssh.vue'),
        hidden: true,
        meta: {
            requireAuth: true,
            index: '/ssh',
            hidden: true,
        }
    },
    {
      path: '/server_ssh',
      name: 'server_ssh',
      component: () => import('@/views/server_ssh.vue'),
      hidden: true,
      meta: {
          requireAuth: true,
          index: '/server_ssh',
          hidden: true,
      }
  },
]
