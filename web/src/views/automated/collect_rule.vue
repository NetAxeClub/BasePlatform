<template>
  <div class="main-container">
    <TableBody>
      <template #header>
        <TableHeader
          :show-filter="false"
          title="查询条件"
          @search="onSearch"
          @reset-search="onResetSearch"
        >
          <template #search-content> </template>
          <template #table-config>
            <TableConfig @update-border="onUpdateBorder" @refresh="doRefresh" />
            <SortableTable
              class="ml-4"
              :columns="tableColumns"
              @update="onUpdateTable"
            />
          </template>
          <template #top-right>
            <n-button type="info" size="small" @click="new_collect_show = true"
              >新建规则</n-button
            >
          </template>
        </TableHeader>
      </template>
      <template #default>
        <DataForm
          ref="searchForm"
          :form-config="{
            labelWidth: 60
          }"
          :options="conditionItems"
          preset="grid-item"
        />
        <n-space class="control_button">
          <n-button type="info" size="small" @click="doRefresh()"
            >查询</n-button
          >
          <n-button type="warning" size="small">重置</n-button>
        </n-space>
        <n-data-table
          :loading="tableLoading"
          :data="dataList"
          :columns="tableColumns"
          :single-line="!bordered"
          :row-key="rowKey"
        />
      </template>
      <template #footer>
        <TableFooter :pagination="pagination" />
      </template>
    </TableBody>
    <!--编辑下发指令模态框-->
    <n-modal v-model:show="showEditExecuteModal">
      <n-card
        style="width: 600px"
        title="编辑下发指令"
        :bordered="false"
        size="medium"
        role="dialog"
        aria-modal="true"
      >
        <v-ace-editor
          v-model:value="new_collect_form.execute"
          lang="yaml"
          theme="monokai"
          style="height: 500px"
          :options="ace_option"
        />
        <template #footer>
          <div class="flex justify-end">
            <n-space>
              <n-button type="primary" size="small" @click="EditExecuteBtn"
                >确定</n-button
              >
            </n-space>
          </div>
        </template>
      </n-card>
    </n-modal>
    <!--编辑模态框-->
    <n-modal v-model:show="showEditModal">
      <n-card
        style="width: 900px"
        title="编辑采集规则"
        :bordered="false"
        size="medium"
        role="dialog"
        aria-modal="true"
      >
        <template #header-extra></template>
        <n-form
          label-align="left"
          label-placement="left"
          :model="new_collect_form"
          label-width="120"
        >
          <n-form-item label="规则">
            <n-input
              v-model:value="new_collect_form.name"
              type="text"
              placeholder="规则名"
            />
          </n-form-item>
          <n-form-item label="执行模块">
            <n-select
              v-model:value="new_collect_form.module"
              filterable
              placeholder="执行模块"
              :options="module_option"
            />
          </n-form-item>
          <n-form-item label="执行方法">
            <n-select
              v-model:value="new_collect_form.method"
              filterable
              placeholder="执行方法"
              :options="method_option"
            />
          </n-form-item>
          <n-form-item label="运算符">
            <n-input
              v-model:value="new_collect_form.operation"
              type="text"
              placeholder="运算符"
              :disabled="true"
            />
          </n-form-item>
        </n-form>
        <n-data-table
          :key="(row:any) => row.id"
          :columns="matchRuleColumns"
          :data="match_rule_data"
          :pagination="paginationRef"
          :on-update:page="handlePageChange"
        />
        <template #footer>
          <div class="flex justify-end">
            <n-space>
              <n-button type="primary" size="small" @click="EditConfirm"
                >确定</n-button
              >
            </n-space>
          </div>
        </template>
      </n-card>
    </n-modal>
    <!--新建规则模态框-->
    <n-modal v-model:show="new_collect_show"
      ><n-card
        style="width: 500px"
        title="新建采集规则"
        :bordered="false"
        size="medium"
        role="dialog"
        aria-modal="true"
      >
        <n-form
          label-align="left"
          label-placement="left"
          :model="new_collect_form"
          label-width="120"
        >
          <n-form-item label="规则">
            <n-input
              v-model:value="new_collect_form.name"
              type="text"
              placeholder="规则名"
            />
          </n-form-item>
          <n-form-item label="执行模块">
            <n-select
              v-model:value="new_collect_form.module"
              filterable
              placeholder="执行模块"
              :options="module_option"
            />
          </n-form-item>
          <n-form-item label="执行方法">
            <n-select
              v-model:value="new_collect_form.method"
              filterable
              placeholder="执行方法"
              :options="method_option"
            />
          </n-form-item>
          <n-form-item label="运算符">
            <n-input
              v-model:value="new_collect_form.operation"
              type="text"
              placeholder="运算符"
            />
          </n-form-item>
        </n-form>
        <template #footer>
          <div class="flex justify-end">
            <n-space>
              <n-button type="warning" size="tiny"> 取消</n-button>
              <n-button type="info" size="tiny" @click="new_collect_submit()">
                确认</n-button
              >
            </n-space>
          </div>
        </template>
      </n-card>
    </n-modal>
  </div>
</template>

<script lang="ts">
import {
  deviceCollect,
  collection_rule_api,
  collection_rule_url,
  collection_match_rule_url
} from '@/api/url'
import {
  TableActionModel,
  useTable,
  useRenderAction,
  useTableColumn,
  usePagination
} from '@/hooks/table'
import {
  defineComponent,
  h,
  nextTick,
  onMounted,
  reactive,
  ref,
  computed,
  shallowReactive
} from 'vue'
import _ from 'lodash'
import {
  DataTableColumn,
  NInput,
  NSelect,
  SelectOption,
  useDialog,
  useMessage,
  NPopconfirm,
  NForm,
  NFormItem,
  NButton
} from 'naive-ui'
import {
  DataFormType,
  ModalDialogType,
  FormItem,
  TablePropsType
} from '@/types/components'
import usePost from '@/hooks/usePost'
import useGet from '@/hooks/useGet'
import usePatch from '@/hooks/usePatch'
import usePut from '@/hooks/usePut'
import useDelete from '@/hooks/useDelete'
import { sortColumns } from '@/utils'
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

const ShowOrEdit = defineComponent({
  props: {
    value: [String, Number],
    onUpdateValue: [Function, Array]
  },
  setup(props) {
    const isEdit = ref(false)
    const inputRef = ref(null)
    const inputValue = ref(props.value)
    function handleOnClick() {
      isEdit.value = true
      nextTick(() => {
        inputRef.value.focus()
      })
    }
    function handleChange() {
      props.onUpdateValue(inputValue.value)
      isEdit.value = false
    }
    return () =>
      h(
        'div',
        {
          style: 'min-height: 22px',
          onClick: handleOnClick
        },
        isEdit.value
          ? h(NInput, {
              ref: inputRef,
              value: inputValue.value,
              onUpdateValue: (v) => {
                inputValue.value = v
              },
              onChange: handleChange,
              onBlur: handleChange
            })
          : props.value
      )
  }
})

export default defineComponent({
  name: 'CollectRule',
  components: {
    VAceEditor
  },
  setup() {
    const get = useGet()
    const post = usePost()
    const patch = usePatch()
    const put = usePut()
    const api_delete = useDelete()
    const ace_option = ref({ fontSize: 14 })
    const class_options = shallowReactive([]) as Array<any>
    const method_options = shallowReactive([]) as Array<any>
    const selectValues = ref('')
    const showEditModal = ref(false)
    const showEditExecuteModal = ref(false)
    const itemFormOptions = [
      {
        key: 'name',
        label: '方案名',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: ''
          })
        }
      },
      {
        key: 'memo',
        label: '备注',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: ''
          })
        }
      },
      {
        key: 'netconf_class',
        label: 'Netconf连接类',
        value: ref(null),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            required: true,
            filterable: true,
            placeholder: '请选择Netconf连接类',
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            'on-update:value': get_method_by_class.bind(formItem.value.value)
          })
        }
      },
      {
        key: 'netconf_method',
        label: 'Netconf方法',
        value: ref(null),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            filterable: true,
            maxTagCount: 3,
            multiple: true,
            required: true,
            placeholder: '请选择netconf_method',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      }
    ] as Array<FormItem>
    const new_collect_show = ref(false)
    // 规则匹配方法
    const match_rule_data = ref<
      {
        rule: any
        name: string
        fields: any
        operator: string
        value: string
      }[]
    >([])
    // 执行模块
    const module_option = ref([
      {
        label: '南向驱动',
        value: 'SouthDriver'
      },
      {
        label: '基础平台',
        value: 'BASE'
      }
    ])
    // 执行方法
    const method_option = ref([
      {
        label: 'NETCONF',
        value: 'NETCONF'
      },
      {
        label: 'CLI',
        value: 'CLI'
      }
    ])
    const new_collect_form = ref({
      name: '',
      module: 'BASE',
      method: 'CLI',
      operation: ' ',
      execute: ' '
    })
    const conditionItems: Array<FormItem> = [
      {
        key: 'name',
        label: '方案名',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: ''
          })
        }
      }
    ]
    const table = useTable()
    const pagination = usePagination(doRefresh)
    pagination.pageSize = 10
    pagination.page = 1
    // pagination.limit = 10
    // pagination.start = 0
    const chart_show = ref(false)
    const searchForm = ref<DataFormType | null>(null)
    const message = useMessage()
    const naiveDailog = useDialog()
    const getDataIndex = (id: any) => {
      return match_rule_data.value.findIndex((item) => item.id === id)
    }
    // 匹配字段
    const matchRuleSelectFieldOption = ref([])
    // 匹配选项
    const matchRuleSelectOperOption = ref([
      {
        label: '精确匹配',
        value: '__exact'
      },
      {
        label: '不区分大小写的精确匹配',
        value: '__iexact'
      },
      {
        label: '包含',
        value: '__contains'
      },
      {
        label: '不区分大小写包含',
        value: '__icontains'
      },
      {
        label: '以指定值开头',
        value: '__startswith'
      },
      {
        label: '以指定值结尾',
        value: '__endswith'
      },
      {
        label: '不区分大小写以指定值开头',
        value: '__istartswith'
      },
      {
        label: '不区分大小写以指定值结尾',
        value: '__iendswith'
      }
    ])
    const current_selected_row_field = ref('')
    // 定义规则匹配方法的表格字段
    const matchRuleColumns = reactive(
      useTableColumn(
        [
          {
            title: '规则',
            key: 'name',
            width: '50px'
          },
          {
            title: '匹配字段',
            key: 'fields',
            width: '180px',
            render(row) {
              const index = getDataIndex(row.id)
              return h(NSelect, {
                options:
                  matchRuleSelectFieldOption.value as Array<SelectOption>,
                filterable: true,
                value: match_rule_data.value[index].fields,
                placeholder: '请选择字段',
                onUpdateValue: (val) => {
                  match_rule_data.value[index].fields = val
                }
              })
            }
          },
          {
            title: '操作符',
            key: 'operator',
            width: '200px',
            render(row) {
              const index = getDataIndex(row.id)
              return h(NSelect, {
                options: matchRuleSelectOperOption.value as Array<SelectOption>,
                filterable: true,
                value: match_rule_data.value[index].operator,
                placeholder: '请选择操作符',
                onUpdateValue: (val) => {
                  console.log(val)
                  match_rule_data.value[index].operator = val
                }
              })
            }
          },
          {
            title: '匹配值',
            key: 'value',
            width: '200px',
            render(row) {
              const index = getDataIndex(row.id)
              return h(ShowOrEdit, {
                value: row.value,
                onUpdateValue(v) {
                  match_rule_data.value[index].value = v
                }
              })
            }
          },
          {
            title: '动作',
            key: 'id',
            width: '100px',
            render(row) {
              const index = getDataIndex(row.id)
              return [
                h(
                  NPopconfirm,
                  {
                    positiveButtonProps: {
                      size: 'tiny',
                      type: 'success'
                    },
                    negativeButtonProps: {
                      size: 'tiny',
                      type: 'default'
                    },
                    onPositiveClick: delete_rule_match_row.bind(null, row)
                  },
                  {
                    trigger: () => {
                      return h(
                        NButton,
                        {
                          type: 'error',
                          size: 'tiny'
                        },
                        { default: () => '删除' }
                      )
                    },
                    default: () => {
                      return '确认删除该规则？'
                    }
                  }
                ),
                h(
                  NButton,
                  {
                    type: 'success',
                    size: 'tiny',
                    onClick: add_match_rule_btn.bind(null, row)
                  },
                  { default: () => '新增' }
                )
              ]
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    // 定义规则表格字段
    const tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '规则名',
            key: 'name'
          },
          {
            title: '执行模块',
            key: 'module',
            render: (rowData) => {
              return module_option.value
                .map((val) => {
                  if (val.value == rowData.module) {
                    return val.label
                  }
                })
                .join(' ')
            }
          },
          {
            title: '执行方法',
            key: 'method'
          },
          {
            title: '执行内容',
            key: 'execute',
            render: (rowData) => {
              return h(
                NButton,
                {
                  onClick: change_commands.bind(null, rowData),
                  type: 'success',
                  size: 'tiny'
                },
                () => h('span', {}, '修改下发指令')
              )
            }
          },
          {
            title: '数据插件',
            key: 'plugin'
          },
          {
            title: '匹配规则',
            key: 'plugin',
            render: (rowData) => {
              return h(
                'div',
                {},
                rowData.match_rule.map((item) => {
                  return h(
                    'p',
                    {},
                    item.name +
                      ': ' +
                      item.fields +
                      ' ' +
                      item.operator_name +
                      '' +
                      item.value
                  )
                })
              )
            }
          },
          {
            title: '动作',
            key: 'id',
            render: (rowData) => {
              return [
                h(
                  NButton,
                  {
                    onClick: edit_collect_rule.bind(null, rowData),
                    type: 'success',
                    size: 'tiny'
                  },
                  () => h('span', {}, '编辑')
                ),
                h(
                  NButton,
                  {
                    onClick: edit_collect_rule.bind(null, rowData),
                    type: 'success',
                    size: 'tiny'
                  },
                  () => h('span', {}, '验证')
                ),
                h(
                  NPopconfirm,
                  {
                    positiveButtonProps: {
                      size: 'tiny',
                      type: 'success'
                    },
                    negativeButtonProps: {
                      size: 'tiny',
                      type: 'default'
                    },
                    onPositiveClick: delete_rule_row.bind(null, rowData)
                  },
                  {
                    trigger: () => {
                      return h(
                        NButton,
                        {
                          type: 'error',
                          size: 'tiny'
                        },
                        { default: () => '删除' }
                      )
                    },
                    default: () => {
                      return '确认删除该规则？'
                    }
                  }
                )
              ]
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const searchDataFormRef = ref<DataFormType | null>(null)
    const rowData = ref<Object | null>(null)
    const second_password = ref('')

    function onSearch() {
      //console.log(searchForm.value?.generatorParams())
    }

    function onResetSearch() {
      searchForm.value?.reset()
    }

    function onUpdateBorder(isBordered: boolean) {
      table.bordered.value = isBordered
    }

    function onUpdateTable(newColumns: Array<TablePropsType>) {
      sortColumns(tableColumns, newColumns)
    }
    // 页面首次加载和重载
    function doRefresh() {
      get({
        url: collection_rule_api,
        data: () => {
          return {
            start: (pagination.page - 1) * pagination.pageSize,
            limit: pagination.pageSize,
            _: Date.now()
          }
        }
      }).then((res) => {
        //  //console.log(res)
        table.handleSuccess(res)
        pagination.setTotalSize(res.count || 10)
      })
      get({
        url: collection_rule_url,
        data: () => {
          return {
            get_cmdb_field: '1'
          }
        }
      }).then((res) => {
        // console.log(res)
        matchRuleSelectFieldOption.value = res.data.map((v) => ({
          label: v.label,
          value: v.value
        }))
      })
    }
    // 编辑下发指令 确认 按钮
    function EditExecuteBtn() {
      console.log(new_collect_form.value.id)
      put({
        url: collection_rule_api + new_collect_form.value.id + '/',
        data: {
          execute: new_collect_form.value.execute
        }
      }).then((res) => {
        console.log(res)
        if (res.code == 200) {
          message.success('更新规则成功')
          showEditExecuteModal.value = false
          nextTick(() => {
            doRefresh()
          })
        } else {
          message.error(res.msg)
        }
      })
    }
    // 删除采集规则
    function delete_rule_row(row) {
      api_delete({
        url: collection_rule_api + row.id + '/'
      }).then((res) => {
        if (res.code == 204) {
          message.success('操作成功')
          nextTick(() => {
            doRefresh()
          })
        }
      })
    }
    // 删除规则匹配方法
    function delete_rule_match_row(row) {
      api_delete({
        url: collection_match_rule_url + row.id + '/'
      }).then((res) => {
        if (res.code == 204) {
          message.success('操作成功')
          nextTick(() => {
            get({
              url: collection_match_rule_url,
              data: () => {
                return {
                  rule: new_collect_form.value.id
                }
              }
            }).then((res) => {
              // console.log(res)
              match_rule_data.value = res.results
              new_collect_form.value.operation = res.results
                .map((item) => item.name)
                .sort()
                .join(' and ')
            })
          })
        }
      })
    }
    // 编辑规则模态框 确认按钮
    function EditConfirm() {
      // 更新规则
      if ('id' in new_collect_form.value) {
        put({
          url: collection_rule_api + new_collect_form.value.id + '/',
          data: new_collect_form.value
        }).then((res) => {
          if (res.code == 200) {
            message.success('更新规则成功')
          } else {
            message.error(res.msg)
          }
          // console.log(res)
        })
      }
      // 更新规则匹配方法
      match_rule_data.value.forEach((item) => {
        // console.log(item)
        if ('id' in item) {
          put({
            url: collection_match_rule_url + item.id + '/',
            data: item
          }).then((res) => {
            if (res.code == 200) {
              message.success('更新规则' + item.name + '成功')
            } else {
              message.error(res.msg)
            }
            // console.log(res)
          })
        } else {
          post({
            url: collection_match_rule_url,
            data: item
          }).then((res) => {
            if (res.code == 201) {
              message.success('新增规则' + item.name + '成功')
            }
            // console.log(res)
          })
        }
      })
      showEditModal.value = false
      nextTick(() => {
        doRefresh()
      })
    }
    // 编辑规则模态框打开
    function edit_collect_rule(item: any) {
      //console.log('编辑采集方案', item)
      // console.log('row', item)
      new_collect_form.value = item
      get({
        url: collection_match_rule_url,
        data: () => {
          return {
            rule: item.id
          }
        }
      }).then((res) => {
        // console.log(res)
        match_rule_data.value = res.results
        new_collect_form.value.operation = res.results
          .map((item) => item.name)
          .sort()
          .join(' and ')
        showEditModal.value = true
      })
    }
    // 添加一条匹配规则
    function add_match_rule_btn(row) {
      let _tmp = match_rule_data.value.map((v) => v.name).sort()
      let nextValue = String.fromCharCode(
        _tmp[_tmp.length - 1].charCodeAt(0) + 1
      )
      match_rule_data.value.push({
        rule: row.id,
        name: nextValue,
        fields: matchRuleSelectFieldOption.value[0].value,
        operator: matchRuleSelectOperOption.value[0].value,
        value: ''
      })
      new_collect_form.value.operation = match_rule_data.value
        .map((item) => item.name)
        .sort()
        .join(' and ')
    }
    // 编辑下发指令1
    function change_commands(item) {
      showEditExecuteModal.value = true
      //  //console.log('修改当前行命令', item.commands)
      new_collect_form.value = item
    }

    function get_method_by_class(item) {
      //console.log('当前选中class', item)
      get({
        url: deviceCollect,
        data: () => {
          return {
            netconf_class: item,
            get_method: 1
          }
        }
      }).then((res) => {
        itemFormOptions[4].optionItems.length = 0
        res.data.forEach((ele) => {
          var dict = {
            value: ele,
            label: ele
          }
          itemFormOptions[4].optionItems.push(dict)
        })
        // nextTick(() => {
        //   itemFormOptions[4].optionItems.splice(0, 0, { value: '', label: '' })
        // })
      })
    }

    function rowKey(rowData) {
      return rowData.id
    }

    // 新建采集规则
    function new_collect_submit() {
      console.log(new_collect_form.value)
      post({
        url: collection_rule_api,
        data: new_collect_form.value
      }).then((res) => {
        console.log(res)
        if (res.code == 201) {
          message.success('操作成功')
          new_collect_show.value = false
          nextTick(() => {
            doRefresh()
          })
        }
      })
    }
    const match_rule_page = ref(1)
    const paginationRef = computed(() => ({
      pageSize: 10,
      page: match_rule_page.value
    }))
    const handlePageChange = (curPage) => {
      match_rule_page.value = curPage
    }
    onMounted(doRefresh)

    return {
      EditConfirm,
      conditionItems,
      showEditExecuteModal,
      showEditModal,
      delete_rule_row,
      delete_rule_match_row,
      matchRuleSelectFieldOption,
      add_match_rule_btn,
      matchRuleSelectOperOption,
      current_selected_row_field,
      handlePageChange,
      match_rule_page,
      paginationRef,
      matchRuleColumns,
      match_rule_data,
      new_collect_submit,
      class_options,
      method_options,
      method_option,
      module_option,
      selectValues,
      new_collect_show,
      new_collect_form,
      patch,
      post,
      edit_collect_rule,
      searchDataFormRef,
      EditExecuteBtn,
      second_password,
      rowData,
      tableColumns,
      change_commands,
      pagination,
      searchForm,
      onResetSearch,
      onSearch,
      ...table,
      itemFormOptions,
      ace_option,
      rowKey,
      onUpdateTable,
      onUpdateBorder,
      doRefresh,
      chart_show
    }
  }
})
</script>

<style lang="scss">
.control_button {
  float: right;
  padding-bottom: 10px;
}
</style>
