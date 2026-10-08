<template>
  <!-- 应用框架：248px 侧边导航 + 64px 顶栏 + 内容区（DESIGN_SPEC §4） -->
  <div class="app-shell">
    <aside class="app-side">
      <div class="side-brand">
        <span class="badge acc">SB</span>
        <span>有声书工作台</span>
      </div>

      <!-- 创作 -->
      <div class="side-group">
        <div class="side-group-title">创作</div>
        <router-link class="side-link" to="/dashboard">
          <span>◈</span><span>工作台</span>
        </router-link>
        <router-link class="side-link" to="/studio">
          <span>✦</span><span>新建作品</span>
        </router-link>
        <!-- 已进入过某本书时，显示「继续上一本书」快捷入口 -->
        <router-link v-if="lastWorkId" class="side-link" :to="`/work/${lastWorkId}`">
          <span>▤</span><span>继续上一本书</span>
        </router-link>
      </div>

      <!-- 资源 -->
      <div class="side-group">
        <div class="side-group-title">资源</div>
        <router-link class="side-link" to="/voices">
          <span>♫</span><span>音色库</span>
        </router-link>
      </div>

      <!-- 账户 -->
      <div class="side-group">
        <div class="side-group-title">账户</div>
        <router-link class="side-link" to="/settings">
          <span>⚙</span><span>设置</span>
        </router-link>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <!-- 全局搜索：检索作品名，回车跳转工作台并按 keyword 过滤 -->
        <input
          v-model="keyword"
          class="input"
          style="max-width: 320px"
          placeholder="搜索作品 / 角色 / 任务"
          @keyup.enter="doSearch"
        />

        <div style="flex: 1"></div>

        <!-- 常驻任务状态徽标：有任务在跑时呼吸点亮 -->
        <span v-if="runningCount" class="badge info">
          <i class="dot"></i> {{ runningCount }} 个任务运行中
        </span>

        <el-button class="btn btn-primary" @click="$router.push('/studio')">
          ＋ 新建作品
        </el-button>

        <el-dropdown trigger="click" @command="onUserCommand">
          <span class="side-link" style="padding: 6px 10px">
            <span>◐</span><span>{{ nickname }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings">账号设置</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import * as authApi from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const keyword = ref('')
/** 最近进入过的工作空间 id，用于侧栏「继续上一本书」 */
const lastWorkId = ref<number | null>(null)

const nickname = computed(() => userStore.profile?.nickname || '我的账号')

/**
 * 演示用途的运行中任务数。
 * 生产应接 GET /tasks?status=running 轮询，或由 SSE 汇总到一个全局 store。
 */
const runningCount = computed(() => 0)

onMounted(() => {
  // 恢复上次进入的作品（localStorage 记住的工作空间）
  const cached = localStorage.getItem('sb_last_work_id')
  lastWorkId.value = cached ? Number(cached) : null
  if (!userStore.profile) loadProfile()
})

/** 拉取当前用户信息（顶栏昵称与克隆合规状态） */
async function loadProfile() {
  try {
    userStore.profile = await authApi.me()
  } catch {
    /* 未登录或接口异常时保持匿名展示 */
  }
}

function doSearch() {
  router.push({ path: '/dashboard', query: { keyword: keyword.value } })
}

function onUserCommand(cmd: string) {
  if (cmd === 'settings') {
    router.push('/settings')
  } else if (cmd === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>
