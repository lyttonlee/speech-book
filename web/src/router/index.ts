import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    { path: '/', name: 'studio', component: () => import('@/views/Studio.vue'), meta: { requiresAuth: true } },
  ],
})

router.beforeEach((to) => {
  const user = useUserStore()
  if (to.meta.requiresAuth && !user.token) return { name: 'login' }
  if (to.name === 'login' && user.token) return { name: 'studio' }
  return true
})

export default router
