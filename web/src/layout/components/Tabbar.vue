<template>
  <div class="tabbar">
    <n-icon size="20" class="arrow left" @click="leftArrowClick()">
      <ChevronBack/>
    </n-icon>
    <n-scrollbar ref="scrollbar" class="bar-content" :x-scrollable="true" :size="0">
      <div style="white-space: nowrap;">
        <n-button
          :type="findType(item.path, route.fullPath)" 
          size="tiny" 
          v-for="(item, index) in commonStore.historyRoutes" 
          :key="index"
          @click="handleBtn(item)"
        >
          <span>{{ item.title }}</span>
          <n-icon class="btn-icon" :size="16" @click.prevent.stop="handleRemoveItem(index)">
            <Close/>
          </n-icon>
        </n-button>
      </div>
    </n-scrollbar>
    <n-icon size="20" class="arrow right" @click="rightArrowClick">
      <ChevronBack/>
    </n-icon>
  </div>
</template>
<script setup lang="ts">
import { ChevronBack, Close } from '@vicons/ionicons5'
import { NScrollbar } from 'naive-ui'
import {ref} from 'vue'
import { useCommonStore, HistoryRoute } from '@/store'
import { useRoute, useRouter } from 'vue-router'

const commonStore = useCommonStore()
const route = useRoute()
const router = useRouter()

const scrollbar = ref()

const handleBtn = (item:HistoryRoute) => {
  if (item.path !== route.fullPath) {
    router.push(item.path)
  }
}

const handleRemoveItem = (index:number) => {
  commonStore.removeHistory(index)
}

const findType = (path1:any, path2:any) => {
  return path1 === path2 ? 'primary' : 'default'
}

const leftArrowClick = () => {
  const scrollX = scrollbar.value.$el?.scrollLeft || 0
  scrollbar.value.scrollTo(
    {
      left: Math.max(0, scrollX - 200),
      debounce: true,
      behavior: 'smooth',
    } as any,
    0
  )
}
const rightArrowClick = () => {
  const scrollX = scrollbar.value.$el?.scrollLeft || 0
  scrollbar.value.scrollTo(
    {
      left: scrollX + 200,
      debounce: false,
      behavior: 'smooth',
    } as any,
    0
  )
}

</script>
<style lang="scss" scoped>
.tabbar {
  display: flex;
  height: 35px;
  .arrow {
    margin-top: 2px;
    cursor: pointer;
    &.left {
      margin-right: 10px;
    }
    &.right {
      transform: rotate(-180deg);
    }
  }
  .bar-content {
    margin: 0 10px;
    .btn-icon {
      border-radius: 10px;
      margin-left: 5px;
      width: 0;
      overflow: hidden;
      transition: all .2s ease-in-out;
    }
    button {
      margin-right: 10px;
      &:hover {
        .btn-icon {
          width: auto;
          display: inline-block;
        }
      }
    }
  }
}
</style>