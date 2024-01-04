<template>
  <slot v-if="disabled" :prefix="prefix" :value="value">
    <div class="icon-wrap" :style="computedStyle">
      <n-icon :size="computedSize">
        <NaIcon :prefix="prefix" :name="value || ''"></NaIcon>
      </n-icon>
    </div>
  </slot>
  <n-popover trigger="click" v-model:show="showModal" v-else>
    <template #trigger>
      <slot :prefix="prefix" :value="value">
        <div class="icon-wrap" :style="computedStyle">
          <n-icon :size="computedSize">
            <NaIcon :prefix="prefix" :name="value || ''"></NaIcon>
          </n-icon>
        </div>
      </slot>
    </template>
    <NaIconCheck
      @cancel="onCancel" 
      @confirm="onConfirm"
      @update:value="updateValue"
      @update:prefix="updatePrefix"
      :value="value"
      :prefix="prefix"
      :options="options"
    />
  </n-popover>
</template>

<script setup lang="ts">
import NaIconCheck from './NaIconCheck.vue'
import {ref, computed} from 'vue'
import NaIcon from '../NaIcon.vue'

const props = defineProps({
  disabled: Boolean,
  value: String,
  prefix: String,
  options: Array,
  size: {
    type: Number,
    default: 60
  }
})

const computedStyle = computed(() => ({
  width: props.size + 'px',
  height: props.size + 'px',
  lineHeight: props.size + 'px'
}))
const computedSize = computed(() => props.size - 30)
const emit = defineEmits(['update:value', 'update:prefix', 'confirm'])

const showModal = ref(false)

const onCancel = () => {
  showModal.value = false
}

const onConfirm = () => {
  showModal.value = false
  emit('confirm')
}

const updateValue = (value:string) => {
  emit('update:value', value)
}

const updatePrefix = () => {}
</script>
<style lang="scss" scoped>
  .icon-wrap {
    border-radius: 100%;
    color: var(--primary-color);
    box-sizing: border-box;
    padding: 10px;
    display: inline-block;
    vertical-align: middle;
    border: solid 1px #e3e3e3;
    text-align: center;
  }
</style>