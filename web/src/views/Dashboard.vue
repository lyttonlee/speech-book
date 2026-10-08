<template>
  <div>
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <div class="desc">管理你的有声书作品，点击进入每本书的工作空间继续制作。</div>
      </div>
      <el-button class="btn btn-primary" @click="$router.push('/studio')">＋ 新建作品</el-button>
    </div>

    <!-- 顶部四项统计 -->
    <div class="grid cols-4 mb">
      <div class="panel stat"><span class="k">作品总数</span><span class="v">{{ stats.total }}</span></div>
      <div class="panel stat"><span class="k">合成完成</span><span class="v">{{ stats.synthDone }}</span></div>
      <div class="panel stat"><span class="k">进行中</span><span class="v">{{ stats.running }}</span></div>
      <div class="panel stat">
        <span class="k">累计音频</span>
        <span class="v">{{ fmtDurationLoose(stats.totalSeconds) }}</span>
      </div>
    </div>

    <!-- 工具条：视图切换 + 状态筛选 + 排序 -->
    <div class="row between mb">
      <div class="segmented">
        <button :class="{ active: view === 'grid' }" @click="view = 'grid'">卡片视图</button>
        <button :class="{ active: view === 'list' }" @click="view = 'list'">列表视图</button>
      </div>
      <div class="row gap-2">
        <select v-model="statusFilter" class="select" style="width:150px">
          <option value="">全部状态</option>
          <option v-for="s in statusOptions" :key="s.key" :value="s.key">{{ s.label }}</option>
        </select>
        <select class="select" style="width:130px">
          <option>最近更新</option>
          <option>创建时间</option>
          <option>名称</option>
        </select>
      </div>
    </div>

    <!-- 加载态 -->
    <div v-if="store.loading" class="panel" style="padding:40px;text-align:center;color:var(--text-3)">
      加载中…
    </div>

    <!-- 空态 -->
    <div v-else-if="!works.length" class="panel" style="padding:48px;text-align:center">
      <div style="font-size:15px;margin-bottom:6px">还没有作品</div>
      <div class="tiny muted" style="margin-bottom:16px">新建一本书，从上传文本开始走完整条制作链路。</div>
      <el-button class="btn btn-primary" @click="$router.push('/studio')">＋ 新建作品</el-button>
    </div>

    <!-- 卡片视图 -->
    <div v-else-if="view === 'grid'" class="grid cols-3">
      <!-- 每张卡 = 一本书，点击进入该书工作空间 -->
      <div
        v-for="w in works"
        :key="w.id"
        class="panel work-card"
        @click="enterWork(w.id)"
      >
        <div class="work-cover"></div>
        <div class="row between">
          <h4>{{ w.name }}</h4>
          <span :class="statusBadgeClass(w.status)">
            <span class="dot"></span>{{ statusMeta(w.status).label }}
          </span>
        </div>
        <div class="work-meta">
          <span>{{ w.type || '未分类' }}</span>·<span>{{ w.chapter_count }} 章</span>
          <span class="right">{{ w.author || '佚名' }}</span>
        </div>
        <div class="progress thin"><i :style="{ width: progressOf(w) + '%' }"></i></div>

        <!-- v0.3 工作空间摘要：让人在列表页就能判断哪本书要动手 -->
        <div class="work-sum">
          <div class="ws">
            <span class="k">制作进度</span>
            <span class="v">{{ statusMeta(w.status).label }} {{ progressOf(w) }}%</span>
          </div>
          <div class="ws">
            <span class="k">已绑声纹</span>
            <span class="v">{{ boundText(w) }}</span>
          </div>
          <div class="ws">
            <span class="k">已配音</span>
            <span class="v">{{ audioText(w) }}</span>
          </div>
        </div>

        <div class="row between">
          <span class="tiny muted">点击进入工作空间</span>
          <span v-if="needsAttention(w)" class="badge warn"><span class="dot"></span>需人工介入</span>
        </div>
      </div>

      <!-- 固定入口：新建作品 -->
      <div class="panel work-card dashed" @click="$router.push('/studio')">
        <div style="text-align:center;padding:34px 0">
          <div style="font-size:26px;color:var(--accent)">＋</div>
          <div style="margin-top:8px">新建作品</div>
          <div class="tiny muted" style="margin-top:4px">上传文本 → 解析 → 配音 → 导出</div>
        </div>
      </div>
    </div>

    <!-- 列表视图 -->
    <div v-else class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>作品</th>
            <th>状态</th>
            <th>制作进度</th>
            <th>角色</th>
            <th>声纹绑定</th>
            <th>已配音</th>
            <th style="text-align:right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in works" :key="w.id">
            <td>{{ w.name }}</td>
            <td>
              <span :class="statusBadgeClass(w.status)">
                <span class="dot"></span>{{ statusMeta(w.status).label }}
              </span>
            </td>
            <td>
              <div style="width:120px">
                <div class="progress thin"><i :style="{ width: progressOf(w) + '%' }"></i></div>
                <span class="tiny muted">{{ progressOf(w) }}%</span>
              </div>
            </td>
            <td>{{ w.summary?.total_roles ?? '—' }}</td>
            <td>{{ boundText(w) }}</td>
            <td>{{ audioText(w) }}</td>
            <td style="text-align:right">
              <el-button class="btn" size="small" @click="enterWork(w.id)">进入工作空间</el-button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkStore } from '@/stores/work'
import { STATUS_META, RUNNING_STATUSES, SYNTH_DONE_STATUSES, fmtDurationLoose, statusBadgeClass, statusMeta } from '@/utils/status'
import type { Work } from '@/types'

const router = useRouter()
const store = useWorkStore()

/** 卡片 / 列表双视图 */
const view = ref<'grid' | 'list'>('grid')
const statusFilter = ref('')

/** 状态筛选下拉项（去掉回收站态，列表已排除 deleted） */
const statusOptions = Object.values(STATUS_META).filter((s) => s.key !== 'deleted')

const works = computed<Work[]>(() => store.works)

/** 顶部四项统计 */
const stats = computed(() => {
  const list = works.value
  return {
    total: list.length,
    synthDone: list.filter((w) => SYNTH_DONE_STATUSES.includes(w.status)).length,
    running: list.filter((w) => RUNNING_STATUSES.includes(w.status)).length,
    // 各书摘要里是「分钟」，这里换算回秒统一 fmtDurationLoose 处理
    totalSeconds: list.reduce((s, w) => s + (w.summary?.audio_minutes ?? 0) * 60, 0),
  }
})

onMounted(() => reload())
watch(statusFilter, () => reload())

/** 按当前筛选条件重新拉列表 */
async function reload() {
  await store.loadWorks({
    status: (statusFilter.value || undefined) as Work['status'] | undefined,
    keyword: (router.currentRoute.value.query.keyword as string) || undefined,
  })
}

/**
 * 卡片进度百分比。
 * 优先用后端算好的 summary.progress；缺失时按状态机已完成的段数兜底估算，
 * 保证页面在接口不完整时也能显示合理的进度。
 */
function progressOf(w: Work): number {
  if (w.summary?.progress != null) return Math.round(w.summary.progress)
  return Math.round((stageIndexOf(w.status) / 6) * 100)
}

/** 状态在流水线中的完成段数（0~6） */
function stageIndexOf(status: Work['status']): number {
  const map: Record<string, number> = {
    draft: 0, text_uploaded: 1, parsing: 1, pending_review: 2, review_done: 3,
    synthesizing: 4, synth_done: 5, exporting: 5, completed: 6,
  }
  return map[status] ?? 0
}

/** 「3/4」这种已绑声纹文案 */
function boundText(w: Work): string {
  const s = w.summary
  if (!s || !s.total_roles) return '—'
  return `${s.bound_roles}/${s.total_roles}`
}

/** 已配音时长文案 */
function audioText(w: Work): string {
  if (!w.summary?.audio_minutes) return '—'
  return fmtDurationLoose(w.summary.audio_minutes * 60)
}

/** 是否需要人工介入：有角色没绑音色，或还没走到合成阶段 */
function needsAttention(w: Work): boolean {
  const s = w.summary
  if (!s) return false
  return s.total_roles > 0 && s.bound_roles < s.total_roles
}

/** 进入某本书的工作空间，并记住它给侧栏「继续上一本书」用 */
function enterWork(id: number) {
  localStorage.setItem('sb_last_work_id', String(id))
  router.push(`/work/${id}`)
}
</script>
