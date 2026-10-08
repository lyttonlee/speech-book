<template>
  <div v-if="modelValue" class="modal-mask" @click.self="close">
    <div class="modal">
      <div class="modal-head">
        <h3>标签管理</h3>
        <span class="tiny muted">作用于所有音色</span>
        <button class="modal-close" @click="close">✕</button>
      </div>
      <div class="modal-body">
        <!-- 已有标签：改名 / 改色 / 删除（删除后音色上的引用自动解除） -->
        <div v-for="t in tags" :key="t.id" class="chapter-item">
          <i
            class="cdot"
            :style="{ background: t.color || '#94a3b8', width: '12px', height: '12px', borderRadius: '99px', flex: 'none' }"
          ></i>
          <b class="sm">{{ t.value }}</b>
          <span class="tiny muted">{{ t.usage_count }} 个音色</span>
          <div class="right row gap-2">
            <button class="icon-btn" @click="rename(t)">✎</button>
            <button class="icon-btn danger" @click="remove(t)">🗑</button>
          </div>
        </div>
        <div v-if="!tags.length" class="tiny muted">还没有标签，先在下面新建一个</div>

        <hr class="divider" />
        <label class="label">新建标签</label>
        <div class="input-group mt-2">
          <input v-model="name" class="input" placeholder="标签名称，如：少年音" @keyup.enter="add" />
          <el-button class="btn" :loading="busy" @click="add">添加</el-button>
        </div>
        <!-- 色板：与设计稿的 7 色一致 -->
        <div class="row gap-2 mt-2">
          <span
            v-for="c in COLOR_PICKS" :key="c"
            :class="['c-dot-pick', c, { sel: color === c }]"
            @click="color = c"
          ></span>
        </div>
      </div>
      <div class="modal-foot">
        <el-button class="btn btn-ghost" @click="close">取消</el-button>
        <el-button class="btn btn-primary" @click="close">完成</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as voicesApi from '@/api/voices'
import type { VoiceTag } from '@/types'

/**
 * 标签管理弹窗（design/voice-library.html 的 #tag-modal）。
 *
 * 标签是全局维度（scope=global）的，改完影响所有音色。
 * 每次写操作都 emit('changed') 让父组件重拉列表，弹窗自己不持有数据源。
 */

// 只声明不接局部变量：模板里直接用 modelValue / tags，无需 props 转发
defineProps<{
  modelValue: boolean
  tags: VoiceTag[]
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  /** 标签有增删改名，父组件据此重拉音色 + 标签列表 */
  changed: []
}>()

const name = ref('')
const color = ref('c-sky')
const busy = ref(false)
/** 色板：与设计稿的 7 色一致 */
const COLOR_PICKS = ['c-sky', 'c-violet', 'c-rose', 'c-amber', 'c-emerald', 'c-cyan', 'c-slate']

function close() {
  name.value = ''
  emit('update:modelValue', false)
}

/** 建全局标签：dim=timbre（音色维度），scope=global（对所有作品生效） */
async function add() {
  if (!name.value.trim()) {
    ElMessage.warning('请输入标签名称')
    return
  }
  busy.value = true
  try {
    await voicesApi.createTag({
      dim: 'timbre',
      value: name.value.trim(),
      color: color.value,
      scope: 'global',
    })
    name.value = ''
    emit('changed')
    ElMessage.success('标签已创建')
  } finally {
    busy.value = false
  }
}

async function rename(t: VoiceTag) {
  try {
    const { value } = await ElMessageBox.prompt('新的标签名称', '重命名标签', {
      inputValue: t.value, confirmButtonText: '保存', cancelButtonText: '取消',
    })
    if (!value) return
    await voicesApi.updateTag(t.id, { value })
    emit('changed')
    ElMessage.success('已重命名')
  } catch { /* 用户取消 */ }
}

/** 删除标签定义：引用自动解除，所以删前先提示清楚影响面 */
async function remove(t: VoiceTag) {
  try {
    await ElMessageBox.confirm(
      `删除标签「${t.value}」，所有音色上的引用会自动解除。确定吗？`,
      '删除标签',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await voicesApi.deleteTag(t.id)
  emit('changed')
  ElMessage.success('标签已删除')
}
</script>
