<template>
  <!-- ==================== 5. 角色与声纹绑定 ==================== -->
  <section class="section anchor" id="cast">
    <div class="sec-head">
      <div>
        <h2>角色与声纹绑定</h2>
        <div class="desc">解析出的角色 → 音色映射，全部字段可人工覆盖，改动即时生效并重合成。</div>
      </div>
    </div>

    <!-- 待处理警示：未绑定 / 低置信聚合提示 -->
    <div v-if="store.pendingCount" class="notice">
      <span class="ni" style="color:var(--warn)">!</span>
      <span class="nt">
        <b>{{ store.unboundRoles.length }} 个角色未绑定音色</b>，现按默认旁白合成；
        另有 {{ lowConfTotal }} 段说话人识别置信度偏低，建议先复核再提交合成。
      </span>
      <el-button class="btn btn-sm" @click="store.autoBind(workId)">补绑未绑定</el-button>
      <el-button class="btn btn-sm btn-ghost" @click="emit('go', 'chapters')">处理 {{ lowConfTotal }} 条低置信</el-button>
    </div>

    <div class="grid" style="grid-template-columns:1.55fr 1fr;align-items:start">
      <CastBinding :work-id="workId" :roles="store.roles" :bindings="store.bindings" />

      <div class="col gap-4">
        <!-- 绑定预览：用选中角色的音色试听一段示例 -->
        <div class="panel">
          <div class="card-h"><h3>绑定预览</h3><span class="sub">当前角色：{{ previewRoleName }}</span></div>
          <div class="player mt-2">
            <button class="play" @click="previewRole">
              <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
            </button>
            <div class="wave">
              <i v-for="(h, i) in previewWave" :key="i" :style="{ height: h + '%' }"></i>
            </div>
            <div class="time">00:00 / 00:03</div>
          </div>
          <ul class="tiny muted mt" style="padding-left:18px;margin:10px 0 0;line-height:2">
            <li v-for="r in store.roles.slice(0, 5)" :key="r.id">
              {{ r.name }} → {{ r.bound_voice_name || '未绑定' }}
              <span v-if="r.params && (r.params as any).speed">
                · 语速 ×{{ (r.params as any).speed }}
              </span>
            </li>
          </ul>
        </div>

        <!-- 情绪 → 韵律映射（EmotionIR，引擎能力探测后自动降级） -->
        <div class="panel">
          <div class="card-h"><h3>情绪 → 韵律映射</h3><span class="sub">EmotionIR</span></div>
          <table class="table">
            <thead><tr><th>情绪</th><th>语速</th><th>音高</th><th class="right"></th></tr></thead>
            <tbody>
              <tr v-for="e in EMOTION_IR" :key="e.name">
                <td>{{ e.name }}</td>
                <td class="mono">{{ e.speed }}</td>
                <td class="mono">{{ e.pitch }}</td>
                <td class="right">
                  <el-button class="btn btn-sm" @click="ElMessage.info('POC 阶段映射为内置常量，生产由引擎能力探测决定')">改</el-button>
                </td>
              </tr>
            </tbody>
          </table>
          <p class="hint">由引擎能力探测自动降级；本地离线引擎不支持精确音高时仅保留语速。</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
/**
 * 角色与声纹绑定区块（design/workspace.html §5）。
 *
 * 左栏是角色卡 → 音色下拉的逐条绑定（复用 CastBinding 子组件）；
 * 右栏是「绑定预览」（选中角色即时试听）+ EmotionIR 映射表（只读）。
 * 绑定改动由 CastBinding 自己调 store.setBindings，本组件只负责编排与事件转发。
 */

import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useWorkStore } from '@/stores/work'
import CastBinding from './CastBinding.vue'
import * as voicesApi from '@/api/voices'
import { mkBars } from '@/utils/format'

const props = defineProps<{ workId: number }>()
const emit = defineEmits<{ go: [id: string] }>()

const store = useWorkStore()

/** 情绪 → 韵律映射表（POC 内置常量；生产由引擎能力探测结果决定） */
const EMOTION_IR = [
  { name: '急切', speed: '+15%', pitch: '+2st' },
  { name: '难过', speed: '-10%', pitch: '-1st' },
  { name: '坚定', speed: '+5%', pitch: '0' },
  { name: '担忧', speed: '-5%', pitch: '-1st' },
]

/** 全书低置信片段总数（聚合警示文案要用） */
const lowConfTotal = computed(() => store.chapters.reduce((s, c) => s + c.low_conf_count, 0))

/** 当前选中的角色名（没有选中时展示「未选择角色」） */
const previewRoleName = computed(
  () => store.roles.find((r) => r.id === store.selectedRoleId)?.name ?? '未选择角色',
)

/** 预览波形：确定性正弦，避免每次重渲染乱跳 */
const previewWave = computed(() => mkBars(40, 1.0))

/** 用选中角色的音色试听一句示例；没绑定音色时提示先去绑定 */
async function previewRole() {
  const r = store.roles.find((x) => x.id === store.selectedRoleId)
  if (!r?.bound_voice_id) {
    ElMessage.warning('请先选中一个已绑定音色的角色')
    return
  }
  const res = await voicesApi.previewVoice(r.bound_voice_id, `${r.name}的台词示例`)
  new Audio(res.audio_url).play().catch(() => ElMessage.warning('浏览器阻止了自动播放，请手动点击'))
}
</script>
