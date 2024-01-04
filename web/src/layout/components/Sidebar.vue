<template>
  <n-menu
    :collapsed="props.collapsed"
    :collapsed-width="64"
    :collapsed-icon-size="22"
    :options="menuOptions"
    key-field="name"
    label-field="title"
    children-field="children"
    @update:value="handleUpdateValue"
    v-model:value="selectedKey"
  >
  </n-menu>
</template>
<script setup lang="ts">
import { useUserStore } from '@/store'
import { VNode, computed, h, watchEffect, ref } from 'vue'
import { RouteRecordRaw, useRoute, useRouter } from 'vue-router'
import {NIcon} from 'naive-ui'
import NaIcon from '@/components/NaIcon.vue'

const route = useRoute()
const router = useRouter()
const selectedKey = ref()

type MenuOption = {
  name: any
  path: string
  icon: () => VNode
  title: any
  children?: MenuOption[]
}

const { permissionRoute } = useUserStore()

const props = defineProps({
  collapsed: Boolean
})

const menuOptions = computed(() => {
  const fn = (routes: RouteRecordRaw[]) => {
    const tempArr:MenuOption[] = []
    routes.forEach(item => {
      if (item.meta && item.meta.hidden) return
      let tempR:MenuOption = {
        name: item.name,
        path: item.path,
        title: item.meta?.title || item.name,
        icon: () => h(NIcon, null, {
          default: () => h(NaIcon, {
            name: item.meta?.icon || 'menu'
          } as any)
        })
      }
      if (item.children && item.children.length) {
        tempR.children = fn(item.children)
      }
      tempArr.push(tempR)
    })
    return tempArr
  }

  return fn(permissionRoute)
})

watchEffect(() => {
  selectedKey.value = route.name
})

const handleUpdateValue = (key: string, item:MenuOption) => {
  selectedKey.value = key
  router.push({
    name: item.name
  })
  return undefined
}

</script>
<style lang="scss" scoped>
.page-header {
  height: 50px;
}
</style>