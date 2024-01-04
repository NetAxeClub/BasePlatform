<template>
  <n-breadcrumb>
    <transition-group name="breadcrumb">
      <n-breadcrumb-item v-for="(item, index) in breadList" :key="index">
        <n-dropdown :on-select="handleBreadSelect" :options="findOptions(item.children)" v-if="item.children && item.children.length">
          <div>{{item.meta && item.meta.title ? item.meta.title : item.name}}</div>
        </n-dropdown>
        <div v-else>{{item.meta && item.meta.title ? item.meta.title : item.name}}</div>
      </n-breadcrumb-item>
    </transition-group>
  </n-breadcrumb>
</template>
<script setup lang="ts">
import { RouteRecordRaw, useRoute, useRouter } from 'vue-router'
import {ref, watch} from 'vue'
import { DropdownMixedOption } from 'naive-ui/es/dropdown/src/interface'

const router = useRouter()
const route = useRoute()

const breadList = ref(route.matched)

watch(() => route.fullPath, () => {
  breadList.value = route.matched
})

const findOptions = (routes:RouteRecordRaw[]) => {
  const result:any[] = []
  routes.forEach(el => {
    if (!(el.meta && el.meta.hidden)) {
      result.push({
        label: el.meta && el.meta.title ? el.meta.title : el.name,
        key: el.name
      })
    }
  })
  return result as DropdownMixedOption[]
}

const handleBreadSelect = (key:string) => {
  router.push({name: key})
}

</script>

<style lang="scss">
/* breadcrumb transition */
.breadcrumb-enter-active,
.breadcrumb-leave-active {
  transition: all 0.5s;
}

.breadcrumb-enter-from,
.breadcrumb-leave-active {
  opacity: 0;
  transform: translateX(20px);
}

.breadcrumb-move {
  transition: all 0.5s;
}

.breadcrumb-leave-active {
  position: absolute;
}
</style>