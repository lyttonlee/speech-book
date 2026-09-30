import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Role, Segment, Work, Voice } from '@/types'

export const useWorkStore = defineStore('work', () => {
  const currentWork = ref<Work | null>(null)
  const roles = ref<Role[]>([])
  const segments = ref<Segment[]>([])
  const voices = ref<Voice[]>([])

  function setWork(w: Work) {
    currentWork.value = w
  }
  function setRoles(r: Role[]) {
    roles.value = r
  }
  function setSegments(s: Segment[]) {
    segments.value = s
  }
  function setVoices(v: Voice[]) {
    voices.value = v
  }

  return { currentWork, roles, segments, voices, setWork, setRoles, setSegments, setVoices }
})
