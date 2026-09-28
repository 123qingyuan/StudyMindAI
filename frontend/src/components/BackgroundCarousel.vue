<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
const active=ref(0);let timer=0
const scenes=[
 {name:'晨雾山峦',tone:'专注从安静开始'},
 {name:'星海微光',tone:'在知识里看见更远'},
 {name:'湖畔晚霞',tone:'让每次积累都有回响'},
 {name:'青蓝极光',tone:'保持好奇，持续探索'}
]
onMounted(()=>{timer=window.setInterval(()=>active.value=(active.value+1)%scenes.length,12000)})
onBeforeUnmount(()=>window.clearInterval(timer))
</script>
<template><div class="background-carousel" aria-hidden="true"><div v-for="(_,i) in scenes" :key="i" class="background-scene" :class="[`scene-${i+1}`,{active:active===i}]"><span class="orb orb-a"></span><span class="orb orb-b"></span><span class="landscape landscape-back"></span><span class="landscape landscape-front"></span><span class="stars"></span></div><div class="background-wash"></div><div class="background-label"><strong>{{scenes[active].name}}</strong><span>{{scenes[active].tone}}</span></div><div class="background-dots"><span v-for="(_,i) in scenes" :key="i" :class="{active:active===i}"></span></div></div></template>