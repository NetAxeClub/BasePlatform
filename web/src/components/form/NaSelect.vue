<template>
  <n-select ref="selectRef" :options="computedOptions" :filterable="filterable" v-bind="$attrs" v-model:value="currentValue" :clearable="clearable"></n-select>
</template>
<script setup lang="ts">
import { isEmpty } from '@/utils'
import {ref, watch, computed, nextTick} from 'vue'
const props = defineProps({
  options: [Array,Function] as any,
  filterable: {
    type: Boolean,
    default: true
  },
  clearable: {
    type: Boolean,
    default: true
  },
  getOptionsFn: Function,
  value: [String, Number, Array, Boolean]
})

const emit = defineEmits(['update:value', 'change'])
const selectRef = ref()

const currentOptions = ref()
const currentValue = ref<any>(isEmpty(props.value) ? null  : props.value)

const computedOptions = computed(() => {
  if (props.getOptionsFn) {
    return currentOptions.value
  } else {
    if (typeof props.options === 'function') {
      return props.options()
    }
    return props.options
  }
})

watch(() => props.value, () => {
  currentValue.value = isEmpty(props.value) ? null  : props.value
})

watch(() => currentValue.value, () => {
  emit('update:value', currentValue.value)
  nextTick(() => {
    emit('change', currentValue.value)
  })
})
// 远程或特殊逻辑拉取选项
const getOptions = async () => {
  if (props.getOptionsFn) {
    currentOptions.value = await props.getOptionsFn()
  }
}

getOptions()

defineExpose({
  focus: () => {
    selectRef.value && selectRef.value.focus()
  }
})

</script>