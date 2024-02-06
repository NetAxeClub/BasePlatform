<template>
  <n-data-table
    ref="table"
    v-bind="$attrs"
    :columns="tableColumns"
    :pagination="pagenation"
    :loading="loading"
    remote
    :on-update:page="handleUpdatePage"
    :on-update:page-size="handleUpdatePageSize"
    :on-update:sorter="handleUpdateSorter"
    class="na-data-table"
  >
    <template #empty>
      <slot name="empty"></slot>
    </template>
    <template #loading>
      <slot name="loading">
        <na-loading show :text="loadingText"></na-loading>
      </slot>
    </template>
  </n-data-table>
</template>
<script setup lang="ts">
import type {DataTableColumn} from 'naive-ui'
import {ref, watch, type PropType} from 'vue'
import NaLoading from '../NaLoading.vue'

export type TableColumn = DataTableColumn & {
  checked?: boolean
  key?: number | string
  _disabled?: boolean
}

export type TableParams = {
  page: number
  start: number
  limit: number
}

type RemoteMoreFn = () => Promise<TableColumn[]>
const props = defineProps({
  loadingText: String,
  /**获取表格数据 */
  getList: Function,
  columns: {
    type: Array as PropType<TableColumn[]>,
    default: () => []
  },
  /**初始显示的表格列 */
  initShowColumns: Array as PropType<(string | number | undefined)[]>,
  /**远程获取额外的表格项 */
  remoteMoreColumns: Function as PropType<RemoteMoreFn>
})

const emit = defineEmits(['column-change'])
const allColumns = ref([] as TableColumn[])
const tableColumns = ref([] as TableColumn[])
const table = ref(null as any)
const pagenation = ref(false as any)
const sorter = ref({} as any)
const needInitAll = ref(false)
const loading = ref(false)

watch(() => props.columns, () => start())

/**
 * 生成分页配置
 */
const generatePagenation = () => {
  pagenation.value = {
    page: 1,
    pageSize: 10,
    itemCount: 0,
    pageCount: 0,
    showSizePicker: true,
    pageSizes: [{
      label: '10/页',
      value: 10
    }, {
      label: '50/页',
      value: 50
    }, {
      label: '100/页',
      value: 100
    }, {
      label: '200/页',
      value: 200
    }],
    prefix: ({itemCount}: any) => {
      return `共${itemCount}项`
    }
  }
}

const getAllColumns = async (cols:TableColumn[]) => {
  cols.forEach(el => {
    el.checked = !props.initShowColumns || props.initShowColumns.includes(el.key) || !el.key
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
  needInitAll.value = true
  tableColumns.value = []
  allColumns.value.forEach(el => {
    el.checked && tableColumns.value.push({...el})
  })
}
const handleColCfgChange = (columns: TableColumn[]) => {
  tableColumns.value = columns
  emit('column-change', [...columns])
}
const getNeedInitAll = () => {
  return needInitAll.value
}
const updateNeedInitAll = (val:boolean) => {
  needInitAll.value = val
}

const handleUpdatePage = (page:number) => {
  pagenation.value.page = page
  queryList()
}

const handleUpdatePageSize = (pageSize:number) => {
  pagenation.value.pageSize = pageSize
  pagenation.value.page = 1
  queryList()
}
/**
 * 排序变更
 */
const handleUpdateSorter = (_options:any) => {}


/*抛出原naive-ui方法*/
const methodsObj:any = {}
const tableMethods = ['clearFilters', 'clearSorter', 'filters', 'page', 'scrollTo', 'sort']
tableMethods.forEach(key => {
  methodsObj[key] = (...args:any[]) => {
    return table.value && table.value[key](...args)
  }
})
if (props.getList) { // 含远程获取表格数据，初始化分页参数
  generatePagenation()
}

const queryData = async () => {
  pagenation.value.page = 1
  await queryList()
  return 1
}

const refresh = async () => {
  await queryList()
  return 1
}

/**
 * 查询表格数据
 */
const queryList = async () => {
  if (props.getList) {
    const params = {
      start: (pagenation.value.page - 1) * pagenation.value.pageSize,
      limit: pagenation.value.pageSize,
      page: pagenation.value.page,
      ...sorter.value
    }
    loading.value = true
    const res = await props.getList(params)
    pagenation.value.itemCount = res.total
    pagenation.value.pageCount = Math.ceil(res.total / pagenation.value.pageSize)
    loading.value = false
  }
  return 1
}

defineExpose({
  allColumns,
  getNeedInitAll,
  updateNeedInitAll,
  handleColCfgChange,
  ...methodsObj,
  queryData,
  refresh
})
start()

</script>
<style lang="scss" scoped>
.na-data-table {
  :deep(.n-spin-container) {
    width: 200px;
  }
}
</style>