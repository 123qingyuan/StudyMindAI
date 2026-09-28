<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'
import AppLayout from './components/AppLayout.vue'
const route = useRoute(); const router = useRouter(); const auth = useAuthStore()
function unauthorized() {
  auth.clear()
  if (route.path !== '/login') void router.replace({ path: '/login', query: { redirect: route.fullPath } })
}
onMounted(() => { window.addEventListener('studymind:unauthorized', unauthorized); void auth.hydrate() })
onUnmounted(() => window.removeEventListener('studymind:unauthorized', unauthorized))
</script>
<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <RouterView v-if="route.meta.public" />
  <AppLayout v-else><RouterView /></AppLayout>
</template>
