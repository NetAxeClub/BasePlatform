<template>
  <n-date-picker :value="currentValue" @update:value="handleUpdateValue" v-bind="$attrs"></n-date-picker>
</template>

<script setup lang="ts">
import {ref, watch} from 'vue'
import moment from 'moment'

const emit = defineEmits(['update:value'])

const props = defineProps({
  value: [Number, String, Array],
  /**格式化取值*/
  formatValue: String
})

const currentValue = ref()

const _format = (val:number) => {
  if (typeof val === 'number') {
    if (props.formatValue) {
      const formatStr = props.formatValue.replace(/y/g, 'Y').replace(/d/g, 'D')
      return moment(val).format(formatStr)
    }
    return val
  }
  return val
}

const _reFormat = (val:any) => {
  if (typeof val === 'number') {
    return val
  }
  if (!val) {
    return null
  }
  return new Date(val).getTime()
}

/**
 * 监听选择值改变
 */
const handleUpdateValue = (val:any) => {
  if (val instanceof Array) { // 区间范围
    emit('update:value', [_format(val[0]), _format(val[1])])
  } else { // 单选
    emit('update:value', _format(val))
  }
}
watch(() => props.value, () => {
  if (props.value instanceof Array) {
    currentValue.value = [_reFormat(props.value[0]), _reFormat(props.value[1])]
  } else {
    currentValue.value = _reFormat(props.value)
  }
})

</script>