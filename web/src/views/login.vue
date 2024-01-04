<template>
    <n-el>
    <div class="flex login-container">
      <div class="left">
        <img :src="ImageBg1" />
        <div class="content-wrapper">
          <div class="logo-wrapper">
            <img :src="logo" />
          </div>
          <!-- <div class="title">NET-AXE</div> -->
          <div class="sub-title">专注网络自动化领域架构解决方案</div>
          <div class="flex-1 flex justify-center items-center ttppii"> 网络自动化平台</div>
          <div class="bottom-wrapper">NET-AXE {{ version }}</div>
        </div>
      </div>
      <div class="right">
        <div class="form-wrapper">
          <div class="form-title">账号登录</div>
          <div class="item-wrapper">
            <n-input
              v-model:value="username"
              placeholder="请输入用户名/手机号"
              prefix-icon="el-icon-user"
              clearable
            />
          </div>
          <div class="mt-4 item-wrapper">
            <n-input
              v-model:value="password"
              placeholder="请输入密码"
              type="password"
              clearable
              prefix-icon="el-icon-lock"
            />
          </div>
          <div class="mt-6">
            <n-button type="primary" class="login" :loading="loading" @click="onLogin">
              登录
            </n-button>
          </div>
          <div class="mt-6 my-width flex-sub">
            <div class="flex justify-between">
              <n-checkbox v-model:checked="autoLogin">自动登录</n-checkbox>
              <a :underline="false" type="primary">忘记密码？</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </n-el>
</template>
<script lang="ts" setup>
import ImageBg1 from '@/assets/login_bg.png'
import logo from '@/assets/logo.png'
import { useUserStore } from '@/store'
import {ref} from 'vue'
import qs from 'qs'
import { useRoute, useRouter } from 'vue-router'

const version = '1.0.0'
const username = ref('admin')
const password = ref('123456')
const loading = ref(false)
const autoLogin = ref(true)
const userStore = useUserStore()
const router = useRouter()
const route = useRoute()

/**
 * 登录
 */
const onLogin = async () => {
  const params = {
    username: username.value,
    password: password.value
  }
  try {
    await userStore.login(qs.stringify(params))
    router.replace({
      path: (route.query.redirect as string) || '/'
    })
  } catch (e) {}
}

</script>

<style lang="scss" scoped>
  .logo-wrapper {
    width: 80px;
    margin-top: 30%;
    img {
      max-width: 100%;
    }
  }
  @keyframes left-to-right {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(0);
    }
  }

  .login-container {
    position: relative;
    overflow: hidden;
    height: 100vh;
    width: 100%;
    @media screen and (max-width: 960px) {
      .left {
        display: none !important;
      }
    }

    .left {
      display: block;
      position: relative;
      //min-width: 600px;
      width: 700px;

      & > img {
        height: 100%;
        width: 100%;
      }

      &::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.6);
        z-index: 2;
      }

      .content-wrapper {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 9;
        display: flex;
        flex-direction: column;
        justify-content: space-around;
        align-items: center;

        .logo-wrapper {
          width: 80px;
          margin-top: 30%;
        }

        .title {
          margin-top: 10px;
          color: #ffffff;
          font-weight: bold;
          font-size: 24px;
        }

        .sub-title {
          margin-top: 10px;
          color: #f5f5f5;
          font-size: 16px;
        }

        .ttppii {
          color: #ffffff;
          font-weight: 500;
          font-size: 30px;
          // text-shadow: 1px 1px 2px #f5f5f5;
          animation: left-to-right 1s cubic-bezier(0.175, 0.885, 0.32, 1.275);
          text-shadow: 0 0 5px var(--primary-color), 0 0 15px var(--primary-color),
            0 0 50px var(--primary-color), 0 0 150px var(--primary-color);
        }

        .bottom-wrapper {
          margin-bottom: 5%;
          color: #c0c0c0;
          font-size: 16px;
        }
      }
    }

    .right {
      flex: 1;
      display: flex;
      justify-content: center;
      flex-direction: column;
      align-items: center;
      background: linear-gradient(to bottom, var(--primary-color));

      .form-wrapper {
        width: 35%;
        border-radius: 5px;
        border: 1px solid #f0f0f0;
        padding: 20px;
        box-shadow: 0px 0px 7px #dddddd;

        .form-title {
          font-size: 26px;
          margin-bottom: 20px;
          font-weight: bold;
        }

        .item-wrapper {
          width: 100%;
        }

        .login {
          width: 100%;
        }
      }

      .third-login {
        width: 50%;
      }
    }
  }

  .m-login-container {
    position: relative;
    height: 100vh;
    max-height: 100vh;
    overflow: hidden;
    background: linear-gradient(#7a9ad7, #3b5a94, #133064);
    // background-image: url(../../assets/img_login_mobile_bg_01.jpg);
    .header {
      height: 25vh;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;

      .the-p {
        width: 100px;
        height: 100px;
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid #f5f5f5;
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 56px;
        font-weight: bold;
      }
    }

    .top-line {
      background-image: linear-gradient(
        to right,
        rgba(117, 117, 117, 0.9) 25%,
        rgba(255, 255, 255, 0.3) 50%,
        rgba(117, 117, 117, 0.9) 75%
      );
      height: 1px;
      background-color: #ffffff;
    }

    .content {
      height: 40vh;
      margin: 5% 10%;
      border-radius: 10px;

      :deep(.n-input) {
        background-color: rgba(183, 183, 183, 0);
      }

      :deep(.n-input .n-input__input-el, .n-input .n-input__textarea-el) {
        color: #fff;
      }

      :deep(.n-checkbox .n-checkbox__label) {
        color: #fff;
      }
    }

    .footer {
      position: absolute;
      left: 10%;
      right: 10%;
      bottom: 10%;

      :deep(.n-divider .n-divider__title) {
        color: #c3c3c3;
        font-size: 14px;
      }

      :deep(.n-divider:not(.n-divider--dashed) .n-divider__line) {
        background-color: rgba(117, 117, 117);
      }
    }
  }
</style>