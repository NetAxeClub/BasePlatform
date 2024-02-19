<template>
   <n-popover :style="{ width: '200px' }" placement="left-start" trigger="click">
    <n-scrollbar>
      <ul class="table-columns-cfg">
        <li class="check-item">
          <n-checkbox
            v-model:checked="allChecked"
            :indeterminate="isIndeterminate"
            @update:checked="onAllChange"
          >
            全选
          </n-checkbox>
        </li>
        <draggable
          :list="opts"
          animation="500"
          item-key="key"
          @end="onUpdateValue"
        >
          <template #item="{ element }">
            <li  class="check-item">
              <div class="checkbox-wrap">
                <n-checkbox
                  v-model:checked="element.checked"
                  :disabled="!element.key || element._disabled"
                  :label="element.prop"
                  @update:checked="onChange"
                >
                  {{ element.title || element.type}}
                </n-checkbox>
              </div>
              <n-icon>
                <MenuIcon />
              </n-icon>
            </li>
          </template>
        </draggable>
      </ul>  
    </n-scrollbar>
    <template #trigger>
      <n-button type="success" size="small" circle>
        <template #icon>
          <n-icon>
            <SettingsIcon />
          </n-icon>
        </template>
      </n-button>
    </template>
 </n-popover>
</template>
<script setup lang="ts">
import { SettingsOutline as SettingsIcon, Menu as MenuIcon } from '@vicons/ionicons5'
import draggable from 'vuedraggable'
import {ref, watchEffect} from 'vue'
const props = defineProps({
  /**NaTable 组件实例化对象 */
  tableRef: Object as any
})
const allChecked = ref(false)
const isIndeterminate = ref(false)
const opts = ref([] as any[])
const allCheckStatus = () => {
  const filterArr = opts.value.filter(el => el.checked)
  isIndeterminate.value = filterArr.length !== 0 && filterArr.length !== opts.value.length
  allChecked.value = filterArr.length !== 0
}
const initColumns = (columns:any[]) => {
  if (columns) {
    opts.value = []
    columns.forEach((el:any) => {
      opts.value.push({...el})
    })
  }
}

watchEffect(() => {
  if (props.tableRef && props.tableRef.allColumns && props.tableRef.getNeedInitAll()) {
    initColumns(props.tableRef.allColumns)
    allCheckStatus()
    props.tableRef.updateNeedInitAll(false)
  }
})

const checkedEmit = () => {
  const data = opts.value.filter(el => el.checked).map(el => {
    const obj = {...el}
    delete obj.checked
    return obj
  })
  // this.$emit('change', data)
  if (props.tableRef) {
    props.tableRef.handleColCfgChange(data)
  }
}

const onAllChange = (val:boolean) => {
  let len = 0
  opts.value.forEach(el => {
    if (el.key && !el._disabled) {
      el.checked = val
      len++
    }
  })
  isIndeterminate.value = len !== opts.value.length
  checkedEmit()
}
const onUpdateValue = () => {
  checkedEmit()
}
const onChange = () => {
  allCheckStatus()
  checkedEmit()
}
</script>
<style lang="scss" scoped>
.table-columns-cfg {
  max-height: 500px;
}
.check-item {
  display: flex;
  margin-bottom: 8px;
  .checkbox-wrap {
    flex: 1;
  }
}
</style>