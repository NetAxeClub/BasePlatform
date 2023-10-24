<template>
 <n-popover :style="{ width: '200px' }" placement="left-start" trigger="click">
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
                :label="element.prop"
                @update:checked="onChange"
              >
                {{ element.title }}
              </n-checkbox>
            </div>
            <n-icon>
              <MenuIcon />
            </n-icon>
          </li>
        </template>
      </draggable>
    </ul>  
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
<script lang="ts">
import { SettingsOutline as SettingsIcon, Menu as MenuIcon } from '@vicons/ionicons5'
import {defineComponent, ref} from 'vue'
import draggable from 'vuedraggable'
export default defineComponent({
  name: 'ColumnsCfg',
  components: {SettingsIcon, draggable, MenuIcon},
  props: {
    columns: Array
  },
  emits: ['change'],
  setup (props) {
    const allChecked = ref(false)
    const isIndeterminate = ref(false)
    const opts = ref([] as any[])
    const allCheckStatus = () => {
      const filterArr = opts.value.filter(el => el.checked)
      isIndeterminate.value = filterArr.length !== 0 && filterArr.length !== opts.value.length
      allChecked.value = filterArr.length !== 0
    }
    const initColumns = () => {
      if (props.columns) {
        opts.value = []
        props.columns.forEach((el:any) => {
          opts.value.push({...el})
        })
      }
    }
    initColumns()
    allCheckStatus()
    return {
      allCheckStatus,
      initColumns,
      allChecked,
      isIndeterminate,
      opts
    }
  },
  watch: {
    columns () {
      this.initColumns()
      this.allCheckStatus()
    }
  },
  methods: {
    onUpdateValue () {
      this.checkedEmit()
    },
    onAllChange (val:boolean) {
      this.opts.forEach(el => {
        el.checked = val
      })
      this.isIndeterminate = false
      this.checkedEmit()
    },
    onChange () {
      this.allCheckStatus()
      this.checkedEmit()
    },
    checkedEmit () {
      const data = this.opts.filter(el => el.checked).map(el => {
        const obj = {...el}
        delete obj.checked
        return obj
      })
      this.$emit('change', data)
    }
  }
})

</script>

<style lang="scss">
  .table-columns-cfg {
    .check-item {
      display: flex;
      padding: 3px 0;
      .checkbox-wrap {
        flex: 1;
      }
    }
  }
</style>