<template>
  <div class="icon-check">
    <!--顶部-->
    <div class="check-top">
      <div class="top-tab">
        <div class="tab-pan active">系统图标</div>
      </div>
      <div>
        <n-input placeholder="请输入关键字" v-model:value="filterStr"></n-input>
      </div>
    </div>
    <!--图标主体显示区域-->
    <div class="check-content">
      <ul class="icon-list">
        <li class="icon-item" 
          v-for="(item, index) in computedViewOptions"
          :key="index"
          :class="{active: item.value === currentValue}"
          @click="handleCheckItem(item)"
          :title="item.label"
        >
          <NaIcon :prefix="currentPrefix" :name="item.value"/>
          <n-icon size="20" class="check" v-if="item.value === currentValue">
            <CheckmarkCircle/>
          </n-icon>
        </li>
      </ul>
    </div>
    <div class="check-footer">
      <n-button type="primary" @click="handleConfirm()">确定</n-button>
      <n-button @click="handleCancel()">取消</n-button>
    </div>
  </div>
</template>
<script setup lang="ts">
import NaIcon from '../NaIcon.vue'
import { CheckmarkCircle } from '@vicons/ionicons5'
import {ref, watchEffect, computed} from 'vue'
import icons from '@/assets/font/icons.json'

export type EnumsItem = {
  label: string
  value: any
}

const props = defineProps({
  prefix: String,
  value: String,
  options: Array
})

const emit = defineEmits(['cancel', 'update:value', 'update:prefix', 'confirm'])
const currentPrefix = ref(props.prefix || 'na-icon-')
const currentValue= ref(props.value)
const filterStr = ref('')

const computedOptions = computed(() => {
  if (!props.options) {
    return icons.map(el => {
      const str = el.replace('na-icon-', '')
      return {
        label: str,
        value: str
      }
    }) as any[]
  }
  return props.options as any[]
})

const computedViewOptions = computed(() => {
  return computedOptions.value.filter(el => el.label.indexOf(filterStr.value.trim()) > -1)
})

watchEffect(() => {
  currentPrefix.value = props.prefix || 'na-icon-'
  currentValue.value = props.value
})

const handleCheckItem = (item:EnumsItem) => {
  currentValue.value = item.value
}

const handleCancel = () => {
  emit('cancel')
}
const handleConfirm = () => {
  emit('update:value', currentValue.value)
  emit('confirm')
}

</script>
<style lang="scss" scoped>
.icon-check {
  width: 600px;
  .check-top {
    border-bottom: solid 1px #e3e3e3;
    display: flex;
    .top-tab {
      flex: 1;
      display: flex;
      .tab-pan {
        padding: 10px 5px;
        max-width: 120px;
        text-overflow: ellipsis;
        overflow: hidden;
        white-space: nowrap;
        position: relative;
        &.active {
          color: var(--primary-color);
          &::after {
            position: absolute;
            width: 100%;
            left: 0;
            bottom: -1px;
            height: 2px;
            content: ' ';
            display: block;
            background-color: var(--primary-color);
          }
        }
      }
    }
  }
  .check-content {
    .icon-list {
      display: flex;
      flex-wrap: wrap;
      .icon-item {
        margin-top: 10px;
        position: relative;
        width: 10%;
        height: 60px;
        display: flex;
        justify-content: center;
        align-items: center;
        font-size: 24px;
        cursor: pointer;
        &:hover {
          background-color: var(--bg-card-color);
        }
        &.active {
          cursor: default;
          background-color: var(--bg-card-color);
          border: dashed 1px #ccc;
          .check {
            position: absolute;
            right: -5px;
            bottom: -5px;
            border-radius: 20px;
            width: 20px;
            height: 20px;
            color: var(--primary-color);

          }
        }
      }
    }
  }
  .check-footer {
    margin-top: 10px;
    border-top: solid 1px #e3e3e3;
    text-align: right;
    padding-top: 10px;
    button {
      margin-left: 10px;
    }
  }
}
</style>