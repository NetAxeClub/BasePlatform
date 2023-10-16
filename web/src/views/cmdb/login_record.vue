<template>
  <div class="main-container">
    <TableBody>
      <template #header>
        <TableHeader
          :show-filter="false"
          title=""
          @search="onSearch"
          @reset-search="onResetSearch"
        >
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
          <template #table-config>
            <TableConfig @update-border="onUpdateBorder" @refresh="doRefresh" />
            <SortableTable
              class="ml-4"
              :columns="tableColumns"
              @update="onUpdateTable"
            />
          </template>
          <!--          <template #top-right>-->
          <!--            <DeleteButton @delete="onDeleteItem"/>-->
          <!--          </template>-->
        </TableHeader>
      </template>
      <template #default>
        <n-grid x-gap="12" :cols="3">
          <n-grid-item>
            <n-card
              :content-style="{ padding: '10px' }"
              :header-style="{ padding: '10px' }"
              :segmented="true"
            >
              <template #header>
                <!--      <n-skeleton text style="width: 50%" v-if="loading" />-->
                <!--      <template v-else>-->
                <div class="text-sm">查询条件</div>
                <!--      </template>-->
              </template>
              <DataForm
                ref="searchForm"
                :form-config="{
                  labelWidth: 60
                }"
                style="width: 100%; height: 180px"
                :options="conditionItems"
                preset="form-item"
              />
            </n-card>
          </n-grid-item>

          <n-grid-item>
            <LoginRecordChart ref="loginRecordChart" />
          </n-grid-item>
          <n-grid-item>
            <NotWorkTimeChart ref="notWorkTimeChart" />
          </n-grid-item>
        </n-grid>

        <n-space style="float: right; padding: 20px">
          <n-button
            style="float: right"
            size="small"
            type="info"
            @click="onSearch()"
            >查询</n-button
          >
          <n-button
            style="float: right"
            size="small"
            type="success"
            @click="onResetSearch()"
            >重置</n-button
          >
        </n-space>
        <n-data-table
          :loading="tableLoading"
          :data="dataList"
          :columns="tableColumns"
          :single-line="!bordered"
          :row-key="rowKey"
          default-expand-all
        />
      </template>
      <template #footer>
        <TableFooter :pagination="pagination" />
      </template>
    </TableBody>
    <ModalDialog
      ref="LogmodalDialog"
      title="登录日志回放"
      @confirm="onDataFormConfirm"
      :style="{ height: '800px', width: '800px' }"
    >
      <template #content>
        <div class="home" ref="player">
          <n-button @click="setSrc" type="info" style="margin-bottom: 20px"
            >开始播放</n-button
          >
          <!-- <iframe :src="log_src" frameborder="0"></iframe> -->
          <asciinema-player
            startAt="0:00"
            poster="0:00"
            :speed="1"
            :fontSize="12"
            :src="data_url"
            theme="tango"
          />
        </div>
      </template>
    </ModalDialog>
    <!-- <ModalDialog ref="WebsshmodalDialog" title="Webssh">
      <template>
        <div class="console" id="terminal"></div>
      </template>
    </ModalDialog> -->
  </div>
</template>

<script lang="ts">
import AsciinemaPlayer from '@/components/asciinema-player.vue'
import { getLoginRecordList, media_url } from '@/api/url'
import { useTable, useTableColumn, usePagination } from '@/hooks/table'
import {
  defineComponent,
  h,
  // nextTick,
  onMounted,
  reactive,
  ref
  // shallowReactive
} from 'vue'
import _ from 'lodash'
import {
  DataTableColumn,
  NInput,
  NLog,
  // NSelect,
  // SelectOption,
  useDialog,
  useMessage,
  NButton,
  NDatePicker
} from 'naive-ui'
import {
  DataFormType,
  ModalDialogType,
  FormItem,
  TablePropsType
} from '@/types/components'
// import usePost from '@/hooks/usePost'
// import { renderTag } from '@/hooks/form'
import useGet from '@/hooks/useGet'
import { sortColumns } from '@/utils'
import LoginRecordChart from './chart/LoginRecordChart.vue'
import NotWorkTimeChart from './chart/NotWorkTimeChart.vue'
// import cast from "./c.cast"
export default defineComponent({
  name: 'LoginRecord',
  components: {
    LoginRecordChart,
    NotWorkTimeChart,
    AsciinemaPlayer
  },
  setup() {
    const conditionItems: Array<FormItem> = [
      {
        key: 'start_time',
        label: '开始时间',
        value: ref(null),
        render: (formItem) => {
          return h(NDatePicker, {
            value: formItem.value.value,
            placeholder: '请选择日期',
            style: 'width: 100%',
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            type: 'date'
          })
        }
      },
      {
        key: 'end_time',
        label: '结束时间',
        value: ref(null),
        render: (formItem) => {
          return h(NDatePicker, {
            value: formItem.value.value,
            placeholder: '请选择日期',
            style: 'width: 100%',
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            type: 'date'
          })
        }
      },
      {
        key: 'admin_server',
        label: '设备IP',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            onKeyup: (Event) => {
              if (Event.keyCode == 13) {
                onSearch()
              }
            },
            placeholder: '请输入管理IP'
          })
        }
      }
    ]
    // const safeHtml = any
    // const videoNumber = ref('')
    const log_src = ref('')
    const data_url = ref('')
    const table = useTable()
    const pagination = usePagination(doRefresh)
    pagination.pageSize = 10
    pagination.limit = 10
    pagination.start = 0
    const searchForm = ref<DataFormType | null>(null)
    const message = useMessage()
    const naiveDailog = useDialog()
    const tableColumns = reactive(
      useTableColumn(
        [
          {
            type: 'expand',
            renderExpand: (rowData) => {
              return h(NLog, {
                log: rowData.admin_record_cmds,
                rows: 15
              })
            }
          },
          {
            title: '用户',
            key: 'admin_login_user'
          },
          {
            title: '设备地址',
            key: 'admin_server'
          },
          {
            title: '链接模式',
            key: 'admin_record_mode'
          },
          {
            title: '远程地址',
            key: 'admin_remote_ip'
          },
          {
            title: '开始时间',
            key: 'admin_start_time'
          },
          {
            title: '登录时间',
            key: 'admin_login_status_time'
          },
          {
            title: '操作',
            key: 'actions',
            render: (rowData) => {
              return h(
                NButton,
                {
                  type: 'warning',
                  size: 'tiny',
                  onClick: log_video_show.bind(null, rowData)
                },
                () => h('span', {}, '日志回放')
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const itemDataFormRef = ref<DataFormType | null>(null)
    const searchDataFormRef = ref<DataFormType | null>(null)
    const modalDialog = ref<ModalDialogType | null>(null)
    const LogmodalDialog = ref<ModalDialogType | null>(null)
    const WebsshmodalDialog = ref<ModalDialogType | null>(null)
    const row_data = ref({
      admin_record_file: ref('')
    })
    const get = useGet()

    function onSearch() {
      //console.log(searchForm.value?.generatorParams())
      const search_form = searchForm.value?.generatorParams()
      get({
        url:
          getLoginRecordList +
          '?start_time=' +
          getFormtTime(search_form.start_time) +
          '&end_time=' +
          getFormtTime(search_form.end_time) +
          '&admin_server=' +
          search_form.admin_server,
        data: () => {
          return {
            start: 0,
            // pageSize: pagination.pageSize,
            limit: pagination.pageSize,
            ordering: '-admin_start_time',
            page: 1,
            _: Date.now()
          }
        }
      }).then((res) => {
        //console.log(res)
        if (res.code === 200) {
          message.success('查询成功')
          table.handleSuccess(res)
          pagination.setTotalSize(res.count || 10)
        } else {
          message.success('查询失败:' + res.msg)
          table.handleSuccess(res)
          pagination.setTotalSize(res.count || 10)
        }
      })
    }

    function onResetSearch() {
      //  //console.log(searchForm.value.options[0]['value'].value =null)
      searchForm.value.options[0]['value'].value = null
      searchForm.value.options[1]['value'].value = null
      searchForm.value.options[2]['value'].value = ''

      // searchForm.value?.reset()
    }

    function onUpdateBorder(isBordered: boolean) {
      table.bordered.value = isBordered
    }

    function onUpdateTable(newColumns: Array<TablePropsType>) {
      sortColumns(tableColumns, newColumns)
    }

    function doRefresh() {
      get({
        url: getLoginRecordList,
        data: () => {
          return {
            start: (pagination.page - 1) * pagination.pageSize,
            // pageSize: pagination.pageSize,
            limit: pagination.pageSize,
            ordering: '-admin_start_time'
          }
        }
      }).then((res) => {
        //  //console.log(res)
        table.handleSuccess(res)
        pagination.setTotalSize(res.count || 10)
      })
    }

    function getFormtTime(dateTime: string | number | Date | null) {
      if (dateTime != null) {
        //若传入的dateTime为字符串类型，需要进行转换成数值，若不是无需下面注释代码
        //var time = parseInt(dateTime)
        var date = new Date(dateTime)
        //获取年份
        var YY = date.getFullYear()
        //获取月份
        var MM =
          date.getMonth() + 1 < 10
            ? '0' + (date.getMonth() + 1)
            : date.getMonth() + 1
        //获取日期
        var DD = date.getDate() < 10 ? '0' + date.getDate() : date.getDate()
        //返回时间格式： 2020-11-09
        return YY + '-' + MM + '-' + DD
      } else {
        return ''
      }
    }

    function onDataFormConfirm() {
      if (itemDataFormRef.value?.validator()) {
        modalDialog.value?.toggle()
        naiveDailog.success({
          title: '提示',
          positiveText: '确定',
          content:
            '模拟部门添加/编辑成功，数据为：' +
            JSON.stringify(itemDataFormRef.value.generatorParams())
        })
      }
    }
    function setSrc() {
      data_url.value = media_url + row_data.value['admin_record_file']
      // console.log('log_src')
      console.log(data_url.value)
    }
    function log_video_show(item: any) {
      // log_src.value

      LogmodalDialog.value?.toggle()
      // console.log('当前行', item)

      row_data.value = item
      // let url = window.location.host
      // window.open(
      //   log_src.value,
      //   'newwindow',
      //   'height=500, width=1005, top=200, left=200, toolbar=no, menubar=no, scrollbars=no, location=no, status=no'
      // )
    }

    function rowKey(rowData: any) {
      return rowData.id
    }

    onMounted(doRefresh)
    return {
      log_src,
      itemDataFormRef,
      searchDataFormRef,
      onDataFormConfirm,
      tableColumns,
      row_data,
      setSrc,
      log_video_show,
      pagination,
      searchForm,
      onResetSearch,
      onSearch,
      ...table,
      rowKey,
      modalDialog,
      WebsshmodalDialog,
      LogmodalDialog,
      conditionItems,
      onUpdateTable,
      onUpdateBorder,
      doRefresh,
      getFormtTime,
      data_url
    }
  }
})
</script>

<style scoped>
.light-green {
  height: 108px;
  background-color: rgba(0, 128, 0, 0.12);
}
</style>
