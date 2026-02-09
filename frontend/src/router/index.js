import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/datasource',
    name: 'DataSource',
    component: () => import('@/views/DataSource.vue'),
    meta: { title: '数据管理' }
  },
  {
    path: '/sync',
    name: 'DataSync',
    component: () => import('@/views/DataSync.vue'),
    meta: { title: '数据同步' }
  },
  {
    path: '/metadata',
    name: 'MetadataInit',
    component: () => import('@/views/MetadataInit.vue'),
    meta: { title: '元数据初始化' }
  },
  {
    path: '/review',
    name: 'Review',
    component: () => import('@/views/Review.vue'),
    meta: { title: '复盘分析' }
  },
  {
    path: '/review/create',
    name: 'CreateReview',
    component: () => import('@/views/CreateReview.vue'),
    meta: { title: '创建复盘' }
  },
  {
    path: '/review/result/:id',
    name: 'ReviewResult',
    component: () => import('@/views/ReviewResult.vue'),
    meta: { title: '复盘结果' }
  },
  {
    path: '/report/:id',
    name: 'Report',
    component: () => import('@/views/Report.vue'),
    meta: { title: '分析报告' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'DaydayUp'} - 可视化自动复盘系统`
  next()
})

export default router

