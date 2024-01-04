<template>
  <RouterView/>
</template>
<script setup lang="ts">
import { useLoadingBar, useMessage, useNotification, useDialog } from 'naive-ui'
import {GLOABAL} from '@/utils/index'
import {useRouter} from 'vue-router'
const loadingBar = useLoadingBar()
const router = useRouter()

GLOABAL.message = useMessage()
GLOABAL.notification = useNotification()
GLOABAL.dialog = useDialog()

router.beforeEach(() => {
  loadingBar.start()
})

router.afterEach(() => {
  loadingBar.finish()
})
</script>