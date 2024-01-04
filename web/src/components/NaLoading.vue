<template>
  <n-spin :show="show">
    <slot></slot>
    <template #description>{{ text || '加载中……' }}</template>
  </n-spin>
</template>
<script setup lang="ts">
defineProps({
  show: Boolean,
  text: String
})

</script>