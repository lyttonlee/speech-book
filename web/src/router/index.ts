import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

/**
 * 路由表（对照 design/ 页面清单）。
 * AppLayout 承载所有需登录页面的统一框架（侧栏 + 顶栏）。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    {
      path: '/',
      component: () => import('@/components/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        { path: '', redirect: '/dashboard' },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '工作台' },
        },
        {
          // 单书工作空间：核心页，对应 design/workspace.html
          path: 'work/:id',
          name: 'workspace',
          component: () => import('@/views/WorkSpace.vue'),
          meta: { title: '作品工作空间' },
        },
        {
          // 保留的四步向导，用于「从零开始」场景（DESIGN_SPEC §5.5）
          path: 'studio',
          name: 'studio',
          component: () => import('@/views/Studio.vue'),
          meta: { title: '新建作品' },
        },
        {
          path: 'voices',
          name: 'voices',
          component: () => import('@/views/VoiceLibrary.vue'),
          meta: { title: '音色库' },
        },
        {
          path: 'settings',
          name: 'settings',
          component: () => import('@/views/Settings.vue'),
          meta: { title: '设置' },
        },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const user = useUserStore()
  if (to.meta.requiresAuth && !user.token) return { name: 'login' }
  if (to.name === 'login' && user.token) return { name: 'dashboard' }
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || ''
  document.title = title ? `${title} · 有声书工作台` : '有声书工作台'
})

export default router
