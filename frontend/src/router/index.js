import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    redirect: '/',
    children: [
      {
        path: '',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页' }
  },
  {
        path: 'datasource',
    name: 'DataSource',
    component: () => import('@/views/DataSource.vue'),
    meta: { title: '数据管理' }
  },
  {
        path: 'sync',
    name: 'DataSync',
    component: () => import('@/views/DataSync.vue'),
    meta: { title: '数据同步' }
  },
  {
        path: 'metadata',
    name: 'MetadataInit',
    component: () => import('@/views/MetadataInit.vue'),
        meta: { title: '元数据' }
  },
  {
        path: 'review',
    name: 'Review',
    component: () => import('@/views/Review.vue'),
        meta: { title: '每日复盘' }
  },
  {
        path: 'review/create',
    name: 'CreateReview',
    component: () => import('@/views/CreateReview.vue'),
    meta: { title: '创建复盘' }
  },
  {
        path: 'review/result/:id',
    name: 'ReviewResult',
    component: () => import('@/views/ReviewResult.vue'),
    meta: { title: '复盘结果' }
  },
  {
        path: 'delivery/upload',
        name: 'DeliveryUpload',
        component: () => import('@/views/DeliveryUpload.vue'),
        meta: { title: '上传交割单' }
      },
  {
        path: 'delivery/list',
    name: 'DeliveryList',
    component: () => import('@/views/DeliveryList.vue'),
    meta: { title: '交割单列表' }
  },
  {
        path: 'admin/factors',
    name: 'FactorList',
    component: () => import('@/views/admin/FactorList.vue'),
    meta: { title: '因子管理' }
  },
  {
        path: 'admin/expressions',
    name: 'ExpressionList',
    component: () => import('@/views/admin/ExpressionList.vue'),
    meta: { title: '表达式配置' }
  },
  {
        path: 'cycle',
    name: 'CycleManagement',
    component: () => import('@/views/CycleManagement.vue'),
        meta: { title: '周期管理' }
  },
  {
        path: 'notes',
    name: 'StockNotes',
    component: () => import('@/views/StockNotes.vue'),
        meta: { title: '炒股笔记' }
  }
]
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
