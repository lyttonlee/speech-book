<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>有声书智能制作平台</h2>
      <p class="sub">POC · 解析 + 样章合成</p>
      <el-form @submit.prevent="onLogin">
        <el-form-item>
          <el-input v-model="email" placeholder="邮箱" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="onLogin" style="width: 100%">
          登录
        </el-button>
      </el-form>
      <el-divider>或</el-divider>
      <el-button :loading="loading" @click="onDemo" style="width: 100%">
        快速体验（自动登录演示账号）
      </el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const email = ref('')
const password = ref('')
const loading = ref(false)
const router = useRouter()
const user = useUserStore()

async function onLogin() {
  if (!email.value || !password.value) return ElMessage.warning('请输入邮箱和密码')
  loading.value = true
  try {
    await user.login(email.value, password.value)
    router.push('/')
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

async function onDemo() {
  loading.value = true
  try {
    await user.quickDemo()
    router.push('/')
  } catch {
    /* ignore */
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.login-card { width: 360px; padding: 8px 12px; }
.sub { color: #909399; margin-top: -8px; }
h2 { margin-bottom: 4px; }
</style>
