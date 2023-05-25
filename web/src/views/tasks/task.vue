<template>
  <div class="main-container">
    <TableBody ref="tableBody">
      <template #header>
        <TableHeader
          :show-filter="true"
          title="查询条件"
          @search="onSearch"
          @reset-search="onResetSearch"
        >
          <template #search-content>
            <DataForm
              ref="searchForm"
              :form-config="{
                labelWidth: 60,
              }"
              :options="conditionItems"
              preset="grid-item"
            />
          </template>
        </TableHeader>
      </template>
      <template #default>
        <n-data-table
          size="small"
          :loading="tableLoading"
          :data="dataList"
          :columns="tableColumns"
          :row-key="rowKey"
          :style="{ height: `${tableHeight}px` }"
          :flex-height="true"
        />
      </template>
      <template #footer>
        <TableFooter :pagination="pagination" />
      </template>
    </TableBody>
  </div>
</template>

<script lang="ts">
  import { post, get } from '@/api/http'
  import { getTaskList } from '@/api/url'
  import { renderTag } from '@/hooks/form'
  import { usePagination, useRowKey, useTable, useTableColumn, useTableHeight } from '@/hooks/table'
  import { DataFormType, FormItem } from '@/types/components'
  import {
    DataTableColumn,
    NAvatar,
    NCheckbox,
    NCheckboxGroup,
    NDatePicker,
    NInput,
    NSelect,
    NSpace,
    NTimePicker,
    SelectOption,
    useMessage,
  } from 'naive-ui'
  import { defineComponent, h, onMounted, ref } from 'vue'
  const conditionItems: Array<FormItem> = [
    {
      key: 'task_id',
      label: '任务ID',
      value: ref(null),
      render: (formItem) => {
        return h(NInput, {
          value: formItem.value.value,
          onUpdateValue: (val) => {
            formItem.value.value = val
          },
          placeholder: '请输入任务ID',
        })
      },
    },
    {
      key: 'library',
      label: '插件类别',
      value: ref(null),
      optionItems: [
        {
          label: '短信',
          value: 'sms',
        },
        {
          label: '微信',
          value: 'wechat',
        },
        {
          label: '电话',
          value: 'telephone',
        },
        {
          label: '邮件',
          value: 'email',
        },
      ],
      render: (formItem) => {
        return h(NSelect, {
          options: formItem.optionItems as Array<SelectOption>,
          value: formItem.value.value,
          placeholder: '请选择插件类别',
          onUpdateValue: (val) => {
            formItem.value.value = val
          },
        })
      },
    },
    {
      key: 'date',
      label: '日期',
      value: ref(null),
      render: (formItem) => {
        return h(NDatePicker, {
          value: formItem.value.value,
          placeholder: '请选择日期',
          style: 'width: 100%',
          onUpdateValue: (val) => {
            formItem.value.value = val
          },
          type: 'date',
        })
      },
    },
  ]
  export default defineComponent({
    name: 'task',
    setup() {
      const searchForm = ref<DataFormType | null>(null)
      const pagination = usePagination(doRefresh)
      pagination.pageSize = 20
      const table = useTable()
      const message = useMessage()
      const rowKey = useRowKey('task_id')
      const query_params = ref({})
      const tableColumns = useTableColumn(
        [
          table.selectionColumn,
          table.indexColumn,
          {
            title: 'ID',
            key: 'task_id',
          },
          {
            title: '插件类型',
            key: 'library',
            width: 80,
            render: (rowData) => {
              if (rowData.library == 'sms') {
                return h('div', '短信')
              } else if (rowData.library == 'wechat') {
                return h('div', '微信')
              } else if (rowData.library == 'telephone') {
                return h('div', '电话')
              } else if (rowData.library == 'email') {
                return h('div', '邮件')
              }
              return h('div', rowData.library)
            },
          },
          {
            title: '状态',
            key: 'status',
          },
          {
            title: '队列',
            key: 'task_queue',
          },
          {
            title: '回调接口',
            key: 'webhook',
            width: 180,
            render: (rowData) => {
              return h('div', 'test')
            },
          },
          {
            title: '状态',
            key: 'status',
            render: (rowData) =>
              renderTag(!!rowData.status ? '正常' : '异常', {
                type: !!rowData.status ? 'success' : 'error',
                size: 'small',
              }),
          },
        ],
        {
          align: 'center',
        } as DataTableColumn
      )
      function doRefresh() {
        get({
          url: getTaskList,
          data: () => {
            return {
              query: JSON.stringify(query_params.value),
              page: pagination.page,
              page_size: pagination.pageSize,
            }
          },
        })
          .then((res) => {
            table.handleSuccess(res)
            pagination.Count = res.count
            pagination.setTotalSize(res.count || 10)
          })
          .catch(console.log)
      }
      function onSearch() {
        // message.success(
        //   '模拟查询成功，参数为：' + JSON.stringify(searchForm.value?.generatorParams())
        // )
        let data = searchForm.value?.generatorParams()
        for (let key in data) {
          if (data[key] === null) {
            delete data[key]
          }
        }
        query_params.value = data
        doRefresh()
        // console.log(JSON.stringify(searchForm.value?.generatorParams()))
      }
      function onResetSearch() {
        searchForm.value?.reset()
      }
      onMounted(async () => {
        table.tableHeight.value = await useTableHeight()
        doRefresh()
      })
      return {
        ...table,
        rowKey,
        pagination,
        searchForm,
        tableColumns,
        conditionItems,
        onSearch,
        onResetSearch,
      }
    },
  })
</script>

<style lang="scss" scoped>
  .avatar-container {
    position: relative;
    width: 30px;
    height: 30px;
    margin: 0 auto;
    vertical-align: middle;
    .avatar {
      width: 100%;
      height: 100%;
      border-radius: 50%;
    }
    .avatar-vip {
      border: 2px solid #cece1e;
    }
    .vip {
      position: absolute;
      top: 0;
      right: -9px;
      width: 15px;
      transform: rotate(60deg);
    }
  }
  .gender-container {
    .gender-icon {
      width: 20px;
    }
  }
</style>
