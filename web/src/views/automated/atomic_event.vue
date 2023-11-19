<template>
  <div class="main-container">
    <TableBody>
      <template #header>
        <TableHeader :show-filter="true" @search="selectFun">
          <template #table-config>
            <TableConfig @update-border="onUpdateBorder" @refresh="doRefresh" />
            <SortableTable
              class="ml-4"
              :columns="tableColumns"
              @update="onUpdateTable"
            />
          </template>
          <template #top-right>
            <n-button type="info" size="small" @click="chart_show = true"
              >事件中心运营数据</n-button
            >
          </template>
          <template #search-content>
            <DataForm
              ref="searchForm"
              :form-config="{
                labelWidth: 60
              }"
              :options="conditionItems"
              preset="grid-item"
            />
          </template>
        </TableHeader>
      </template>
      <template #default>
        <n-data-table
          :loading="tableLoading"
          :single-line="!bordered"
          :data="dataList"
          :columns="tableColumns"
          :row-key="rowKey"
          @update:checked-row-keys="handleSelectionChange"
        />
      </template>
      <template #footer>
        <TableFooter :pagination="pagination" />
      </template>
    </TableBody>
    <ModalDialog
      ref="modalDialog"
      title="查看参数"
      :style="{ height: '600px', width: '800px' }"
    >
      <template #content>
        <v-ace-editor
          v-model:value="kwargs_value"
          lang="json"
          theme="monokai"
          style="height: 620px"
          :options="ace_option"
        />
      </template>
    </ModalDialog>
    <ModalDialog
      ref="commands_modalDialog"
      title="查看命令"
      :style="{ height: '600px', width: '800px' }"
    >
      <template #content>
        <!-- <DataForm
          ref="itemDataFormRef"
          :form-config="{ labelWidth: 60 }"
          preset="form-item"
          :options="commands_value"
        /> -->
        <v-ace-editor
          v-model:value="commands_value"
          lang="json"
          theme="monokai"
          style="height: 620px"
          :options="ace_option"
        />
      </template>
    </ModalDialog>
    <ModalDialog
      ref="back_modalDialog"
      title="查看回退命令"
      :style="{ height: '600px', width: '800px' }"
    >
      <template #content>
        <!-- <DataForm ref="itemDataFormRef" :form-config="{ labelWidth: 60 }" preset="form-item"
                    :options="back_value" /> -->
        <v-ace-editor
          v-model:value="back_value"
          lang="json"
          theme="monokai"
          style="height: 620px"
          :options="ace_option"
        />
      </template>
    </ModalDialog>

    <ModalDialog
      ref="result_modalDialog"
      title="查看配置过程"
      :style="{ height: '600px', width: '1000px' }"
    >
      <template #content>
        <!-- <DataForm ref="itemDataFormRef" :form-config="{ labelWidth: 60 }" preset="form-item"
                    :options="result_value" /> -->
        <v-ace-editor
          v-model:value="result_value"
          lang="json"
          theme="monokai"
          style="height: 620px"
          :options="ace_option"
        />
      </template>
    </ModalDialog>

    <n-modal
      v-model:show="chart_show"
      preset="dialog"
      header-style="padding: 10px 20px"
      title="事件中心运营数据"
      :style="{ height: '380px', width: '1300px' }"
    >
      <n-grid x-gap="12" :cols="3">
        <n-gi>
          <TaskModuleChart ref="taskModuleChart" />
        </n-gi>
        <n-gi>
          <EventTaskUserChart ref="eventTaskUserChart" />
        </n-gi>
        <n-gi>
          <EventCommitTimeChart ref="eventCommitTimeChart" />
        </n-gi>
      </n-grid>
    </n-modal>
  </div>
</template>

<script lang="ts">
import { get } from '@/api/http'
import { AutoWorkFlow } from '@/api/url'
import { renderTag } from '@/hooks/form'
import {
  TableActionModel,
  usePagination,
  useRenderAction,
  useRowKey,
  useTable,
  useTableColumn
} from '@/hooks/table'
import {
  FormItem,
  ModalDialogType,
  TablePropsType,
  DataFormType
} from '@/types/components'
import { sortColumns } from '@/utils'
import {
  DataTableColumn,
  useDialog,
  useMessage,
  NInput,
  NSelect,
  SelectOption,
  NButton,
  NDropdown
} from 'naive-ui'
import { defineComponent, h, nextTick, onMounted, reactive, ref } from 'vue'
import TaskModuleChart from './chart/TaskModuleChart.vue'
import EventTaskUserChart from './chart/EventTaskUserChart.vue'
import EventCommitTimeChart from './chart/EventCommitTimeChart.vue'
import { VAceEditor } from 'vue3-ace-editor'
import 'ace-builds/src-noconflict/mode-yaml'
import 'ace-builds/src-noconflict/mode-html'
import 'ace-builds/src-noconflict/theme-chrome'
import ace from 'ace-builds'
import modeYamlUrl from 'ace-builds/src-noconflict/mode-yaml?url'
ace.config.setModuleUrl('ace/mode/yaml', modeYamlUrl)
import modenunjucksUrl from 'ace-builds/src-noconflict/mode-nunjucks?url'
ace.config.setModuleUrl('ace/mode/nunjucks', modenunjucksUrl)
import modeJsonUrl from 'ace-builds/src-noconflict/mode-json?url'
ace.config.setModuleUrl('ace/mode/json', modeJsonUrl)
import themeMonokaiUrl from 'ace-builds/src-noconflict/theme-monokai?url'
ace.config.setModuleUrl('ace/theme/monokai', themeMonokaiUrl)
export default defineComponent({
  name: 'AtomicEvent',
  components: {
    TaskModuleChart,
    EventTaskUserChart,
    EventCommitTimeChart,
    VAceEditor
  },
  setup() {
    const table = useTable()
    const pagination = usePagination(doRefresh)
    const navieDialog = useDialog()
    const message = useMessage()
    const rowKey = useRowKey('id')
    const chart_show = ref(false)
    const tableColumns = reactive(
      useTableColumn(
        [
          // table.selectionColumn,
          // table.indexColumn,
          {
            title: '任务ID',
            key: 'task_id',
            width: 80
          },
          {
            title: '设备IP',
            key: 'device',
            width: 120
          },
          {
            title: '配置模式',
            key: 'method',
            width: '120px'
          },
          {
            title: '用户',
            key: 'commit_user',
            width: '80px'
          },
          {
            title: '调用IP',
            key: 'remote_ip',
            width: 120
          },
          {
            title: '来源',
            key: 'origin'
          },
          {
            title: '更新时间',
            key: 'commit_time',
            width: '150px'
          },
          {
            title: '任务模块',
            key: 'task'
          },
          // {
          //   title: '调用IP',
          //   key: 'remote_ip',
          // },
          {
            title: '任务参数',
            key: 'task_args',
            render: (rowData) => {
              return useRenderAction([
                {
                  label: '查看参数',
                  onClick: show_args.bind(null, rowData),
                  type: 'info'
                }
              ] as TableActionModel[])
            }
          },
          {
            title: '下发命令',
            key: 'task_args',
            render: (rowData) => {
              return useRenderAction([
                {
                  label: '查看命令',
                  onClick: show_commands.bind(null, rowData),
                  type: 'info'
                }
              ] as TableActionModel[])
            }
          },
          {
            title: '回退命令',
            key: 'task_args',
            render: (rowData) => {
              return useRenderAction([
                {
                  label: '查看回退',
                  onClick: show_back.bind(null, rowData),
                  type: 'info'
                }
              ] as TableActionModel[])
            }
          },
          {
            title: '操作过程',
            key: 'task_args',
            render: (rowData) => {
              return useRenderAction([
                {
                  label: '查看过程',
                  onClick: show_result.bind(null, rowData)
                }
              ] as TableActionModel[])
            }
          },
          {
            title: '流转状态',
            key: 'state',
            render: (rowData) => {
              if (rowData.state === 'Published') {
                return useRenderAction([
                  {
                    label: '发布成功',
                    // onClick: onWebssh.bind(null, rowData),
                    type: 'success'
                  }
                ] as TableActionModel[])
              }
              if (rowData.state === 'Failed') {
                return useRenderAction([
                  {
                    label: '失败',
                    // onClick: onWebssh.bind(null, rowData),
                    type: 'error'
                  }
                ] as TableActionModel[])
              }
            }
            // render: (rowData) => {
            //   return useRenderAction([
            //     {
            //       label: '查看过程',
            //       // onClick: onWebssh.bind(null, rowData),
            //     },
            //
            //   ] as TableActionModel[])
            // },
          },
          {
            title: '动作',
            key: 'task_args',
            width: 100,
            render: (rowData) => {
              return h(
                NDropdown,
                {
                  onSelect: (key: string | number) =>
                    handleSelect(rowData, key),
                  options: [
                    {
                      label: '回退',
                      key: '回退'
                    },
                    {
                      label: '批准',
                      key: '批准'
                    },
                    {
                      label: '归档',
                      key: '归档'
                    }
                  ],
                  trigger: 'click'
                },
                {
                  trigger: () => h('span', {}, () => h('span', {}, '动作')),
                  default: () =>
                    h(
                      NButton,
                      {
                        type: 'info',
                        size: 'tiny'
                      },
                      () => h('span', {}, '动作')
                    )
                }
              )
              // return useRenderAction([
              //   {
              //     label: '动作',
              //     // onClick: onWebssh.bind(null, rowData),
              //   },
              //
              // ] as TableActionModel[])
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const query_params = ref({})
    const modalDialog = ref<ModalDialogType | null>(null)
    const commands_modalDialog = ref<ModalDialogType | null>(null)
    const back_modalDialog = ref<ModalDialogType | null>(null)
    const result_modalDialog = ref<ModalDialogType | null>(null)
    const ace_option = ref({ fontSize: 14 })
    const kwargs_value = ref('')
    const commands_value = ref('')
    const back_value = ref('')
    const result_value = ref('')
    const conditionItems: Array<FormItem> = [
      {
        key: 'task',
        label: '任务类型',
        value: ref(null),
        render: (formItem) => {
          return h(NSelect, {
            options: [
              {
                label: 'DNAT',
                value: 'DNAT'
              },
              {
                label: 'SNAT',
                value: 'SNAT'
              },
              {
                label: '安全策略',
                value: '安全策略'
              },
              {
                label: '一键封堵',
                value: '一键封堵'
              }
            ] as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择任务类型',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      }
    ]

    const searchForm = ref<DataFormType | null>(null)
    function doRefresh() {
      let params = {
        start: (pagination.page - 1) * pagination.pageSize,
        limit: pagination.pageSize
      }
      if (JSON.stringify(query_params.value) != '{}') {
        for (let key in query_params.value) {
          params[key] = query_params.value[key]
        }
      }
      get({
        url: AutoWorkFlow,
        data: () => {
          return params
        }
      }).then((res) => {
        table.handleSuccess(res)
        pagination.setTotalSize(res.count || 10)
      })
      //   .catch(console.log)
    }
    function selectFun() {
      query_params.value = searchForm.value?.generatorParams()
      doRefresh()
    }
    function onUpdateTable(newColumns: Array<TablePropsType>) {
      sortColumns(tableColumns, newColumns)
    }

    function onUpdateBorder(isBordered: boolean) {
      table.bordered.value = isBordered
    }

    function show_args(item: any) {
      console.log('查看参数', item.kwargs)
      modalDialog.value?.toggle()
      nextTick(() => {
        kwargs_value.value = item.kwargs.replaceAll(',', ',\n')
        // kwargs_value.forEach((it) => {
        //   const key = it.key
        //   const propName = item[key]
        //   it.value.value = propName.replaceAll(',', '\n')
        // })
      })
    }

    function show_commands(item: any) {
      // console.log('查看命令', item.commands)
      commands_modalDialog.value?.toggle()
      nextTick(() => {
        commands_value.value = item.commands.replaceAll(',', ',\n')
      })
    }

    function show_back(item: nay) {
      // console.log('查看回退命令')
      back_modalDialog.value?.toggle()
      nextTick(() => {
        back_value.value = item.back_off_commands.replaceAll(',', ',\n')
      })
    }

    function show_result(item: any) {
      // console.log(item)
      result_modalDialog.value?.toggle()
      nextTick(() => {
        if (item.task_result) {
          result_value.value = item.task_result.replaceAll(',', ',\n')
        } else {
          result_value.value = ''
        }
      })
    }

    function handleSelect(row, key) {
      console.log('选中key', key)
    }

    onMounted(doRefresh)
    return {
      chart_show,
      handleSelect,
      show_args,
      show_commands,
      show_back,
      result_value,
      show_result,
      modalDialog,
      commands_modalDialog,
      back_modalDialog,
      result_modalDialog,
      kwargs_value,
      commands_value,
      back_value,
      ...table,
      rowKey,
      tableColumns,
      pagination,
      onUpdateTable,
      selectFun,
      searchForm,
      query_params,
      conditionItems,
      doRefresh,
      onUpdateBorder,
      ace_option
    }
  }
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
