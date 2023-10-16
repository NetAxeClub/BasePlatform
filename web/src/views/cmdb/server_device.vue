<template>
  <div class="main-container">
    <n-tabs type="line" animated @update:value="tab_change">
      <n-tab-pane name="物理服务器" tab="物理服务器">
        <TableBody>
          <template #header>
            <TableHeader
              :show-filter="false"
              title="查询条件"
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
                <TableConfig
                  @update-border="onUpdateBorder"
                  @refresh="doRefresh"
                />
                <!-- <SortableTable
                  class="ml-4"
                  :columns="tableColumns"
                  @update="onUpdateTable"
                /> -->
              </template>
              <template #top-right>
                <n-button type="info" size="small" @click="server_entering">
                  资产录入
                </n-button>
                <n-button type="success" size="small" @click="new_account">
                  新建账户
                </n-button>
                <!-- <n-button type="primary" size="small" @click="import_from_nvwa">
                  从女娲导入
                </n-button> -->
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
            <n-space style="float: right; padding-bottom: 20px">
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
                >重置
              </n-button>
            </n-space>

            <n-data-table
              :loading="tableLoading"
              :data="dataList"
              :columns="tableColumns"
              :single-line="!bordered"
              :row-key="rowKey"
              @update:expanded-row-keys="handleExpand"
            />
          </template>
          <template #footer>
            <TableFooter :pagination="pagination" />
          </template>
        </TableBody>
      </n-tab-pane>
      <n-tab-pane name="容器" tab="容器">
        <TableBody>
          <template #header>
            <TableHeader title="容器列表" :show-filter="false">
              // eslint-disable-next-line vue/no-lone-template
              <template name="table-config"></template>
              <template #top-right>
                <n-input
                  v-model:value="container_keyword"
                  type="text"
                  size="small"
                  placeholder="容器实例关键字"
                  @keyup.enter.native="filter_container_list"
                />
              </template>
            </TableHeader>
          </template>
          <template #default>
            <n-data-table
              :data="
                container_list.slice(
                  (container_page - 1) * container_pageSize,
                  container_page * container_pageSize
                )
              "
              :columns="container_tableColumns"
              :row-key="ContainerRowKey"
              :loading="tableLoading"
            />
          </template>
          <template #footer>
            <div class="flex justify-center">
              <n-pagination
                v-model:page="container_page"
                :page-count="container_pageCount"
                show-size-picker
                :page-sizes="container_pageSizes"
              />
              <!--              <n-button v-if="showRefresh" circle class="ml-1" size="small" type="primary" @click="refresh">-->
              <!--                <template #icon>-->
              <!--                  <n-icon>-->
              <!--                    &lt;!&ndash;                    <RefreshIcon />&ndash;&gt;-->
              <!--                  </n-icon>-->
              <!--                </template>-->
              <!--              </n-button>-->
            </div>
          </template>
        </TableBody>
      </n-tab-pane>
    </n-tabs>
    <ModalDialog
      ref="NewAssetModalDialog"
      title="服务器资产新增"
      @confirm="NewAssetConfirm"
      :style="{ height: '800px', width: '600px' }"
    >
      <template #content>
        <DataForm
          ref="NewAsset_itemDataFormRef"
          :form-config="{ labelWidth: 60 }"
          preset="grid-two-item"
          :options="NewAsset_itemFormOptions"
        />
      </template>
    </ModalDialog>
    <ModalDialog
      ref="NewAccountModalDialog"
      title="账户新增"
      @confirm="NewAccountConfirm"
      :style="{ height: '300px', width: '500px' }"
    >
      <template #content>
        <DataForm
          ref="NewAccount_itemDataFormRef"
          :form-config="{ labelWidth: 85 }"
          :options="NewAccount_itemFormOptions"
        />
      </template>
    </ModalDialog>
    <ModalDialog
      ref="modalDialog"
      title="资产数据维护"
      @confirm="onDataFormConfirm"
      :style="{ height: '800px', width: '600px' }"
    >
      <template #content>
        <DataForm
          ref="itemDataFormRef"
          :form-config="{ labelWidth: 60 }"
          preset="grid-two-item"
          :options="itemFormOptions"
        />
      </template>
    </ModalDialog>
    <ModalDialog
      ref="show_password_modalDialog"
      title="查看管理账户信息"
      :style="{ height: '500px', width: '500px' }"
    >
      <template #content>
        <h3>请输入二级密码</h3>
        <n-space>
          <n-input
            type="password"
            show-password-on="mousedown"
            placeholder="回车查看密码"
            v-model:value="second_password"
            @keyup.enter.native="second_onConfirm"
          />
        </n-space>
      </template>
    </ModalDialog>
    <ModalDialog
      ref="account_modalDialog"
      title="账户信息"
      :style="{ height: '500px', width: '500px' }"
    >
      <template #content>
        <n-input v-model:value="account_info" />
      </template>
    </ModalDialog>
    <ModalDialog
      ref="connect_account_modalDialog"
      title="关联设备管理账户"
      :style="{ height: '500px', width: '500px' }"
      @confirm="ConnectAccountConfirm"
    >
      <template #content>
        <DataForm
          ref="connect_account_DataFormRef"
          :form-config="{
            labelWidth: 60
          }"
          :options="connect_account_FormOptions"
        />
      </template>
    </ModalDialog>
  </div>
</template>

<script lang="ts">
import {
  getServerDeviceList,
  getCmdbIdcList,
  getCmdbRoleList,
  getServerVendorList,
  getCategoryList,
  get_server_expand,
  get_cmdb_idc_model,
  get_cmdb_rack,
  getContainerList,
  getCmdbServerModelList,
  getCmdbIdcModelList,
  getCmdbRackList,
  getcmdb_accountList,
  serverWebSsh,
  server_account_url
} from '@/api/url'
import {
  // TableActionModel,
  useTable,
  // useRenderAction,
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
  NForm,
  NFormItem,
  NButton,
  NPopconfirm
} from 'naive-ui'
import {
  DataFormType,
  ModalDialogType,
  FormItem,
  TablePropsType
} from '@/types/components'
import usePost from '@/hooks/usePost'
import usePut from '@/hooks/usePut'
// import { renderTag } from '@/hooks/form'
import useGet from '@/hooks/useGet'
import { sortColumns } from '@/utils'
import router from '@/router'

export default defineComponent({
  name: 'ServerDevice',
  setup() {
    const row_item = ref({
      account: ref([])
    })
    const connect_account_FormOptions = [
      {
        key: 'account',
        label: '管理账号',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem: any) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择协议端口',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
              //console.log(val)
            }
          })
        }
      }
    ]
    const itemFormOptions = [
      {
        key: 'name',
        label: '设备名称',
        type: 'input',
        value: ref(null),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (newVal: any) => {
              formItem.value.value = newVal
            },
            maxlength: 50,
            placeholder: ''
          })
        },
        validator: (formItem, message) => {
          if (!formItem.value.value) {
            message.error('请输入部门名称')
            return false
          }
          return true
        }
      },
      {
        key: 'idc',
        label: '机房',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(
            NSelect,
            {
              options: formItem.optionItems as Array<SelectOption>,
              value: formItem.value.value,
              placeholder: '请选择机房',
              filterable: true,
              onUpdateValue: (val) => {
                formItem.value.value = val
                //console.log('选择val', val)
                // select_idc.bind(null, val)
              },
              'on-update:value': select_idc.bind(formItem.value.value)

              // onUpdateValue:(val) => {
              //   formItem.value.value = val
              //   //  //console.log(val);
              //   select_idc.bind(null, val)
              // }
              // onUpdateValue: (val) => {
              //   // formItem.value.value = val
              //   formItem.value.value = val
              //   select_idc.bind(val)
              // },
            },
            { default: () => formItem }
          )
        }
      },
      {
        key: 'manage_ip',
        label: '管理地址',
        value: ref(null),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (newVal: any) => {
              formItem.value.value = newVal
            },
            maxlength: 50,
            placeholder: ''
          })
        }
      },
      {
        key: 'idc_model',
        label: '模块',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择模块',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'vendor',
        label: '供应商',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择供应商',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'rack',
        label: '机柜',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择机柜',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'u_location',
        label: 'U位',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '起始U位'
          })
        }
      },
      {
        key: 'model',
        label: '类型',
        value: ref<number>(0),
        optionItems: [
          // { value: '', label: '' },
          { value: 2, label: '服务器' },
          { value: 4, label: '虚拟机' },
          { value: 6, label: '容器' }
          // { value: 3, label: '备用' },
        ],
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择类型',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
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
            placeholder: '请输入备注',
            disabled: true
          })
        }
      },
      {
        key: 'serial_num',
        label: '序列号',
        value: ref(''),

        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入序列号',
            disabled: true
          })
        }
      },
      {
        key: 'status',
        label: '状态',
        value: ref<number>(0),
        optionItems: [
          { value: '', label: '' },
          { value: 0, label: '在线' },
          { value: 1, label: '下线' },
          { value: 2, label: '挂牌' },
          { value: 3, label: '备用' }
        ],
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择供应商',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'system',
        label: '系统',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '系统'
            // disabled: true,
          })
        }
      },
      {
        key: 'status',
        label: '虚机',
        value: ref<number>(0),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择供应商',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'cpu_model',
        label: 'CPU型号',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'CPU型号'
            // disabled: true,
          })
        }
      },
      {
        key: 'manager_name',
        label: '归属人',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '归属人'
            // disabled: true,
          })
        }
      },
      {
        key: 'cpu_number',
        label: 'CPU核数',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'CPU核数'
            // disabled: true,
          })
        }
      },
      {
        key: 'manager_account',
        label: '',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: ''
            // disabled: true,
          })
        }
      },
      {
        key: 'vcpu_number',
        label: 'CPU逻辑核数',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'CPU逻辑核数'
            // disabled: true,
          })
        }
      },
      {
        key: 'manager_tel',
        label: '联系电话',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '联系电话'
            // disabled: true,
          })
        }
      },
      {
        key: 'purpose',
        label: '用途',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '用途'
            // disabled: true,
          })
        }
      },
      {
        key: 'id',
        label: 'id',
        value: ref<number>(0),
        render: (formItem) => {
          return h(NInput, {
            value: JSON.stringify(formItem.value.value),
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            hidden: true
            // placeholder: '用途',
            // disabled: true,
          })
        }
      }
    ] as Array<FormItem>

    const conditionItems: Array<FormItem> = [
      {
        key: 'name',
        label: '设备名',
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
            placeholder: '请输入设备名'
          })
        }
      },
      {
        key: 'vendor',
        label: '供应商',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择供应商',
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'idc',
        label: '机房',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(
            NSelect,
            {
              options: formItem.optionItems as Array<SelectOption>,
              value: formItem.value.value,
              placeholder: '请选择机房',
              filterable: true,
              onUpdateValue: (val) => {
                formItem.value.value = val
                //console.log('选择val', val)
                // select_idc.bind(null, val)
              },
              'on-update:value': select_idc.bind(formItem.value.value)

              // onUpdateValue:(val) => {
              //   formItem.value.value = val
              //   //  //console.log(val);
              //   select_idc.bind(null, val)
              // }
              // onUpdateValue: (val) => {
              //   // formItem.value.value = val
              //   formItem.value.value = val
              //   select_idc.bind(val)
              // },
            },
            { default: () => formItem }
          )
        }
      },
      {
        key: 'rack',
        label: '机柜',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择机柜',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'manage_ip',
        label: '管理IP',
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
      },

      {
        key: 'idc_model',
        label: '模块',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择模块',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'search',
        label: '搜索',
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
            placeholder: '关键字'
          })
        }
      },

      {
        key: 'serial_num',
        label: '序列号',
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
            placeholder: '请输入序列号'
          })
        }
      },
      {
        key: 'u_location',
        label: 'U位',
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
            placeholder: '起始U位'
          })
        }
      },
      {
        key: 'server_admin',
        label: '归属人',
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
            placeholder: '归属人'
          })
        }
      }
    ]
    const NewAsset_itemFormOptions: Array<FormItem> = [
      {
        key: 'name',
        label: '名称',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入名称'
          })
        }
      },
      {
        key: 'idc',
        label: '机房',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(
            NSelect,
            {
              options: formItem.optionItems as Array<SelectOption>,
              value: formItem.value.value,
              placeholder: '请选择机房',
              filterable: true,
              onUpdateValue: (val) => {
                formItem.value.value = val
                //console.log('选择val', val)
                // select_idc.bind(null, val)
              },
              'on-update:value': select_idc.bind(formItem.value.value)

              // onUpdateValue:(val) => {
              //   formItem.value.value = val
              //   //  //console.log(val);
              //   select_idc.bind(null, val)
              // }
              // onUpdateValue: (val) => {
              //   // formItem.value.value = val
              //   formItem.value.value = val
              //   select_idc.bind(val)
              // },
            },
            { default: () => formItem }
          )
        }
      },
      {
        key: 'manage_ip',
        label: '管理IP',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入管理IP'
          })
        }
      },
      {
        key: 'idc_model',
        label: '模块',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择模块',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },

      {
        key: 'vendor',
        label: '供应商',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择供应商',
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            'on-update:value': get_info_by_vendor.bind(formItem.value.value)
          })
        }
      },
      {
        key: 'rack',
        label: '机柜',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择机柜',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },

      {
        key: 'model',
        label: '型号',
        value: ref(''),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择型号',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },

      {
        key: 'u_location',
        label: 'U位',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'U位'
          })
        }
      },
      {
        key: 'sub_asset_type',
        label: '类型',
        value: ref(''),
        optionItems: [
          { value: 1, label: '虚拟机' },
          { value: 0, label: '服务器' }
        ],
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择类型',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
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
            placeholder: '请输入备注'
          })
        }
      },
      {
        key: 'serial_num',
        label: '序列号',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入序列号'
          })
        }
      },
      {
        key: 'status',
        label: '状态',
        value: ref<number>(0),
        optionItems: [
          { value: '', label: '' },
          { value: 0, label: '在线' },
          { value: 1, label: '下线' },
          { value: 2, label: '挂牌' },
          { value: 3, label: '备用' }
        ],
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择型号',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'system',
        label: '系统',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '操作系统'
          })
        }
      },
      {
        key: 'hosted_on',
        label: '虚机',
        value: ref<number>(0),
        optionItems: shallowReactive([] as Array<SelectOption>),
        render: (formItem) => {
          return h(NSelect, {
            options: formItem.optionItems as Array<SelectOption>,
            value: formItem.value.value,
            placeholder: '请选择虚机',
            filterable: true,
            onUpdateValue: (val) => {
              formItem.value.value = val
            }
          })
        }
      },
      {
        key: 'cpu_model',
        label: 'CPU型号',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'CPU型号'
          })
        }
      },
      {
        key: 'manager_name',
        label: '归属人',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '归属人'
          })
        }
      },
      {
        key: 'cpu_number',
        label: 'CPU核数',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'CPU核数'
          })
        }
      },
      
      {
        key: 'vcpu_number',
        label: 'CPU逻辑核数',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: 'CPU逻辑核数'
          })
        }
      },
      {
        key: 'manager_tel',
        label: '联系电话',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '联系电话'
          })
        }
      },
      {
        key: 'purpose',
        label: '用途',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '用途'
          })
        }
      }
    ]
    const NewAccount_itemFormOptions: Array<FormItem> = [
      {
        key: 'name',
        label: '账户',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入账户名称'
          })
        }
      },
      {
        key: 'username',
        label: '登录用户名',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,

            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入用户名'
          })
        }
      },
      {
        key: 'password',
        label: '登录密码',
        value: ref(''),
        render: (formItem) => {
          return h(NInput, {
            value: formItem.value.value,
            type: 'password',
            onUpdateValue: (val) => {
              formItem.value.value = val
            },
            placeholder: '请输入密码'
          })
        }
      }
    ]
    const account_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '账户',
            key: 'account__username'
          },
          {
            title: '密码',
            key: 'account__password'
          },
          {
            title: '协议',
            key: 'protocol_port__protocol'
          },
          {
            title: '端口',
            key: 'protocol_port__port'
          }
        ],
        { align: 'center' } as DataTableColumn
      )
    )
    const table = useTable()
    const pagination = usePagination(doRefresh)
    pagination.pageSize = 10
    pagination.limit = 10
    pagination.start = 0
    const searchForm = ref<DataFormType | null>(null)
    const connect_account_DataFormRef = ref<DataFormType | null>(null)
    const message = useMessage()
    const naiveDailog = useDialog()
    const container_keyword = ref('')
    const container_list = shallowReactive([]) as Array<any>
    const connect_account_modalDialog = ref<ModalDialogType | null>(null)
    const device_info = ref(0)
    const container_pageSizes = [
      {
        label: '10 每页',
        value: 10
      },
      {
        label: '50 每页',
        value: 50
      },
      {
        label: '100 每页',
        value: 100
      },
      {
        label: '200 每页',
        value: 200
      }
    ]
    const container_page = ref<number>(1)
    const container_pageSize = ref<number>(10)
    const container_pageCount = ref<number>(1)
    const container_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '服务名',
            key: 'name'
          },
          {
            title: '镜像',
            key: 'service'
          },
          {
            title: '工作目录',
            key: 'working_dir'
          },
          {
            title: '配置文件',
            key: 'config_files'
          },
          {
            title: '项目',
            key: 'project'
          },
          {
            title: '访问路径',
            key: 'url_path'
          },
          {
            title: '宿主机名',
            key: 'config_files'
          },
          {
            title: '宿主机IP',
            key: 'on_server_ip'
          },
          {
            title: '创建时间',
            key: 'creation_time'
          },

          {
            title: '操作',
            key: 'actions',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  // onPositiveClick: () => delete_address_detail(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                  // onclick: delete_silience.bind(null, rowData)
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error' }, () => h('span', {}, '删除')),
                  default: () =>
                    h('span', {}, () => '请确认删除操作,删除将立即删除屏蔽记录')
                }
              )
              // return useRenderAction([
              //   {
              //     label: '删除',
              //     type:"error",
              //     onClick: delete_service_detail.bind(null, rowData),
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
    const tableColumns = reactive(
      useTableColumn(
        [
          table.selectionColumn,
          // table.indexColumn,
          {
            type: 'expand',
            expandable: () => true,
            renderExpand: (rowData) => {
              return h('DataForm', { preset: 'grid-item' }, [
                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(
                      NFormItem,
                      {
                        label: '设备名: ',
                        style: {
                          height: '0px',
                          width: '30%'
                        }
                      },
                      () => h('span', {}, '' + rowData.name)
                    ),
                    h(
                      NFormItem,
                      { label: '供应商: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.vendor_name)
                    ),
                    h(
                      NFormItem,
                      { label: '所属机房:', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.idc_name)
                    )
                  ]
                ),
                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(
                      NFormItem,
                      { label: '管理IP:', style: { width: '30%' } },
                      () => h('span', {}, ' ' + rowData.manage_ip)
                    ),
                    h(
                      NFormItem,
                      { label: '类别: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.asset_type)
                    ),
                    h(
                      NFormItem,
                      { label: '操作系统:', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.system)
                    )
                  ]
                ),
                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(
                      NFormItem,
                      { label: '序列号: ', style: { width: '30%' } },
                      () => h('span', '' + rowData.serial_num)
                    ),
                    h(
                      NFormItem,
                      { label: '硬件型号: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.model_name)
                    ),
                    h(
                      NFormItem,
                      { label: '内核版本:', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.kernel)
                    )
                  ]
                ),
                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(
                      NFormItem,
                      { label: '设备状态: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.status_name)
                    ),
                    h(
                      NFormItem,
                      { label: 'CPU型号: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.cpu_model)
                    ),
                    h(
                      NFormItem,
                      { label: '机房模块:', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.idc_model_name)
                    )
                  ]
                ),

                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(
                      NFormItem,
                      { label: '管理账户\n:', style: { width: '30%' } },
                      () => h('span', {}, ' ' + rowData.to_account)
                    ),
                    h(
                      NFormItem,
                      { label: '物理CPU核数\n:', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.cpu_number)
                    ),
                    h(
                      NFormItem,
                      { label: '机柜\n: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.rack_name)
                    )
                  ]
                ),
                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(
                      NFormItem,
                      { label: '逻辑CPU核数\n:', style: { width: '30%' } },
                      () => h('span', {}, ' ' + rowData.vcpu_number)
                    ),
                    h(
                      NFormItem,
                      { label: 'U位\n: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.u_location)
                    ),
                    h(
                      NFormItem,
                      { label: '主机变量\n: ', style: { width: '30%' } },
                      () => h('span', {}, '' + rowData.host_vars)
                    )
                  ]
                ),
                h(
                  NForm,
                  {
                    labelWidth: '160px',
                    inline: true,
                    labelPlacement: 'left',
                    style: { height: '5px', fontSize: '12px' }
                  },
                  [
                    h(NFormItem, { label: '账户', style: { width: '30%' } }, [
                      h(
                        NButton,
                        {
                          text: true,
                          color: '#204d74',
                          onclick: show_account_handleClick.bind(null, rowData)
                        },
                        () => h('span', {}, '查看账户')
                      ),
                      h(
                        NButton,
                        {
                          text: true,
                          color: '#204d74',
                          onclick: connect_account_handleClick.bind(
                            null,
                            rowData
                          )
                        },
                        () => h('span', {}, '关联账户')
                      )
                    ])
                  ]
                )
              ])
            }
          },
          {
            title: '设备名称',
            key: 'name'
          },
          {
            title: '管理IP',
            key: 'manage_ip'
          },
          {
            title: '厂商',
            key: 'vendor_name',
            width: 80
          },
          {
            title: '型号',
            key: 'model_name'
          },
          {
            title: '类型',
            key: 'asset_type',
            width: 100
          },
          {
            title: '宿主机',
            key: 'hosted_on_ip'
          },
          {
            title: '归属人',
            key: 'manager_name'
          },
          {
            title: '用途',
            key: 'purpose'
          },
          {
            title: '操作系统',
            key: 'system'
          },
          {
            title: '机房',
            key: 'idc_name'
          },
          {
            title: '机柜',
            key: 'rack_name'
          },
          {
            title: 'U位',
            key: 'u_location'
          },
          {
            title: '编辑',
            key: 'actions',
            render: (rowData) => {
              return h(
                NButton,
                {
                  type: 'success',
                  size: 'tiny',
                  onClick: EditServer.bind(null, rowData)
                },
                () => h('span', {}, 'EDIT')
              )
            }
          },
          {
            title: '操作',
            key: 'actions',
            render: (rowData) => {
              return h(
                NButton,
                {
                  type: 'success',
                  size: 'tiny',
                  onClick: EditServer.bind(null, rowData)
                },
                () => h('span', {}, '扫描')
              )
            }
          },
          {
            title: 'WEBSSH',
            key: 'actions',
            render: (rowData) => {
              return h(
                NButton,
                {
                  type: 'success',
                  size: 'tiny',
                  onClick: onWebssh.bind(null, rowData)
                },
                () => h('span', {}, 'WEBSSH')
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
    const NewAsset_itemDataFormRef = ref<DataFormType | null>(null)
    const NewAccount_itemDataFormRef = ref<DataFormType | null>(null)
    const searchDataFormRef = ref<DataFormType | null>(null)
    const modalDialog = ref<ModalDialogType | null>(null)
    const NewAssetModalDialog = ref<ModalDialogType | null>(null)
    const WebsshmodalDialog = ref<ModalDialogType | null>(null)
    const NewAccountModalDialog = ref<ModalDialogType | null>(null)
    const show_password_modalDialog = ref<ModalDialogType | null>(null)
    const account_modalDialog = ref<ModalDialogType | null>(null)
    const rowData = ref<Object | null>(null)
    const second_password = ref('')
    const account_info = ref('')
    const get = useGet()
    const post = usePost()
    const put = usePut()

    function onSearch() {
      //console.log(searchForm.value?.generatorParams())
      const search_form = searchForm.value?.generatorParams()
      searchDataFormRef.value = search_form
      get({
        url:
          getServerDeviceList +
          '?name=' +
          search_form.name +
          '&manage_ip=' +
          search_form.manage_ip +
          '&vendor=' +
          search_form.vendor +
          '&idc=' +
          search_form.idc +
          '&serial_num=' +
          search_form.serial_num +
          '&rack=' +
          search_form.rack +
          '&idc_model=' +
          search_form.idc_model +
          '&serial_num=' +
          search_form.serial_num +
          '&manager_account=' +
          search_form.server_admin +
          '&search=' +
          search_form.search,
        data: () => {
          return {
            start: 0,
            // pageSize: pagination.pageSize,
            limit: pagination.pageSize
          }
        }
      }).then((res) => {
        //console.log(res)

        // message.success('查询成功')
        table.handleSuccess(res)
        pagination.setTotalSize(res.count || 10)
      })
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

    function get_container_list() {
      //getContainerList
      get({
        url: getContainerList,
        data: () => {
          return {
            limit: 10000,
            _: Date.now()
          }
        }
      }).then((res) => {
        container_list.push(...res.results)
        container_page.value = 1
        container_pageSize.value = 10
        container_pageCount.value = Math.ceil(res.count / 10)
      })
    }

    function doRefresh() {
      //console.log(searchDataFormRef.value)
      let request_url = ''
      let search_form = searchDataFormRef.value
      if (searchDataFormRef.value === null) {
        request_url = getServerDeviceList
      } else {
        request_url =
          getServerDeviceList +
          '?name=' +
          search_form.name +
          '&manage_ip=' +
          search_form.manage_ip +
          '&vendor=' +
          search_form.vendor +
          '&idc=' +
          search_form.idc +
          '&serial_num=' +
          search_form.serial_num +
          '&rack=' +
          search_form.rack +
          '&idc_model=' +
          search_form.idc_model +
          '&serial_num=' +
          search_form.serial_num +
          '&manager_account=' +
          search_form.server_admin
      }
      get({
        url: request_url,
        data: () => {
          return {
            start: (pagination.page - 1) * pagination.pageSize,
            // pageSize: pagination.pageSize,
            limit: pagination.pageSize,
            status: 0
          }
        }
      }).then((res) => {
        console.log(res)
        NewAsset_itemFormOptions[13].optionItems.length = 0
        NewAsset_itemFormOptions[13].optionItems = res.results
        table.handleSuccess(res)
        pagination.setTotalSize(res.count)
      })
    }

    function doIdc() {
      get({
        url: getCmdbIdcList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        //  //console.log('idc_res', res)
        //  //console.log(conditionItems)
        const idc_list = res.results
        for (var i = 0; i < idc_list.length; i++) {
          const dict = {
            label: idc_list[i]['name'],
            value: idc_list[i]['id']
          }
          if (conditionItems[2].optionItems != undefined) {
            conditionItems[2].optionItems.push(dict)
          }
          if (NewAsset_itemFormOptions[1].optionItems != undefined) {
            NewAsset_itemFormOptions[1].optionItems.push(dict)
          }
          if (itemFormOptions[1].optionItems != undefined) {
            itemFormOptions[1].optionItems.push(dict)
          }
        }
      })
    }

    function doVendor() {
      get({
        url: getServerVendorList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        //  //console.log('vendor_res', res)
        //  //console.log(conditionItems)
        const idc_list = res.results
        for (var i = 0; i < idc_list.length; i++) {
          const dict = {
            label: idc_list[i]['name'],
            value: idc_list[i]['id']
          }
          if (conditionItems[1].optionItems != undefined) {
            conditionItems[1].optionItems.push(dict)
          }
          if (NewAsset_itemFormOptions[4].optionItems != undefined) {
            NewAsset_itemFormOptions[4].optionItems.push(dict)
          }
          if (itemFormOptions[4].optionItems != undefined) {
            itemFormOptions[4].optionItems.push(dict)
          }
        }
      })
    }

    function doRole() {
      get({
        url: getCmdbRoleList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        //  //console.log('role_res', res)
        //  //console.log(conditionItems)
        const idc_list = res.results
        for (var i = 0; i < idc_list.length; i++) {
          const dict = {
            label: idc_list[i]['name'],
            value: idc_list[i]['id']
          }
          // if (conditionItems[3].optionItems != undefined) {
          //   conditionItems[3].optionItems.push(dict)
          //   // conditionItems[3].optionItems.splice(0, 0, {
          //   //   label: '',
          //   //   value: ''
          //   // });
          // }
        }
      })
    }

    function doCagetory() {
      get({
        url: getCategoryList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        //  //console.log('category_res', res)
        //  //console.log(conditionItems)
        const idc_list = res.results
        for (var i = 0; i < idc_list.length; i++) {
          const dict = {
            label: idc_list[i]['name'],
            value: idc_list[i]['id']
          }
          // if (conditionItems[5].optionItems != undefined) {
          //   conditionItems[5].optionItems.push(dict)
          //   // conditionItems[3].optionItems.splice(0, 0, {
          //   //   label: '',
          //   //   value: ''
          //   // });
          // }
        }
      })
    }

    function select_idc(val: any) {
      //conditionItems
      //  //console.log('select_idc', val)
      get({
        url: get_cmdb_idc_model,
        data: () => {
          return {
            limit: 1000,
            idc: val
          }
        }
      }).then((res) => {
        //  //console.log('idc_model', res)
        //  //console.log(conditionItems)
        const rack_list = res.results
        conditionItems[5].optionItems.length = 0
        for (var i = 0; i < rack_list.length; i++) {
          const dict = {
            label: rack_list[i]['name'],
            value: rack_list[i]['id']
          }

          if (conditionItems[5].optionItems != undefined) {
            conditionItems[5].optionItems.push(dict)
            // conditionItems[3].optionItems.splice(0, 0, {
            //   label: '',
            //   value: ''
            // });
          }
          if (NewAsset_itemFormOptions[3].optionItems != undefined) {
            NewAsset_itemFormOptions[3].optionItems.push(dict)
            // conditionItems[3].optionItems.splice(0, 0, {
            //   label: '',
            //   value: ''
            // });
          }
        }
      })
      get({
        url: get_cmdb_rack,
        data: () => {
          return {
            limit: 1000,
            idc: val
          }
        }
      }).then((res) => {
        //  //console.log('idc_model', res)
        //  //console.log(conditionItems)
        const rack_list = res.results
        conditionItems[3].optionItems.length = 0
        for (var i = 0; i < rack_list.length; i++) {
          const dict = {
            label: rack_list[i]['name'],
            value: rack_list[i]['id']
          }

          if (conditionItems[3].optionItems != undefined) {
            conditionItems[3].optionItems.push(dict)
            // conditionItems[3].optionItems.splice(0, 0, {
            //   label: '',
            //   value: ''
            // });
          }
          if (NewAsset_itemFormOptions[5].optionItems != undefined) {
            NewAsset_itemFormOptions[5].optionItems.push(dict)
            // conditionItems[3].optionItems.splice(0, 0, {
            //   label: '',
            //   value: ''
            // });
          }
        }
      })
    }

    function get_info_by_vendor(item: any) {
      //  //console.log('当前选中供应商', item)
      get({
        url: getCmdbServerModelList,
        data: () => {
          return {
            vendor: item,
            limit: 1000
          }
        }
      }).then((res) => {
        //  //console.log('该供应商型号', res)
        //  //console.log(conditionItems)
        // let filter_list = []
        if (NewAsset_itemFormOptions[6].optionItems !== undefined) {
          NewAsset_itemFormOptions[6].optionItems.length = 0
          let model_list: { value: any; label: any }[] = []
          res.results.forEach((ele: { [x: string]: any }) => {
            let dict = {
              value: ele['id'],
              label: ele['name']
            }
            model_list.push(dict)
          })
          NewAsset_itemFormOptions[6].optionItems.push(...model_list)
        }
      })
    }

    function onDataFormConfirm() {
      if (itemDataFormRef.value?.validator()) {
        modalDialog.value?.toggle()
        //console.log('itemDataFormRef.value', itemDataFormRef.value?.generatorParams())
        const server_info = itemDataFormRef.value?.generatorParams()
        var put_data = new FormData()
        put_data.append('name', server_info['name'])
        put_data.append('manage_ip', server_info['manage_ip'])
        put_data.append('vendor', server_info['vendor'])
        put_data.append('model', server_info['model'])
        put_data.append(
          'sub_asset_type',
          server_info['sub_asset_type'] ? server_info['sub_asset_type'] : ''
        )
        put_data.append('system', server_info['system'])
        put_data.append('cpu_model', server_info['cpu_model'])
        put_data.append(
          'cpu_number',
          server_info['cpu_number'] ? server_info['cpu_number'] : ''
        )
        put_data.append(
          'vcpu_number',
          server_info['vcpu_number'] ? server_info['vcpu_number'] : ''
        )
        put_data.append('purpose', server_info['purpose'])
        put_data.append('idc', server_info['idc'])
        put_data.append('idc_model', server_info['idc_model'])
        put_data.append('rack', server_info['rack'])
        put_data.append('u_location', server_info['u_location'])
        put_data.append('memo', server_info['memo'] ? server_info['memo'] : '')
        put_data.append('status', server_info['status'])
        put_data.append(
          'hosted_on',
          server_info['hosted_on'] ? server_info['hosted_on'] : ''
        )
        put_data.append('manager_name', server_info['manager_name'])
        put_data.append('manager_account', server_info['manager_account'])
        put_data.append('manager_tel', server_info['manager_tel'])
        put({
          url: getServerDeviceList + '/' + server_info['id'] + '/',
          data: put_data
        }).then((res) => {
          if (res) {
            message.success('编辑服务器信息成功')
            doRefresh()
          }
        })

        // naiveDailog.success({
        //   title: '提示',
        //   positiveText: '确定',
        //   content:
        //       '模拟部门添加/编辑成功，数据为：' +
        //       JSON.stringify(itemDataFormRef.value.generatorParams()),
        // })
      }
    }
    function connect_account_handleClick(item: { id: number }) {
      row_item.value = item
      connect_account_modalDialog.value?.toggle()
      device_info.value = item.id
    }
    function show_account_handleClick(item: Object | null) {
      show_password_modalDialog.value?.toggle()
      rowData.value = item
    }

    function server_entering() {
      NewAssetModalDialog.value?.toggle()
    }
    function get_cmdb_account() {
      get({
        url: getcmdb_accountList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        if (connect_account_FormOptions[0].optionItems !== undefined) {
          res.results.forEach((ele: { [x: string]: any }) => {
            var dict = {
              label: ele['name'] + '(' + ele['username'] + ')',
              value: ele['id']
            }
            connect_account_FormOptions[0].optionItems.push(dict)
          })
        }
      })
      //console.log('connect_account_FormOptions', connect_account_FormOptions)
    }
    function isInArray(arr, value) {
      for (var i = 0; i < arr.length; i++) {
        if (value == arr[i]) {
          return true
        }
      }
      return false
    }
    function ConnectAccountConfirm() {
      var connect_account_info =
        connect_account_DataFormRef.value?.generatorParams()
      // console.log(row_item.value['account'])
      // if (
      //   isInArray(row_item.value['account'], connect_account_info['account'])
      // ) {
      //   message.error('不可以关联重复设备账户')
      // } else {
        var account_data = new FormData()
        account_data.append('server', device_info.value.toString())
        account_data.append('account', connect_account_info['account'])
        post({
          url: server_account_url,
          data: account_data
        }).then((res) => {
          if (res) {
            if (res.code === 201) {
              message.success('关联账户成功')
              connect_account_modalDialog.value!.toggle()
              doRefresh()
            }
          }
        })
      // }
    }

    function NewAccountConfirm() {
      //console.log('账户新增确认 ', NewAccount_itemDataFormRef.value.generatorParams())
      let new_account_info = NewAccount_itemDataFormRef.value.generatorParams()
      let new_account_formdata = new FormData()
      new_account_formdata.append('name', new_account_info.name)
      new_account_formdata.append('username', new_account_info.username)
      new_account_formdata.append('password', new_account_info.password)
      post({
        url: getcmdb_accountList,
        data: new_account_formdata
      }).then(() => {
        NewAccountModalDialog.value!.toggle()
        message.success(`新增账户成功:${new_account_info.name}`)
      })
    }

    function NewAssetConfirm() {
      //console.log('资产新增确认 ', NewAsset_itemDataFormRef.value.generatorParams())
      let new_asset_info = NewAsset_itemDataFormRef.value.generatorParams()
      let new_asset_formdata = new FormData()
      new_asset_formdata.append('name', new_asset_info.name)
      new_asset_formdata.append('manage_ip', new_asset_info.manage_ip)
      new_asset_formdata.append('vendor', new_asset_info.vendor)
      new_asset_formdata.append('model', new_asset_info.model)
      new_asset_formdata.append('sub_asset_type', new_asset_info.sub_asset_type)
      new_asset_formdata.append('serial_num', new_asset_info.serial_num)
      new_asset_formdata.append('system', new_asset_info.system)
      new_asset_formdata.append('cpu_model', new_asset_info.cpu_model)
      new_asset_formdata.append('cpu_number', new_asset_info.cpu_number)
      new_asset_formdata.append('vcpu_number', new_asset_info.vcpu_number)
      new_asset_formdata.append('purpose', new_asset_info.purpose)
      new_asset_formdata.append('idc', new_asset_info.idc)
      new_asset_formdata.append('idc_model', new_asset_info.idc_model)
      new_asset_formdata.append('rack', new_asset_info.rack)
      new_asset_formdata.append('u_location', new_asset_info.u_location)
      new_asset_formdata.append('memo', new_asset_info.memo)
      new_asset_formdata.append('status', new_asset_info.status)
      new_asset_formdata.append(
        'hosted_on',
        new_asset_info['hosted_on'] ? new_asset_info['hosted_on'] : ''
      )
      new_asset_formdata.append('manager_name', new_asset_info.manager_name)
      new_asset_formdata.append(
        'manager_account',
        new_asset_info.manager_account
      )
      new_asset_formdata.append('manager_tel', new_asset_info.manager_tel)
      post({
        url: getServerDeviceList,
        data: new_asset_formdata
      }).then((res) => {
        if (res.code === 201) {
          message.success('新增服务器资产成功')
          NewAssetModalDialog.value?.toggle()
        }
      })
    }

    function second_onConfirm() {
      //console.log(second_password.value)
      if (second_password.value === 'netaxe_second') {
        show_password_modalDialog.value!.toggle()
        // 打开真实密码account_list/get_device_account
        get({
          url: get_server_expand,
          data: () => {
            return {
              password: second_password.value,
              id: rowData.value['id']
            }
          }
        }).then((res) => {
          //console.log('account_list', res)
          // account_list.length = 0
          // account_list.push(...res.results)
          account_info.value =
            res.results[0]['account__username'] +
            ' ' +
            res.results[0]['account__password']
        })
        account_modalDialog.value?.toggle()
      } else {
        message.warning('请校验二级管理密码')
      }
      // showModal.value = false
      //
    }

    // function second_onCancel() {
    //   //console.log(second_password.value)
    // }

    function onWebssh(item: { id: any; manage_ip: any }) {
      get({
        url: serverWebSsh,
        data: () => {
          return {
            pk: item.id
          }
        }
      }).then((res) => {
        //console.log(res)
        // const init_cmd = res.data['init_cmd']
        const remote_ip = res.data['remote_ip']
        const routerUrl = router.resolve({
          path: '/server_ssh/',
          query: {
            id: item.id,
            remote_ip: remote_ip,
            manage_ip: item.manage_ip
          }
        })
        //console.log(routerUrl)
        window.open(routerUrl.fullPath, '_blank') //打开新的窗口
      })
    }

    function EditServer(item: any) {
      //console.log('编辑当前行', item)
      // 根据机房查询模块

      nextTick(() => {
        get({
          url: getCmdbIdcModelList,
          data: () => {
            return {
              idc: item.idc,
              limit: 1000
            }
          }
        }).then((res) => {
          //console.log('编辑--机房获取模块', res)
          //  //console.log(conditionItems)
          // let filter_list = []
          if (itemFormOptions[3].optionItems !== undefined) {
            itemFormOptions[3].optionItems.length = 0
            let idc_model_list: { value: any; label: any }[] = []
            res.results.forEach((ele: { [x: string]: any }) => {
              let dict = {
                value: ele['id'],
                label: ele['name']
              }
              idc_model_list.push(dict)
            })
            itemFormOptions[3].optionItems.push(...idc_model_list)
          }
        })

        // 根据模块查询机柜
        get({
          url: getCmdbRackList,
          data: () => {
            return {
              idc_model: item.idc_model,
              limit: 1000
            }
          }
        }).then((res) => {
          //console.log('编辑模块机柜内容', res)
          //  //console.log(conditionItems)
          // let filter_list = []
          if (itemFormOptions[5].optionItems !== undefined) {
            itemFormOptions[5].optionItems.length = 0
            let model_list: { value: any; label: any }[] = []
            res.results.forEach((ele: { [x: string]: any }) => {
              let dict = {
                value: ele['id'],
                label: ele['name']
              }
              model_list.push(dict)
            })
            itemFormOptions[5].optionItems.push(...model_list)
          }
        })
        nextTick(() => {
          modalDialog.value?.toggle()
          itemFormOptions.forEach((it) => {
            const key = it.key
            const propName = item[key]
            it.value.value = propName
          })
        })
      })
    }

    function rowKey(rowData: any) {
      return rowData.id
    }

    function ContainerRowKey(rowData: any) {
      return rowData.id + rowData.on_server_ip + rowData.name
    }

    function import_from_nvwa() {}

    function filter_container_list() {
      //console.log('容器搜索关键字', container_keyword.value)
      if (container_keyword.value) {
        let filter_list: any[] = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = container_list.filter((item) => {
          return item.name.indexOf(container_keyword.value) != -1
        })
        nextTick(() => {
          container_list.length = 0
          container_list.push(...filter_list)
          container_page.value = 1
          container_pageSize.value = 10
          container_pageCount.value = Math.ceil(container_list.length / 10)
        })
      } else {
        get_container_list()
      }
    }

    function new_account() {
      //console.log('打开账户新增对话框')
      NewAccountModalDialog.value?.toggle()
    }

    function handleExpand(rowKeys: any) {
      //console.log('当前行', rowKeys)
      // let current_row_data = table.dataList.filter((item) => {
      //   return item['id'] == rowKeys
      // })[0]
      //console.log('当前行数据', current_row_data)
    }

    onMounted(doRefresh)
    onMounted(doIdc)
    onMounted(doVendor)
    onMounted(doRole)
    onMounted(doCagetory)
    onMounted(get_cmdb_account)
    return {
      connect_account_handleClick,
      ContainerRowKey,
      server_entering,
      import_from_nvwa,
      new_account,
      NewAccountModalDialog,
      itemDataFormRef,
      NewAsset_itemDataFormRef,
      NewAccount_itemDataFormRef,
      searchDataFormRef,
      onDataFormConfirm,
      select_idc,
      get_info_by_vendor,
      second_password,
      rowData,
      show_password_modalDialog,
      account_modalDialog,
      account_info,
      show_account_handleClick,
      second_onConfirm,
      NewAssetConfirm,
      handleExpand,
      NewAccountConfirm,
      tableColumns,
      account_tableColumns,
      EditServer,
      pagination,
      searchForm,
      onResetSearch,
      onSearch,
      ...table,
      filter_container_list,
      itemFormOptions,
      NewAsset_itemFormOptions,
      NewAccount_itemFormOptions,
      rowKey,
      modalDialog,
      NewAssetModalDialog,
      WebsshmodalDialog,
      conditionItems,
      onUpdateTable,
      onUpdateBorder,
      doRefresh,
      container_list,
      container_page,
      container_pageSize,
      container_pageSizes,
      container_pageCount,
      container_tableColumns,
      container_keyword,
      connect_account_modalDialog,
      device_info,
      connect_account_FormOptions,
      ConnectAccountConfirm,
      isInArray,
      connect_account_DataFormRef,
      get_cmdb_account,
      row_item,
      tab_change: (value: string) => {
        // message.info(value)
        if (value === '物理服务器') {
          doRefresh()
        }
        if (value === '容器') {
          get_container_list()
          //console.log('获取容器列表')
        }
      }
    }
  }
})
</script>
<style lang="scss">
.n-form.n-form--inline {
  width: 100%;
  display: inline-flex;
  align-items: flex-start;
  align-content: space-around;
  height: 5px;
}

.n-form-item.n-form-item--left-labelled .n-form-item-label {
  font-weight: bold;
}
</style>
