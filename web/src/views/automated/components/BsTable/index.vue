<template>
  <div class="bs-table">
    <!--筛选头部--->
    <div class="bs-table-header">
      <ColumnsCfg v-if="showFilterColumn" :columns="allColumns" @change="handleColCfgChange"/>
      <slot name="header"></slot>
    </div>
    <slot name="form"></slot>
    <n-data-table ref="table" v-bind="$attrs" :columns="tableColumns">
      <template #empty>
        <slot name="empty"></slot>
      </template>
      <template #loading>
        <slot name="loading"></slot>
      </template>
    </n-data-table>
  </div>
</template>
<script lang="ts">
import { NDataTable } from 'naive-ui'
import type {DataTableColumn} from 'naive-ui'
import ColumnsCfg from './ColumnsCfg.vue';
import {ref, defineComponent} from 'vue'
import type {PropType} from 'vue'


type TableColumn = DataTableColumn & {
  checked: boolean
  key: number | string
}
type RemoteMoreFn = () => Promise<TableColumn[]>
export default defineComponent({
  name: 'BsTable',
  components: {NDataTable, ColumnsCfg},
  props: {
    /**是否显示表格列筛选操作按钮 */
    showFilterColumn: Boolean,
    /**远程获取额外的表格项 */
    remoteMoreColumns: Function as PropType<RemoteMoreFn>,
    /**初始显示的表格列 */
    initShowColumns: Array as PropType<(string | number)[]>,
    columns: {
      type: Array as PropType<TableColumn[]>,
      default: () => []
    }
  },
  setup (props) {
    const allColumns = ref([] as TableColumn[])
    const tableColumns = ref([] as TableColumn[])
    const table = ref(null as any)
    const getAllColumns = async (cols:TableColumn[]) => {
      cols.forEach(el => {
        el.checked = !props.initShowColumns || props.initShowColumns.includes(el.key)
      })
      if (props.remoteMoreColumns) {
        const cfgs = await props.remoteMoreColumns() || []
        cfgs.forEach(el => {
          el.checked = !!(props.initShowColumns && props.initShowColumns.includes(el.key))
        })
        return [...cols, ...cfgs]
      }
      return cols
    }
    const start = async () => {
      allColumns.value = await getAllColumns([...props.columns])
      tableColumns.value = []
      allColumns.value.forEach(el => {
        el.checked && tableColumns.value.push({...el})
      })
    }
    start()
    return {
      table,
      allColumns,
      tableColumns,
      getAllColumns
    }
  },
  mounted () {
    const tableMethods = ['clearFilters', 'clearSorter', 'filters', 'page', 'scrollTo', 'sort']
    tableMethods.forEach(el => {
      (this as any)[el] = this.table[el]
    })
  },
  methods: {
    handleColCfgChange (columns:TableColumn[]) {
      this.tableColumns = columns
    },
  }
})
</script>

<style lang="scss">
.bs-table-header {
  text-align: right;
}
</style>