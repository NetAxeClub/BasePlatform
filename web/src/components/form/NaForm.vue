<template>
  <n-form 
    :label-placement="labelPlacement" 
    :size="size"
    :label-width="labelWidth"
    v-bind="$attrs"
    :model="formValue"
    ref="form"
  >
    <n-grid :cols="12" :x-gap="gap">
      <template v-for="(option, index) in options">
        <n-form-item-gi
          :key="index"
          :span="computedSpan"
          :label="option.label"
          :label-width="option.labelWidth"
          v-if="showFormItem(option)"
          :path="option.path"
        >
        <component 
          :is="getComponent(option)" 
          v-bind="getFormItemBind(option)"
          :value="formItemValue(option)"
          @update:value="(val:any) => upateformItemValue(option, val)"
        >
        </component>
      </n-form-item-gi>
      </template>
    </n-grid>
    <slot>
    </slot>
  </n-form>
</template>
<script setup lang="ts">
import { LabelPlacement, Size } from 'naive-ui/es/form/src/interface'
import { NInput, NSelect, FormInst, NTimePicker, NCheckbox, NInputNumber, NSwitch } from 'naive-ui'
import NaDatePicker from './NaDatePicker.vue'
import NaSelect from './NaSelect.vue'
import {computed, VNode, DefineComponent, ref, watch} from 'vue'

const defualtCmp:any = {
  input: NInput,
  select: NSelect,
  naSelect: NaSelect,
  date: NaDatePicker,
  checkbox: NCheckbox,
  number: NInputNumber,
  time: NTimePicker,
  switch: NSwitch
}

type Func = () => VNode | DefineComponent
type Unshow = () => boolean

/**配置项类型 */
export type FormOptionItem = {
  label: string
  path: string
  type?: 'input' | 'select' | 'naSelect' | 'date' | 'checkbox' | 'number' | 'time' | 'switch'
  /**是否不显示 */
  unshow?: boolean | Unshow
  /**type不存在时 此方法必须*/
  render?: Func
  bind: any
  labelWidth?: string | number
}
type Props = {
  model: any
  labelPlacement?: LabelPlacement
  grid?: 1|2|3|4
  gap?: number,
  size?: Size
  labelWidth?: string | number
  options?: FormOptionItem[]
}

const props = withDefaults(defineProps<Props>(), {
  labelPlacement: 'left',
  grid: 4,
  gap: 12,
  size: 'small',
  labelWidth: '80px',
  options: () => []
})

const formValue = ref(props.model)
const form = ref<FormInst | null>(null)

watch(() => props.model, () => {
  generateFormValue()
})

const generateFormValue = () => {
  if (props.model) {
    formValue.value = props.model
  } else {
    // 从options获取，弊端，无法多层级格式化数据例如path: a.b.c
    const obj:any = {}
    props.options.forEach(el => {
      obj[el.path] = ''
    })
    formValue.value = obj
  }
}
const getComponent = (option:FormOptionItem) => {
  let cmp = defualtCmp[option.type || '']
  if (!cmp) {
    if (typeof option.render === 'function') {
      cmp = option.render()
    }
  }
  return cmp
}
const showFormItem = (option:FormOptionItem) => {
  if (typeof option.unshow === 'function') {
    return !option.unshow()
  }
  return !option.unshow
}

const getFormItemBind = (option: FormOptionItem) => {
  if (typeof option.bind === 'function') {
    return option.bind()
  }
  return option.bind
}

const formItemValue = (option:FormOptionItem) => {
  const arr = option.path.split('.')
  let value
  for (let key of arr) {
    if (value) {
      value = value[key]
    } else {
      value = formValue.value[key]
    }
  }
  return value
}
const upateformItemValue = (option:FormOptionItem, val:any) => {
  const arr = option.path.split('.')
  let data = formValue.value
  for (let i = 0; i < arr.length; i++) {
    if (i < arr.length - 1) {
      data = data[arr[i]]
    } else {
      data[arr[i]] = val
    }
  }
  return undefined
}


/***初始化表单配置****/
const computedSpan = computed(() => 12 / (props.grid || 1))
generateFormValue()


const validate = (...args:any[]) => {
  return form.value?.validate(...args)
}

const restoreValidation = () => {
  return form.value?.restoreValidation()
}
/**
 * 获取表单数据
 */
const getFormValue = () => {
  return formValue.value
}

defineExpose({
  validate,
  restoreValidation,
  getFormValue
})

</script>