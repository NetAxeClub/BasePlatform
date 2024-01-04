<template>
  <div class="page-header">
    <!--左侧区域-->
    <div class="header-left">
      <div class="logo-wrap">
        <img :src="logo">
        <div class="logo-title">{{title}}</div>
      </div>
    </div>
    <!--右侧区域-->
    <div class="header-right">
      <n-dropdown :options="rightOptions" size="large" @select="handleRightSelect">
        <div class="avatar-wrap">
          <div class="avatar">
            <n-avatar circle size="small" :src="avatar"></n-avatar>
          </div>
          <div class="nick-name">
            张三
            <n-icon class="tip">
              <CaretDownSharp/>
            </n-icon>
          </div>
        </div>
      </n-dropdown>
    </div>
  </div>
</template>
<script setup lang="ts">
import logo from '@/assets/logo.png'
import { PersonOutline, LogInOutline, BuildOutline, CaretDownSharp } from '@vicons/ionicons5'
import {NIcon, useDialog} from 'naive-ui'
import avatar from '@/assets/avatar.png'
import {h} from 'vue'
import {useUserStore} from '@/store'
import { redirectToLogin } from '@/utils/auth'

defineProps({
  title: String
})

const dialog = useDialog()
const userStore = useUserStore()
const rightOptions = [{
  label: '个人中心',
  key: 'personal-center',
  icon: () => h(NIcon, null, {
    default: () => h(PersonOutline)
  })
}, {
  label: '修改密码',
  key: 'modify-pwd',
  icon: () => h(NIcon, null, {
    default: () => h(BuildOutline)
  })
}, {
  label: '退出登录',
  key: 'logout',
  icon: () =>
    h(NIcon, null, {
      default: () => h(LogInOutline),
    }),
}]
const handleRightSelect = (val:string) => {
  if (val === 'logout') {
    logout()
  }
}

/**
 * 退出登录
 */
const logout = () => {
  dialog.warning({
    title: '提示',
    content: '确定退出登录？',
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      await userStore.logout({})
      redirectToLogin()
    }
  })
}
</script>
<style lang="scss" scoped>
.page-header {
  height: 50px;
  border-bottom: solid 1px #e3e3e3;
  display: flex;
  .header-left {
    flex: 1;
  }
  .logo-wrap {
    width: 210px;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 48px;
    img {
      width: 70px;
    }
    .logo-title {
      font-size: 14px;
      font-weight: bold;
      margin-left: 10px;
    }
  }
  .header-right {
    margin-left: 20px;
    padding-right: 20px;
    padding-top: 10px;
    display: flex;
    .avatar-wrap {
      display: flex;
      cursor: pointer;
      .nick-name {
        margin-left: 5px;
      }
      .tip {
        transition: transform 0.3s ease;
      }
      &:hover {
       .tip {
        transform: rotate(180deg);
       } 
      }
    }
  }
}
</style>