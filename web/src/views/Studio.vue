<template>
  <div class="studio">
    <!-- ============ 页头：返回 + 当前作品 ============ -->
    <div class="page-head">
      <div>
        <h1>{{ title }} · 工作室</h1>
        <div class="desc">四步走完从文本到成片：上传 → 解析 → 绑定 → 合成</div>
      </div>
      <el-button class="btn btn-ghost" @click="$router.push('/dashboard')">← 返回工作台</el-button>
    </div>

    <!-- ============ 步骤条（点任意一步可来回切） ============ -->
    <div class="panel mb">
      <div class="stepper">
        <template v-for="(s, i) in STEPS" :key="s.key">
          <div
            :class="['step', { active: step === i + 1, done: step > i + 1 }]"
            @click="go(i + 1)"
          >
            <div class="num">{{ step > i + 1 ? '✓' : i + 1 }}</div>
            <div class="txt"><b>{{ s.title }}</b><span>{{ s.sub }}</span></div>
          </div>
          <div v-if="i < STEPS.length - 1" class="bar"></div>
        </template>
      </div>
    </div>

    <!-- ============ 步骤一：上传文本 ============ -->
    <StepUpload v-if="step === 1" @parsed="onParsed" />

    <!-- ============ 步骤二：解析确认 ============ -->
    <StepParse
      v-if="step >= 2 && workId" v-show="step === 2"
      :work-id="workId" @next="go(3)"
    />

    <!-- ============ 步骤三：角色绑定 ============ -->
    <StepCast
      v-if="step >= 3 && workId" v-show="step === 3"
      :work-id="workId" @next="go(4)"
    />

    <!-- ============ 步骤四：合成试听 ============ -->
    <StepSynth v-if="step === 4 && workId" :work-id="workId" />

    <!-- 走到最后一步，给一条通往单书工作空间的出口 -->
    <div v-if="step === 4 && workId" class="row between wrap mt-6">
      <span class="tiny muted">合成完成后可进入工作空间做校对、留痕与导出。</span>
      <el-button class="btn btn-primary" @click="$router.push(`/work/${workId}`)">
        进入作品工作空间 →
      </el-button>
    </div>

    <p class="hint mt-8">
      交互说明：点击顶部步骤条可来回切换；解析与合成的进度由 SSE 推送；
      任务失败可用「重试上次任务」按当前范围重跑。
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useWorkStore } from '@/stores/work'
import StepUpload from '@/components/studio/StepUpload.vue'
import StepParse from '@/components/studio/StepParse.vue'
import StepCast from '@/components/studio/StepCast.vue'
import StepSynth from '@/components/studio/StepSynth.vue'

/**
 * 新建作品向导（design/studio.html 的 Vue 实现，DESIGN_SPEC §5.5）。
 *
 * 只做三件事：管当前步号、管作品 id、把四块步骤内容拼起来。
 * 每块内容各自一个组件（components/studio/Step*.vue），避免单文件过长。
 */

const store = useWorkStore()

/** 步骤条定义：标题 + 副标题（与设计稿一致） */
const STEPS = [
  { key: 'upload', title: '上传文本', sub: '粘贴 / 导入' },
  { key: 'parse', title: '解析确认', sub: '角色 / 情绪' },
  { key: 'cast', title: '角色绑定', sub: '音色分配' },
  { key: 'synth', title: '合成试听', sub: '样章 / 全本' },
]

/** 当前步号 1~4 */
const step = ref(1)
/** 建好的作品 id（步骤二起使用，步骤一结束才产生） */
const workId = ref<number | null>(null)

const title = computed(() => store.currentWork?.name || '新建作品')

/**
 * 步骤一解析完成 → 记住作品 id 并推进到步骤二。
 * @param work 后端返回的作品对象（StepUpload 里刚建的那一本）
 */
function onParsed(work: { id: number }) {
  workId.value = work.id
  step.value = 2
}

/**
 * 切换步骤。
 * 规则：前三步必须已有作品才能进（否则只能停在步骤一），
 * 且不回退到「没有产物」的步骤之后——重复解析由 StepParse 自己处理。
 */
function go(n: number) {
  if (!workId.value && n > 1) return
  step.value = Math.min(STEPS.length, Math.max(1, n))
}
</script>
