<template>
  <div>
    <!--头部-->
    <TopHeader :title="hooks.title"/>
    <n-layout class="page-main" has-sider>
      <n-layout-sider
        bordered
        collapse-mode="width"
        :collapsed-width="64"
        :width="210"
        :collapsed="collapsed"
        show-trigger
        @collapse="collapsed = true"
        @expand="collapsed = false"
      >
      <n-scrollbar>
        <Sidebar :collapsed="collapsed"/>
      </n-scrollbar>
      </n-layout-sider>
      <n-layout class="page-main-container">
        <n-scrollbar ref="scrollRef">
          <div class="page-main-tabbar">
            <Tabbar/>
          </div>
          <div class="page-main-top">
            <Bread/>
          </div>
          <RouterView/>
          <div class="page-mian-footer" v-html="hooks.footerText"></div>
        </n-scrollbar>
      </n-layout>
    </n-layout>
  </div>
</template>
<script lang="ts" setup>
import TopHeader from './components/TopHeader.vue'
import Sidebar from './components/Sidebar.vue'
import hooks from '@/hooks'
import { ref, watch } from 'vue'
import Bread from './components/Bread.vue'
import Tabbar from './components/Tabbar.vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const collapsed = ref(false)
const scrollRef = ref()

watch(() => route.fullPath, () => {
  scrollRef.value.scrollTo({top: 0})
})

</script>
<style lang="scss" scoped>
.page-main {
  height: calc(100vh - 50px);
}
.page-main-container {
  position: relative;
  background-color: #f0f2f5;
}
.page-mian-footer {
  text-align: center;
  padding: 10px 0;
  background-color: #fff;
  margin: 0 5px;
}
.page-main-top {
  padding: 0 15px;
  padding-top: 15px;
}
.page-main-tabbar {
  padding: 5px 15px;
  padding-bottom: 0;
  border-bottom: solid 1px #e3e3e3;
  box-shadow: 10px 5px 10px #0000001a;
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: #fff;
}

</style>