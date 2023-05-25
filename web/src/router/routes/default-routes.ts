/**
 * 这里的 defaultRoutes 是为了在一开始对接项目的时候，后端人员还没有准备好菜单接口，导致前端开发者不能进入主页面。
 * 所以这里返回默认的菜单数据，同时也向大家说明菜单数据的数据结构。后端的菜单接口一定要按这个格式去返回json数据，否则会解析菜单失败
 */
export default [
  {
    web_path: '/index',
    name: 'Dashborad',
    routeName: 'dashborad',
    parentPath: '',
    children: [
      {
        parentPath: '/index',
        web_path: '/index/main',
        name: '主控台',
        routeName: 'home',
      },
      {
        parentPath: '/index',
        web_path: '/index/work-place',
        name: '工作台',
        routeName: 'workPlace',
      },
    ],
  },
    {
    web_path: '/tasks',
    name: '任务管理',
    routeName: 'tasks',
    parentPath: '',
    children: [
      {
        parentPath: '/task',
        web_path: '/tasks/task',
        name: '任务记录',
        routeName: 'task',
      }
    ],
  },
]
