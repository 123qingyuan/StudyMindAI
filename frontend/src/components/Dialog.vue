<template>
  <Teleport to="body">
    <div v-if="modelValue" class="dialog-backdrop" @click.self="onBackdrop">
      <section class="dialog-card" :style="{ width }" role="dialog" aria-modal="true" :aria-label="title">
        <header class="dialog-header">
          <h2>{{ title }}</h2>
          <button v-if="showClose" class="icon-button" type="button" aria-label="关闭" :disabled="busy" @click="close"><Icon name="close" /></button>
        </header>
        <div class="dialog-body"><slot /></div>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import Icon from './Icon.vue'
const props = withDefaults(defineProps<{
  modelValue: boolean
  title?: string
  width?: string
  closeOnClickModal?: boolean
  closeOnPressEscape?: boolean
  showClose?: boolean
  busy?: boolean
}>(), { title: '', width: '560px', closeOnClickModal: true, closeOnPressEscape: true, showClose: true, busy: false })
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
function close() { if (!props.busy) emit('update:modelValue', false) }
function onBackdrop() { if (props.closeOnClickModal) close() }
function onKey(event: KeyboardEvent) { if (event.key === 'Escape' && props.closeOnPressEscape) close() }
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>
