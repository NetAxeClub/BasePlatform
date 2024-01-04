<template>
  <n-modal
    :show="show"
    @update:show="updateShow"
    preset="card"
    :title="title"
    size="small"
    class="modal-dialog-wrapper"
    header-style="padding: 10px 20px"
    :bordered="false"
    :style="bodyStyle"
    :segmented="segmented"
    display-directive="show"
    v-bind="$attrs"
    ref="modalRef"
  >
    <n-scrollbar>
      <div :style="{ maxHeight: 'calc(100vh - 160px)', height: contentHeight }">
          <slot></slot>
      </div>
    </n-scrollbar>
    <template #footer>
      <slot name="footer">
        <div class="flex justify-end">
          <n-space>
            <n-button type="default" size="small" @click="onCancel">取消</n-button>
            <n-button type="primary" size="small" @click="onConfirm">确定</n-button>
          </n-space>
        </div>
      </slot>
    </template>
  </n-modal>
</template>
<script setup lang="ts">
import { computed, ref, watchEffect, nextTick } from 'vue'
import { drag, unDrag } from './utils/dialog-drag'
import {isEmpty} from '@/utils'

const props = defineProps({
  /**是否可拖拽 */
  dragable: {
    type: Boolean,
    default: true
  },
  top: {
    type: Number
  },
  /**设置弹框宽度 */
  width: {
    type: String,
    default: '80%'
  },
  show: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: '操作'
  },
  contentHeight: {
    type: String,
    default: 'auto'
  }
})
const emit = defineEmits(['confirm', 'cancel', 'update:show'])
const header = ref<HTMLElement | null>()
const parent = ref<HTMLElement | null>()
const parentWrap = ref<HTMLElement | null>()
const modalRef = ref(null)
const bodyStyle = computed(() => ({width: props.width}))
const segmented = {
  content: 'soft',
  footer: 'soft'
} as any

const updateShow = (val:boolean) => {
  emit('update:show', val)
}

const toggle = () => {
  const val = !props.show
  updateShow(val)
  return Promise.resolve(val)
}

const open = () => {
  updateShow(true)
  return Promise.resolve(true)
}

const close = () => {
  updateShow(false)
  return Promise.resolve(false)
}

const onCancel = () => {
  updateShow(false)
  emit('cancel')
}
const onConfirm = () => {
  emit('confirm')
}

/**
 * 重置弹框位置
 */
const resetPosition = () => {
  if (parent.value && parentWrap.value) {
    parent.value.style.top = isEmpty(props.top) ? (window.innerHeight - parentWrap.value.offsetHeight) / 2 + 'px' : props.top + 'px'
  }
}

watchEffect(() => {
  if (!props.dragable) return
  if (props.show) {
    nextTick(() => {
      if (!header.value) {
        header.value = (modalRef.value as any).containerRef.querySelector(
          '.n-modal-container .n-card-header'
        ) as HTMLElement
        const parentNode = header.value.parentElement
        const parentP = parentNode?.parentElement
        parent.value = parentNode
        parentWrap.value = parentP
        if (parentP) {
          parentP.style.minHeight = 'auto'
          parentNode.style.top = isEmpty(props.top) ? (window.innerHeight - parentP.offsetHeight) / 2 + 'px' : props.top + 'px'
        }
      }
      // if (parentNode && parentNode?.offsetTop < 0) {
      //   parentNode.style.top = '0px'
      // }
      drag(header.value)
    })
  } else {
    nextTick(() => {
      if (header.value) {
        unDrag(header.value as HTMLElement)
      }
    })
  }
})
defineExpose({
  toggle,
  resetPosition,
  open,
  close
})
</script>
<style lang="scss" scoped>
.modal-dialog-wrapper {
  color: red;
  :deep(.n-modal-body-wrapper .n-modal-scroll-content) {
    min-height: auto;
  }
}
</style>