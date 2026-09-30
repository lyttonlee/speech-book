import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as authApi from '@/api/auth'
import type { User } from '@/types'

const TOKEN_KEY = 'sb_token'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const profile = ref<User | null>(null)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem(TOKEN_KEY, t)
  }

  async function login(email: string, password: string) {
    const data = await authApi.login(email, password)
    setToken(data.access_token)
    return data
  }

  // POC 便捷入口：自动注册并登录演示账号
  async function quickDemo() {
    try {
      await authApi.register('demo@demo.com', 'demo1234', '体验用户')
    } catch {
      /* 已存在则忽略 */
    }
    await login('demo@demo.com', 'demo1234')
  }

  function logout() {
    token.value = ''
    profile.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, profile, login, quickDemo, logout }
})
