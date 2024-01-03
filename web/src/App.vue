<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN">
    <n-global-style/>
    <n-loading-bar-provider>
      <n-dialog-provider>
        <n-message-provider>
          <n-notification-provider>
            <Main/>
          </n-notification-provider>
        </n-message-provider>
      </n-dialog-provider>
    </n-loading-bar-provider>
  </n-config-provider>
</template>
<script setup lang="ts">
import { zhCN, dateZhCN } from 'naive-ui'
import Main from './layout/Main.vue'
</script>
<style scoped>
</style>
