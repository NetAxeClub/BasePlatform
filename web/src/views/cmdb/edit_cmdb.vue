<template>
  <div class="main-container">
    <n-card title="" style="margin-bottom: 16px">
      <n-tabs type="line" animated>
        <n-tab-pane name="CMDB基本属性维护" tab="CMDB基本属性维护">
          <!--          <div>-->
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>硬件型号维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_vendor_show = true"
                    >新增供应商
                  </n-button>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_devicetype_show = true"
                    >新增设备类型
                  </n-button>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_model_show = true"
                    >新增硬件型号
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="硬件型号搜索"
                    v-model:value="model_keyword"
                    @keyup.enter.native="model_filter_func"
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    model_list.slice(
                      (model_page - 1) * model_pageSize,
                      model_page * model_pageSize
                    )
                  "
                  :columns="model_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="model_page"
                    :page-count="model_pageCount"
                    show-size-picker
                    :page-sizes="model_pageSizes"
                  >
                    <template #prefix="{ itemCount, startIndex }">
                      共 {{ model_count }} 项
                    </template>
                  </n-pagination>
                </div>
              </template>
            </TableBody>
          </div>
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>设备角色维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_role_show = true"
                    >新增设备角色
                  </n-button>

                  <n-input
                    size="tiny"
                    placeholder="设备角色搜索"
                    v-model:value="role_keyword"
                    @keyup.enter.native="role_filter_func"
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    role_list.slice(
                      (role_page - 1) * role_pageSize,
                      role_page * role_pageSize
                    )
                  "
                  :columns="role_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="role_page"
                    :page-count="role_pageCount"
                    show-size-picker
                    :page-sizes="role_pageSizes"
                  >
                    <template #prefix="{ itemCount, startIndex }">
                      共 {{ role_count }} 项
                    </template>
                  </n-pagination>
                  <!--              <n-button  circle class="ml-1" size="tiny" type="primary" @click="refresh">-->
                  <!--                <template #icon>-->
                  <!--                  <n-icon>-->
                  <!--                                        <RefreshIcon />-->
                  <!--                  </n-icon>-->
                  <!--                </template>-->
                  <!--              </n-button>-->
                </div>
              </template>
            </TableBody>
          </div>
          <!--          </div>-->
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>网络区域维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_netzone_show = true"
                    >新增网络区域
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="网络区域搜索"
                    v-model:value="netzone_keyword"
                    @keyup.enter.native="netzone_filter_func"
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    netzone_list.slice(
                      (netzone_page - 1) * netzone_pageSize,
                      netzone_page * netzone_pageSize
                    )
                  "
                  :columns="netzone_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="netzone_page"
                    :page-count="netzone_pageCount"
                    show-size-picker
                    :page-sizes="netzone_pageSizes"
                  >
                    <template #prefix="{ itemCount, startIndex }">
                      共 {{ netzone_count }} 项
                    </template>
                  </n-pagination>
                  <!--              <n-button  circle class="ml-1" size="tiny" type="primary" @click="refresh">-->
                  <!--                <template #icon>-->
                  <!--                  <n-icon>-->
                  <!--                                        <RefreshIcon />-->
                  <!--                  </n-icon>-->
                  <!--                </template>-->
                  <!--              </n-button>-->
                </div>
              </template>
            </TableBody>
          </div>
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>网络属性维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_attribute_show = true"
                    >新增网络属性
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="网络属性搜索"
                    v-model:value="net_attribute_keyword"
                    @keyup.enter.native="net_attributefilter_func"
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    attribute_list.slice(
                      (attribute_page - 1) * attribute_pageSize,
                      attribute_page * attribute_pageSize
                    )
                  "
                  :columns="attribute_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="attribute_page"
                    :page-count="attribute_pageCount"
                    show-size-picker
                    :page-sizes="attribute_pageSizes"
                  >
                    <template #prefix="{ itemCount, startIndex }">
                      共 {{ attribute_count }} 项
                    </template>
                  </n-pagination>
                  <!--              <n-button  circle class="ml-1" size="tiny" type="primary" @click="refresh">-->
                  <!--                <template #icon>-->
                  <!--                  <n-icon>-->
                  <!--                                        <RefreshIcon />-->
                  <!--                  </n-icon>-->
                  <!--                </template>-->
                  <!--              </n-button>-->
                </div>
              </template>
            </TableBody>
          </div>
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>网络架构维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_framework_show = true"
                    >新增网络架构
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="网络架构搜索"
                    v-model:value="net_framework_keyword"
                    @keyup.enter.native="net_frameworkfilter_func"
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    framework_list.slice(
                      (framework_page - 1) * framework_pageSize,
                      framework_page * framework_pageSize
                    )
                  "
                  :columns="framework_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="framework_page"
                    :page-count="framework_pageCount"
                    show-size-picker
                    :page-sizes="framework_pageSizes"
                  >
                    <template #prefix="{ itemCount, startIndex }">
                      共 {{ framework_count }} 项
                    </template>
                  </n-pagination>
                  <!--              <n-button  circle class="ml-1" size="tiny" type="primary" @click="refresh">-->
                  <!--                <template #icon>-->
                  <!--                  <n-icon>-->
                  <!--                                        <RefreshIcon />-->
                  <!--                  </n-icon>-->
                  <!--                </template>-->
                  <!--              </n-button>-->
                </div>
              </template>
            </TableBody>
          </div>
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>网络机柜维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_cmdb_show = true"
                    >新增网络机房
                  </n-button>
                  <n-button
                    size="tiny"
                    type="success"
                    @click="add_network_model_show = true"
                    >新增网络模块
                  </n-button>
                  <n-button
                    size="tiny"
                    type="warning"
                    @click="click_add_netrack()"
                    >新增网络机柜
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="网络机柜搜索"
                    v-model:value="net_rack_keyword"
                    @keyup.enter.native="net_rackfilter_func"
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    rack_list.slice(
                      (rack_page - 1) * rack_pageSize,
                      rack_page * rack_pageSize
                    )
                  "
                  :columns="rack_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="rack_page"
                    :page-count="rack_pageCount"
                    show-size-picker
                    :page-sizes="rack_pageSizes"
                  >
                    <template #prefix="{ itemCount, startIndex }">
                      共 {{ rack_count }} 项
                    </template>
                  </n-pagination>
                  <!--              <n-button  circle class="ml-1" size="tiny" type="primary" @click="refresh">-->
                  <!--                <template #icon>-->
                  <!--                  <n-icon>-->
                  <!--                                        <RefreshIcon />-->
                  <!--                  </n-icon>-->
                  <!--                </template>-->
                  <!--              </n-button>-->
                </div>
              </template>
            </TableBody>
          </div>
        </n-tab-pane>
        <n-tab-pane name="服务器基本属性维护" tab="服务器基本属性维护">
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>服务器供应商维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_server_vendor_show = true"
                    >新增服务器供应商
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="服务器供应商搜索"
                    @keyup.enter.native=""
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    server_vendor_list.slice(
                      (server_vendor_page - 1) * server_vendor_pageSize,
                      server_vendor_page * server_vendor_pageSize
                    )
                  "
                  :columns="server_vendor_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="server_vendor_page"
                    :page-count="server_vendor_pageCount"
                    show-size-picker
                    :page-sizes="server_vendor_pageSizes"
                  />
                  <!--              <n-button  circle class="ml-1" size="tiny" type="primary" @click="refresh">-->
                  <!--                <template #icon>-->
                  <!--                  <n-icon>-->
                  <!--                                        <RefreshIcon />-->
                  <!--                  </n-icon>-->
                  <!--                </template>-->
                  <!--              </n-button>-->
                </div>
              </template>
            </TableBody>
          </div>
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>服务器管理账户维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button size="tiny" type="info" @click=""
                    >新增服务器管理账户
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="服务器账户搜索"
                    @keyup.enter.native=""
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    server_account_list.slice(
                      (server_account_page - 1) * server_account_pageSize,
                      server_account_page * server_account_pageSize
                    )
                  "
                  :columns="server_account_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="server_account_page"
                    :page-count="server_account_pageCount"
                    show-size-picker
                    :page-sizes="server_account_pageSizes"
                  />
                </div>
              </template>
            </TableBody>
          </div>
          <div style="width: 100%; display: inline-block; padding: 10px">
            <h3>服务器型号维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_server_model_show = true"
                    >新增服务器型号
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="服务器型号搜索"
                    @keyup.enter.native=""
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    server_model_list.slice(
                      (server_model_page - 1) * server_model_pageSize,
                      server_model_page * server_model_pageSize
                    )
                  "
                  :columns="server_model_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="server_model_page"
                    :page-count="server_model_pageCount"
                    show-size-picker
                    :page-sizes="server_model_pageSizes"
                  />
                </div>
              </template>
            </TableBody>
          </div>
        </n-tab-pane>
        <n-tab-pane name="账户属性维护" tab="账户属性维护">
          <div style="width: 50%; display: inline-block; padding: 10px">
            <h3>管理账户维护</h3>
            <TableBody>
              <template #header>
                <n-space>
                  <n-button
                    size="tiny"
                    type="info"
                    @click="add_cmdb_account_show = true"
                    >新增设备管理账户
                  </n-button>
                  <n-input
                    size="tiny"
                    placeholder="管理账户搜索"
                    @keyup.enter.native=""
                  />
                </n-space>
              </template>
              <template #default>
                <n-data-table
                  :data="
                    cmdb_account_list.slice(
                      (cmdb_account_page - 1) * cmdb_account_pageSize,
                      cmdb_account_page * cmdb_account_pageSize
                    )
                  "
                  :columns="cmdb_account_tableColumns"
                  :row-key="rowKey"
                />
              </template>
              <template #footer>
                <div class="flex justify-center">
                  <n-pagination
                    v-model:page="cmdb_account_page"
                    :page-count="cmdb_account_pageCount"
                    show-size-picker
                    :page-sizes="cmdb_account_pageSizes"
                  />
                </div>
              </template>
            </TableBody>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-card>
    <n-modal v-model:show="add_vendor_show" preset="dialog" title="新增供应商">
      <div>
        <n-form
          :model="add_vendor_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="供应商">
            <n-input
              v-model:value="add_vendor_form.name"
              placeholder="供应商"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddVendor()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddVendorConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_devicetype_show"
      preset="dialog"
      title="新增设备类型"
    >
      <div>
        <n-form
          :model="add_devicetype_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="设备类型">
            <n-input
              v-model:value="add_devicetype_form.name"
              placeholder="设备类型"
            />
          </n-form-item>
          <n-form-item label="供应商">
            <n-select
              v-model:value="add_devicetype_form.vendor"
              filterable
              placeholder="选择供应商"
              :options="vendor_options"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddDeviceType()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddDeviceTypeConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal v-model:show="add_cmdb_show" preset="dialog" title="新增机房">
      <div>
        <n-form
          :model="add_cmdb_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="机房名称">
            <n-input
              v-model:value="add_cmdb_form.name"
              placeholder="机房名称"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddCmdb()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddCmdbConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal v-model:show="add_rack_show" preset="dialog" title="新增机柜">
      <div>
        <n-form
          :model="add_rack_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="机柜编号">
            <n-input
              v-model:value="add_rack_form.name"
              placeholder="机柜编号"
            />
          </n-form-item>
          <n-form-item label="关联模块">
            <n-select
              v-model:value="add_rack_form.idc_model"
              filterable
              placeholder="选择关联模块"
              :options="idc_model_options"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddRack()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddRackConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_network_model_show"
      preset="dialog"
      title="新增网络模块"
    >
      <div>
        <n-form
          :model="add_network_model_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="模块名称">
            <n-input
              v-model:value="add_network_model_form.name"
              placeholder="模块名称"
            />
          </n-form-item>
          <n-form-item label="关联机房">
            <n-select
              v-model:value="add_network_model_form.idc"
              filterable
              placeholder="选择关联机房"
              :options="idc_options"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button
              size="tiny"
              type="warning"
              @click="CancelAddNetworkModel()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddNetworkModelConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal v-model:show="add_model_show" preset="dialog" title="新增硬件型号">
      <div>
        <n-form
          :model="add_model_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="硬件型号">
            <n-input
              v-model:value="add_model_form.name"
              placeholder="硬件型号"
            />
          </n-form-item>
          <n-form-item label="供应商">
            <n-select
              v-model:value="add_model_form.vendor"
              filterable
              placeholder="选择供应商"
              :options="vendor_options"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelModel()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddModelConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal v-model:show="add_role_show" preset="dialog" title="新增设备角色">
      <div>
        <n-form
          :model="add_role_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="设备角色">
            <n-input
              v-model:value="add_role_form.name"
              placeholder="设备角色"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelRole()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddRoleConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_attribute_show"
      preset="dialog"
      title="新增网络属性"
    >
      <div>
        <n-form
          :model="add_attribute_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="属性名">
            <n-input
              v-model:value="add_attribute_form.name"
              placeholder="属性名"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddAttribute()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddAttributeConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_server_vendor_show"
      preset="dialog"
      title="新增服务器供应商"
    >
      <div>
        <n-form
          :model="add_server_vendor_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="服务器供应商名">
            <n-input
              v-model:value="add_server_vendor_form.name"
              placeholder="服务器供应商名"
            />
          </n-form-item>
          <n-form-item label="别名">
            <n-input
              v-model:value="add_server_vendor_form.alias"
              placeholder="别名"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button
              size="tiny"
              type="warning"
              @click="CancelAddServerVendor()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddServerVendorConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_framework_show"
      preset="dialog"
      title="新增网络架构"
    >
      <div>
        <n-form
          :model="add_framework_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="架构名">
            <n-input
              v-model:value="add_framework_form.name"
              placeholder="架构名"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddFramework()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddFrameworkConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_netzone_show"
      preset="dialog"
      title="新增网络区域"
    >
      <div>
        <n-form
          :model="add_netzone_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="区域名">
            <n-input
              v-model:value="add_netzone_form.name"
              placeholder="区域名"
            />
          </n-form-item>
          <n-form-item label="关联机房">
            <n-select
              v-model:value="add_netzone_form.idc"
              filterable
              placeholder="选择关联机房"
              :options="idc_options"
            />
          </n-form-item>
          <n-form-item label="备注">
            <n-input v-model:value="add_netzone_form.memo" placeholder="备注" />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddNetzone()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddNetzoneConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_server_model_show"
      preset="dialog"
      title="新增服务器型号"
    >
      <div>
        <n-form
          :model="add_server_model_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="硬件型号">
            <n-input
              v-model:value="add_server_model_form.name"
              placeholder="硬件型号"
            />
          </n-form-item>
          <n-form-item label="型号别名">
            <n-input
              v-model:value="add_server_model_form.alias"
              placeholder="型号别名"
            />
          </n-form-item>
          <n-form-item label="供应商">
            <n-select
              v-model:value="add_server_model_form.vendor"
              filterable
              placeholder="选择供应商"
              :options="server_vendor_options"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddServerModel()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddServerModelConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_cmdb_account_show"
      preset="dialog"
      title="新增设备管理账户"
    >
      <div>
        <n-form
          :model="add_cmdb_account_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="账户标识名">
            <n-input
              v-model:value="add_cmdb_account_form.name"
              placeholder="账户标识名"
            />
          </n-form-item>
          <n-form-item label="登录用户名">
            <n-input
              v-model:value="add_cmdb_account_form.username"
              placeholder="登录用户名"
            />
          </n-form-item>
          <n-form-item label="登录密码">
            <n-input
              v-model:value="add_cmdb_account_form.password"
              placeholder="登录密码"
            />
          </n-form-item>
          <n-form-item label="协议">
            <n-input
              v-model:value="add_cmdb_account_form.protocol"
              placeholder="协议:ssh/netconf/telnet"
            />
          </n-form-item>
          <n-form-item label="端口">
            <n-input
              v-model:value="add_cmdb_account_form.port"
              placeholder="协议端口"
            />
          </n-form-item>
          <n-form-item label="特权密码">
            <n-input
              v-model:value="add_cmdb_account_form.enable_password"
              placeholder="特权密码"
            />
          </n-form-item>

          <n-form-item label="账户角色">
            <n-select
              v-model:value="add_cmdb_account_form.user_role"
              filterable
              placeholder="选择账户角色"
              :options="user_role_options"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddCmdbAccount()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddCmdbAccountConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
    <n-modal
      v-model:show="add_connect_type_show"
      preset="dialog"
      title="新增协议端口"
    >
      <div>
        <n-form
          :model="add_connect_type_form"
          label-placement="left"
          label-width="auto"
        >
          <n-form-item label="协议名">
            <n-input
              v-model:value="add_connect_type_form.name"
              placeholder="协议名"
            />
          </n-form-item>
          <n-form-item label="端口号">
            <n-input
              v-model:value="add_connect_type_form.port"
              placeholder="端口号"
            />
          </n-form-item>
        </n-form>
      </div>
      <template #action>
        <div>
          <n-space>
            <n-button size="tiny" type="warning" @click="CancelAddConnectType()"
              >取消
            </n-button>
            <n-button size="tiny" type="info" @click="AddConnectTypeConfirm()"
              >确认
            </n-button>
          </n-space>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script lang="ts">
import {
  // getFirewallList,
  // getAddress_setList,
  // getasset_account_protocolList,
  getCmdbServerModelList,
  get_cmdb_rack,
  getCmdbIdcModelList,
  getCmdbIdcList,
  getCategoryList,
  getCmdbModelList,
  getCmdbRoleList,
  getCmdbNetzoneList,
  getAttributeList,
  getFrameworkList,
  getCmdbRackList,
  getServerVendorList,
  server_account_url,
  // getCmdbServerModelList,
  getcmdb_accountList,
  // getcmdb_protocol_portList,
  getVendorList
} from '@/api/url'
import usePost from '@/hooks/usePost'
import useGet from '@/hooks/useGet'
import {
  // TableActionModel,
  // useTable,
  // useRenderAction,
  useTableColumn
  // usePagination
} from '@/hooks/table'
import {
  DataTableColumn,
  // NInput,
  // NSelect,
  SelectOption,
  useDialog,
  useMessage,
  // NDropdown,
  NButton,
  NPopconfirm
} from 'naive-ui'
import {
  defineComponent,
  // computed,
  // watch,
  h,
  nextTick,
  onMounted,
  reactive,
  ref,
  shallowReactive
} from 'vue'
// import { DataFormType, FormItem, ModalDialogType } from '@/types/components'
import useDelete from '@/hooks/useDelete'
// import usePatch from '@/hooks/usePatch'

export default defineComponent({
  name: 'EditCmdb',
  setup() {
    const dialog_test = ref('')
    const dialog = useDialog()
    const message = useMessage()
    const model_keyword = ref('')
    const role_keyword = ref('')
    const netzone_keyword = ref('')
    const net_attribute_keyword = ref('')
    const net_framework_keyword = ref('')
    const net_rack_keyword = ref('')
    const add_vendor_show = ref(false)
    const add_connect_type_show = ref(false)
    const add_connect_type_form = ref({
      name: '',
      port: ''
    })
    const add_vendor_form = ref({
      name: ''
    })
    const add_model_show = ref(false)
    const add_model_form = ref({
      name: '',
      vendor: ref<number>(2)
    })
    const add_role_show = ref(false)
    const add_framework_show = ref(false)
    const add_attribute_show = ref(false)
    const add_rack_show = ref(false)
    const add_network_model_show = ref(false)
    const add_cmdb_show = ref(false)
    const add_netzone_show = ref(false)
    const add_server_vendor_show = ref(false)
    const add_server_model_show = ref(false)
    const add_cmdb_account_show = ref(false)
    const add_cmdb_account_form = ref({
      name: '',
      username: '',
      password: '',
      enable_password: '',
      user_role: ref<number>(3),
      port: ref(22),
      protocol: ref('')
    })
    const add_server_vendor_form = ref({
      name: '',
      alias: '',
      vendor: ref<number>(0)
    })
    const add_server_model_form = ref({
      name: '',
      alias: '',
      vendor: ref<number>(0)
    })
    const add_role_form = ref({
      name: ''
    })
    const add_framework_form = ref({
      name: ''
    })
    const add_attribute_form = ref({
      name: ''
    })
    const add_netzone_form = ref({
      name: '',
      idc: ref<number>(1),
      memo: ''
    })
    const add_rack_form = ref({
      name: '',
      idc_model: ref<number>(1)
    })
    const add_network_model_form = ref({
      name: '',
      idc: ref<number>(1)
    })
    const add_cmdb_form = ref({
      name: ''
    })
    const add_devicetype_show = ref(false)
    const add_devicetype_form = ref({
      name: '',
      vendor: ref<number>(2)
    })
    const get = useGet()
    const post = usePost()
    const delete_func = useDelete()
    const model_list = shallowReactive([] as Array<SelectOption>)
    const vendor_options = shallowReactive([] as Array<SelectOption>)
    const idc_options = shallowReactive([] as Array<SelectOption>)
    const idc_model_options = shallowReactive([] as Array<SelectOption>)
    const model_options = shallowReactive([] as Array<SelectOption>)
    const role_options = shallowReactive([] as Array<SelectOption>)
    const server_vendor_options = shallowReactive([] as Array<SelectOption>)
    const user_role_options = shallowReactive([
      { value: 3, label: '超级管理员' },
      { value: 2, label: '管理员' },
      { value: 1, label: '普通用户' },
      { value: 0, label: '查看' }
    ] as Array<SelectOption>)
    const model_pageSizes = [
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
    const model_page = ref<number>(1)
    const model_pageSize = ref<number>(10)
    const model_pageCount = ref<number>(1)
    const role_list = shallowReactive([] as Array<SelectOption>)
    const role_pageSizes = [
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
    const role_page = ref<number>(1)
    const role_pageSize = ref<number>(10)
    const role_pageCount = ref<number>(1)
    const netzone_list = shallowReactive([] as Array<SelectOption>)
    const netzone_pageSizes = [
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
    const netzone_page = ref<number>(1)
    const netzone_pageSize = ref<number>(10)
    const netzone_pageCount = ref<number>(1)

    const attribute_list = shallowReactive([] as Array<SelectOption>)
    const attribute_pageSizes = [
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
    const attribute_page = ref<number>(1)
    const attribute_pageSize = ref<number>(10)
    const attribute_pageCount = ref<number>(1)

    const framework_list = shallowReactive([] as Array<SelectOption>)
    const framework_pageSizes = [
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
    const framework_page = ref<number>(1)
    const framework_pageSize = ref<number>(10)
    const framework_pageCount = ref<number>(1)

    const rack_list = shallowReactive([] as Array<SelectOption>)
    const rack_pageSizes = [
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
    const rack_page = ref<number>(1)
    const rack_pageSize = ref<number>(10)
    const rack_pageCount = ref<number>(1)
    const model_count = ref<number>(0)
    const role_count = ref<number>(0)
    const netzone_count = ref<number>(0)
    const attribute_count = ref<number>(0)
    const framework_count = ref<number>(0)
    const rack_count = ref<number>(0)

    const server_vendor_list = shallowReactive([] as Array<SelectOption>)
    const server_vendor_pageSizes = [
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
    const server_vendor_page = ref<number>(1)
    const server_vendor_pageSize = ref<number>(10)
    const server_vendor_pageCount = ref<number>(1)

    const server_account_list = shallowReactive([] as Array<SelectOption>)
    const server_account_pageSizes = [
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
    const server_account_page = ref<number>(1)
    const server_account_pageSize = ref<number>(10)
    const server_account_pageCount = ref<number>(1)

    const server_model_list = shallowReactive([] as Array<SelectOption>)
    const server_model_pageSizes = [
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
    const server_model_page = ref<number>(1)
    const server_model_pageSize = ref<number>(10)
    const server_model_pageCount = ref<number>(1)

    const cmdb_account_list = shallowReactive([] as Array<SelectOption>)
    const cmdb_account_pageSizes = [
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
    const cmdb_account_page = ref<number>(1)
    const cmdb_account_pageSize = ref<number>(10)
    const cmdb_account_pageCount = ref<number>(1)

    const cmdb_protocol_list = shallowReactive([] as Array<SelectOption>)
    const cmdb_protocol_pageSizes = [
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
    const cmdb_protocol_page = ref<number>(1)
    const cmdb_protocol_pageSize = ref<number>(10)
    const cmdb_protocol_pageCount = ref<number>(1)
    const server_vendor_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '供应商',
            key: 'name'
          },
          {
            title: '别名',
            key: 'alias'
          },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_server_vendor(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const server_account_tableColumns = reactive(
      useTableColumn(
        [
          // {
          //   title: '服务器',
          //   key: 'server'
          // },
          {
            title: '服务器名称',
            key: 'server_name'
          },
          // {
          //   title: '账户',
          //   key: 'account'
          // },
          {
            title: '账户名称',
            key: 'account_name'
          },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_server_account(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const server_model_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '硬件型号',
            key: 'name'
          },
          {
            title: '型号别名',
            key: 'alias'
          },
          {
            title: '供应商',
            key: 'vendor_name'
          },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_server_model(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const cmdb_account_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '管理账户',
            key: 'name'
          },
          {
            title: '登录用户名',
            key: 'username'
          },
          {
            title: '协议',
            key: 'protocol'
          },
          {
            title: '端口号',
            key: 'port'
          },
          // {
          //     title: '操作',
          //     key: 'action',
          //     render: (rowData) => {
          //         return h(NButton, {type: 'info', size: 'tiny'}, () => h('span', {}, '编辑'))
          //     },
          // },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_cmdb_account(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const cmdb_protocol_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '协议',
            key: 'protocol'
          },
          {
            title: '端口',
            key: 'port'
          },
          // {
          //     title: '操作',
          //     key: 'action',
          //     render: (rowData) => {
          //         return h(NButton, {type: 'info', size: 'tiny'}, () => h('span', {}, '编辑'))
          //     },
          // },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_cmdb_protol(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const model_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '供应商',
            key: 'vendor_name'
          },
          {
            title: '型号',
            key: 'name'
          },

          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_model(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确定要删除该条硬件型号记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const role_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '角色名',
            key: 'name'
          },
          // {
          //     title: '操作',
          //     key: 'action',
          //     render: (rowData) => {
          //         return h(NButton, {type: 'info', size: 'tiny'}, () => h('span', {}, '编辑'))
          //
          //     },
          // },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_role(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确定要删除这条设备角色记录吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const netzone_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '区域名',
            key: 'name'
          },
          {
            title: '所属机房',
            key: 'idc_name'
          },
          {
            title: '备注',
            key: 'memo'
          },

          // {
          //     title: '操作',
          //     key: 'action',
          //     render: (rowData) => {
          //         return h(NButton, {type: 'info', size: 'tiny'}, () => h('span', {}, '编辑'))
          //
          //     },
          // },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_netzone(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该条网络区域吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const attribute_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '属性名',
            key: 'name'
          },
          // {
          //     title: '操作',
          //     key: 'action',
          //     render: (rowData) => {
          //         return h(NButton, {type: 'info', size: 'tiny'}, () => h('span', {}, '编辑'))
          //
          //     },
          // },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_attribute(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该网络属性吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const framework_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '架构名',
            key: 'name'
          },

          // {
          //     title: '操作',
          //     key: 'action',
          //     render: (rowData) => {
          //         return h(NButton, {type: 'info', size: 'tiny'}, () => h('span', {}, '编辑'))
          //
          //     },
          // },
          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_framework(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该网络架构吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )
    const rack_tableColumns = reactive(
      useTableColumn(
        [
          {
            title: '模块名称',
            key: 'idc_model_name'
          },
          {
            title: '机房名称',
            key: 'idc_name'
          },
          {
            title: '机柜名称',
            key: 'name'
          },
          // {

          {
            title: '删除',
            key: 'delete',
            render: (rowData) => {
              return h(
                NPopconfirm,
                {
                  onPositiveClick: () => delete_rack(rowData),
                  negativeText: '取消',
                  positiveText: '确认'
                },
                {
                  trigger: () =>
                    h(NButton, { type: 'error', size: 'tiny' }, () =>
                      h('span', {}, '删除')
                    ),
                  default: () => h('span', {}, '确认删除该网络机柜吗?')
                }
              )
            }
          }
        ],
        {
          align: 'center'
        } as DataTableColumn
      )
    )

    function get_idc_model() {
      get({
        url: getCmdbModelList,
        data: () => {
          return {
            limit: 1000,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          model_list.length = 0
          model_list.push(...res.results)

          model_page.value = 1
          model_pageSize.value = 10
          model_pageCount.value = Math.ceil(res.count / 10)
          model_count.value = res.count
        }
      })
    }

    function get_role() {
      get({
        url: getCmdbRoleList,
        data: () => {
          return {
            limit: 1000,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          role_list.length = 0
          role_list.push(...res.results)

          role_page.value = 1
          role_pageSize.value = 10
          role_pageCount.value = Math.ceil(res.count / 10)
          role_count.value = res.count
        }
      })
    }

    function get_netzone() {
      get({
        url: getCmdbNetzoneList,
        data: () => {
          return {
            limit: 1000,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          netzone_list.length = 0
          netzone_list.push(...res.results)

          netzone_page.value = 1
          netzone_pageSize.value = 10
          netzone_pageCount.value = Math.ceil(res.count / 10)
          netzone_count.value = res.count
        }
      })
    }

    function get_attribute() {
      get({
        url: getAttributeList,
        data: () => {
          return {
            limit: 1000,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          attribute_list.length = 0
          attribute_list.push(...res.results)

          attribute_page.value = 1
          attribute_pageSize.value = 10
          attribute_pageCount.value = Math.ceil(res.count / 10)
          attribute_count.value = res.count
        }
      })
    }

    function get_framework() {
      get({
        url: getFrameworkList,
        data: () => {
          return {
            limit: 1000,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          framework_list.length = 0
          framework_list.push(...res.results)

          framework_page.value = 1
          framework_pageSize.value = 10
          framework_pageCount.value = Math.ceil(res.count / 10)
          framework_count.value = res.count
        }
      })
    }

    function get_rack() {
      get({
        url: getCmdbRackList,
        data: () => {
          return {
            limit: 10000,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          rack_list.length = 0
          rack_list.push(...res.results)

          rack_page.value = 1
          rack_pageSize.value = 10
          rack_pageCount.value = Math.ceil(res.count / 10)
          rack_count.value = res.count
        }
      })
    }

    function get_server_vendor() {
      get({
        url: getServerVendorList,
        data: () => {
          return {
            limit: 9999,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          server_vendor_list.length = 0
          server_vendor_list.push(...res.results)

          server_vendor_page.value = 1
          server_vendor_pageSize.value = 10
          server_vendor_pageCount.value = Math.ceil(res.count / 10)
          const server_vendor_array: { value: any; label: string }[] = []
          res.results.forEach((item) => {
            const dict = {
              value: item.id,
              label: item.name + '-' + item.alias
            }
            server_vendor_array.push(dict)
          })
          server_vendor_options.push(...server_vendor_array)
        }
      })
    }

    function get_server_account() {
      get({
        url: server_account_url,
        data: () => {
          return {
            limit: 9999,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          server_account_list.length = 0
          server_account_list.push(...res.results)

          server_account_page.value = 1
          server_account_pageSize.value = 10
          server_account_pageCount.value = Math.ceil(res.count / 10)
        }
      })
    }

    function get_server_model() {
      get({
        url: getCmdbServerModelList,
        data: () => {
          return {
            limit: 9999,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          server_model_list.length = 0
          server_model_list.push(...res.results)

          server_model_page.value = 1
          server_model_pageSize.value = 10
          server_model_pageCount.value = Math.ceil(res.count / 10)
        }
      })
    }

    function get_cmdb_account() {
      get({
        url: getcmdb_accountList,
        data: () => {
          return {
            limit: 9999,
            _: Date.now()
          }
        }
      }).then((res) => {
        if (res) {
          cmdb_account_list.length = 0
          cmdb_account_list.push(...res.results)

          cmdb_account_page.value = 1
          cmdb_account_pageSize.value = 10
          cmdb_account_pageCount.value = Math.ceil(res.count / 10)
        }
      })
    }

    // function get_cmdb_protocol() {
    //   get({
    //     url: getcmdb_protocol_portList,
    //     data: () => {
    //       return {
    //         limit: 9999,
    //         _: Date.now()
    //       }
    //     }
    //   }).then((res) => {
    //     if (res) {
    //       cmdb_protocol_list.length = 0
    //       cmdb_protocol_list.push(...res.results)

    //       cmdb_protocol_page.value = 1
    //       cmdb_protocol_pageSize.value = 10
    //       cmdb_protocol_pageCount.value = Math.ceil(res.count / 10)
    //     }
    //   })
    // }

    function rowKey(rowData: any) {
      return rowData.id
    }

    function model_filter_func() {
      //console.log('硬件型号关键字', model_keyword.value)
      if (model_keyword.value) {
        let filter_list = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = model_list.filter((item) => {
          return (
            (item.name + item.vendor_name).indexOf(model_keyword.value) != -1
          )
        })
        nextTick(() => {
          model_list.length = 0
          model_list.push(...filter_list)
          model_page.value = 1
          model_pageSize.value = 10
          model_pageCount.value = Math.ceil(model_list.length / 10)
        })
      } else {
        get_idc_model()
      }
    }

    function role_filter_func() {
      //console.log('角色关键字', role_keyword.value)
      if (role_keyword.value) {
        let filter_list = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = role_list.filter((item) => {
          return item.name.indexOf(role_keyword.value) != -1
        })
        nextTick(() => {
          role_list.length = 0
          role_list.push(...filter_list)
          role_page.value = 1
          role_pageSize.value = 10
          role_pageCount.value = Math.ceil(role_list.length / 10)
        })
      } else {
        get_role()
      }
    }

    function netzone_filter_func() {
      //console.log('区域关键字', netzone_keyword.value)
      if (netzone_keyword.value) {
        let filter_list = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = netzone_list.filter((item) => {
          return item.name.indexOf(netzone_keyword.value) != -1
        })
        nextTick(() => {
          netzone_list.length = 0
          netzone_list.push(...filter_list)
          netzone_page.value = 1
          netzone_pageSize.value = 10
          netzone_pageCount.value = Math.ceil(netzone_list.length / 10)
        })
      } else {
        get_netzone()
      }
    }

    function net_attributefilter_func() {
      //console.log('属性关键字', net_attribute_keyword.value)
      if (net_attribute_keyword.value) {
        let filter_list = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = attribute_list.filter((item) => {
          return item.name.indexOf(net_attribute_keyword.value) != -1
        })
        nextTick(() => {
          attribute_list.length = 0
          attribute_list.push(...filter_list)
          attribute_page.value = 1
          attribute_pageSize.value = 10
          attribute_pageCount.value = Math.ceil(attribute_list.length / 10)
        })
      } else {
        get_attribute()
      }
    }

    function net_frameworkfilter_func() {
      //console.log('架构关键字', net_framework_keyword.value)
      if (net_framework_keyword.value) {
        let filter_list = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = framework_list.filter((item) => {
          return item.name.indexOf(net_framework_keyword.value) != -1
        })
        nextTick(() => {
          framework_list.length = 0
          framework_list.push(...filter_list)
          framework_page.value = 1
          framework_pageSize.value = 10
          framework_pageCount.value = Math.ceil(framework_list.length / 10)
        })
      } else {
        get_framework()
      }
    }

    function net_rackfilter_func() {
      //console.log('机柜关键字', net_rack_keyword.value)
      if (net_rack_keyword.value) {
        let filter_list = []
        // container_list.filter((item) => {
        //   return item.name.indexOf(container_keyword.value) != -1
        // })
        filter_list = rack_list.filter((item) => {
          return (
            (item.name + item.idc_name + item.idc_model_name).indexOf(
              net_rack_keyword.value
            ) != -1
          )
        })
        nextTick(() => {
          rack_list.length = 0
          rack_list.push(...filter_list)
          rack_page.value = 1
          rack_pageSize.value = 10
          rack_pageCount.value = Math.ceil(rack_list.length / 10)
        })
      } else {
        get_rack()
      }
    }

    function AddVendorConfirm() {
      add_vendor_show.value = false
      //console.log(add_vendor_form.value)
      var new_data = new FormData()
      new_data.append('name', add_vendor_form.value['name'])
      post({
        url: getVendorList,
        data: new_data
      }).then(() => {
        message.success('新增供应商成功')
        get_vendor()
        get_idc_model()
      })
    }

    function CancelAddVendor() {
      add_vendor_show.value = false
      add_vendor_form.value['name'] = ''
    }

    function get_vendor() {
      get({
        url: getVendorList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        nextTick(() => {
          let vendor_list = []
          res.results.forEach((item) => {
            const dict = {
              value: item.id,
              label: item.name
            }
            vendor_list.push(dict)
          })
          vendor_options.push(...vendor_list)
        })
      })
    }

    function CancelAddDeviceType() {
      add_devicetype_form.value['name'] = ''
      add_devicetype_form.value['vendor'] = 2
      add_devicetype_show.value = false
    }

    function CancelModel() {
      add_model_form.value['name'] = ''
      add_model_form.value['vendor'] = 2
      add_model_show.value = false
    }

    function CancelAddNetworkModel() {
      add_network_model_form.value['name'] = ''
      add_network_model_form.value['idc'] = 1
      add_network_model_show.value = false
    }

    function AddDeviceTypeConfirm() {
      //console.log(add_devicetype_form.value)
      const post_data = new FormData()
      post_data.append('name', add_devicetype_form.value.name)
      post({
        url: getCategoryList,
        data: post_data
      }).then(() => {
        message.success('新增设备类型成功')
        get_idc_model()
      })
      // add_devicetype_form.value['name'] = ''
      // add_devicetype_form.value['vendor'] = 2
      add_devicetype_show.value = false
    }

    function AddModelConfirm() {
      //console.log(add_model_form.value)
      const post_data = new FormData()
      post_data.append('name', add_model_form.value['name'])
      post_data.append('vendor', add_model_form.value.vendor)
      post({
        url: getCmdbModelList,
        data: post_data
      }).then(() => {
        message.success('新增硬件型号成功')
        get_idc_model()
      })
      add_model_show.value = false
    }

    function AddRoleConfirm() {
      //console.log(add_role_form.value['name'])
      const role_data = new FormData()
      role_data.append('name', add_role_form.value['name'])
      post({
        url: getCmdbRoleList,
        data: role_data
      }).then(() => {
        add_role_show.value = false
        message.success('新增设备角色成功')
        get_role()
      })
    }

    function AddNetzoneConfirm() {
      //console.log(add_netzone_form.value)
      const netzone_data = new FormData()
      netzone_data.append('name', add_netzone_form.value.name)
      netzone_data.append('memo', add_netzone_form.value.memo)
      netzone_data.append('idc', add_netzone_form.value['idc'].toString())
      post({
        url: getCmdbNetzoneList,
        data: netzone_data
      }).then(() => {
        message.success('新增网络区域成功')
        add_netzone_form.value['name'] = ''
        add_netzone_form.value['memo'] = ''
        add_netzone_form.value['idc'] = 1
      })
      add_netzone_show.value = false
    }

    function AddAttributeConfirm() {
      //console.log(add_attribute_form.value)
      const attribute_data = new FormData()
      attribute_data.append('name', add_attribute_form.value.name)
      post({
        url: getAttributeList,
        data: attribute_data
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
      }).then(() => {
        message.success('新增网络属性成功')
        add_attribute_show.value = false
        get_attribute()
      })
    }

    function AddFrameworkConfirm() {
      //console.log(add_framework_form.value)
      const framework_data = new FormData()
      framework_data.append('name', add_framework_form.value.name)
      post({
        url: getFrameworkList,
        data: framework_data
      }).then(() => {
        message.success('新增网络架构成功')
        add_framework_show.value = false
        get_framework()
      })
    }

    function AddNetworkModelConfirm() {
      //console.log(add_rack_form.value)
      const network_model_data = new FormData()
      network_model_data.append('name', add_network_model_form.value.name)
      network_model_data.append(
        'idc',
        add_network_model_form.value['idc'].toString()
      )
      post({
        url: getCmdbIdcModelList,
        data: network_model_data
      }).then(() => {
        message.success('新增网络模块成功')
        add_network_model_show.value = false
        // get_rack()
      })
    }

    function AddRackConfirm() {
      //console.log(add_rack_form.value)
      const rack_data = new FormData()
      rack_data.append('name', add_rack_form.value.name)
      rack_data.append('idc_model', add_rack_form.value['idc_model'].toString())
      post({
        url: get_cmdb_rack,
        data: rack_data
      }).then(() => {
        message.success('新增网络机柜成功')
        add_rack_show.value = false
        get_rack()
      })
    }

    function AddCmdbConfirm() {
      //console.log(add_rack_form.value)
      const rack_data = new FormData()
      rack_data.append('name', add_cmdb_form.value.name)

      post({
        url: getCmdbIdcList,
        data: rack_data
      }).then(() => {
        message.success('新增网络机房成功')
        add_cmdb_show.value = false
        get_idc()
        get_cmdb_idc_model()
      })
    }

    function AddServerVendorConfirm() {
      //console.log(add_server_vendor_form.value)
      const post_data = new FormData()
      post_data.append('name', add_server_vendor_form.value['name'])
      post_data.append('alias', add_server_vendor_form.value['alias'])
      post({
        url: getServerVendorList,
        data: post_data
      }).then(() => {
        add_server_vendor_form.value['name'] = ''
        add_server_vendor_form.value['alias'] = ''
        message.success('新增服务器供应商成功')
        add_server_vendor_show.value = false
        get_server_vendor()
      })
    }

    function AddServerModelConfirm() {
      //console.log(add_server_model_form.value)
      const post_data = new FormData()
      post_data.append('name', add_server_model_form.value['name'])
      post_data.append('alias', add_server_model_form.value['alias'])
      post_data.append('vendor', add_server_model_form.value['vendor'])
      post({
        url: getCmdbServerModelList,
        data: post_data
      }).then(() => {
        message.success('新增服务器型号成功')
        add_server_model_show.value = false
        get_server_model()
      })
    }

    function AddCmdbAccountConfirm() {
      //console.log(add_cmdb_account_form.value)
      const post_data = new FormData()
      post_data.append('name', add_cmdb_account_form.value['name'])
      post_data.append('username', add_cmdb_account_form.value['username'])
      post_data.append('password', add_cmdb_account_form.value['password'])
      post_data.append(
        'enable_password',
        add_cmdb_account_form.value['enable_password']
      )
      post_data.append('protocol', add_cmdb_account_form.value['protocol'])
      post_data.append('port', add_cmdb_account_form.value['port'].toString())
      post_data.append(
        'user_role',
        add_cmdb_account_form.value['user_role'].toString()
      )
      post({
        url: getcmdb_accountList,
        data: post_data
      }).then(() => {
        message.success('新增管理账户成功')
        add_cmdb_account_show.value = false
        add_cmdb_account_form.value['name'] = ''
        add_cmdb_account_form.value['username'] = ''
        add_cmdb_account_form.value['password'] = ''
        add_cmdb_account_form.value['enable_password'] = ''
        add_cmdb_account_form.value['user_role'] = 3
        get_cmdb_account()
      })
    }

    function AddConnectTypeConfirm() {
      //console.log(add_connect_type_form.value)
      const post_data = new FormData()
      post_data.append('name', add_connect_type_form.value['name'])
      post_data.append('port', add_connect_type_form.value['port'])
      post({
        url: getcmdb_accountList,
        data: post_data
      }).then(() => {
        message.success('新增协议端口成功')
        // get_cmdb_protocol()
        add_connect_type_show.value = false
        add_connect_type_form.value['name'] = ''
        add_connect_type_form.value['port'] = ''
      })
    }

    function CancelAddCmdbAccount() {
      add_cmdb_account_show.value = false
      add_cmdb_account_form.value['name'] = ''
      add_cmdb_account_form.value['username'] = ''
      add_cmdb_account_form.value['password'] = ''
      add_cmdb_account_form.value['enable_password'] = ''
      add_cmdb_account_form.value['user_role'] = 3
    }

    function CancelAddConnectType() {
      add_connect_type_show.value = false
      add_connect_type_form.value['name'] = ''
      add_connect_type_form.value['port'] = ''
    }

    function CancelAddServerVendor() {
      add_server_vendor_form.value['name'] = ''
      add_server_vendor_form.value['alias'] = ''
      add_server_vendor_show.value = false
    }

    function CancelAddServerModel() {
      add_server_model_form.value['name'] = ''
      add_server_model_form.value['alias'] = ''
      add_server_model_form.value['vendor'] = 0
      add_server_model_show.value = false
    }

    function CancelRole() {
      add_role_show.value = false
      add_role_form.value['name'] = ''
    }

    function CancelAddRack() {
      add_rack_show.value = false
      add_rack_form.value['name'] = ''
      add_rack_form.value['idc_model'] = 0
    }

    function CancelAddCmdb() {
      add_cmdb_show.value = false
      add_cmdb_form.value['name'] = ''
    }

    function CancelAddNetzone() {
      add_netzone_show.value = false
      add_netzone_form.value['name'] = ''
      add_netzone_form.value['memo'] = ''
      add_netzone_form.value['idc'] = 1
    }

    function CancelAddFramework() {
      add_framework_show.value = false
      add_framework_form.value['name'] = ''
    }

    function CancelAddAttribute() {
      add_attribute_show.value = false
      add_attribute_form.value['name'] = ''
    }

    function delete_model(item: any) {
      delete_func({
        url: getCmdbModelList + item.id + '/'
      }).then(() => {
        message.success('删除硬件型号成功')
        get_idc_model()
      })
    }
    function delete_server_account(item) {
      delete_func({
        url: server_account_url + item.id + '/'
      }).then(() => {
        message.success('删除服务器管理账户成功')
        get_server_account()
      })
    }
    function delete_role(item) {
      delete_func({
        url: getCmdbRoleList + item.id + '/'
      }).then(() => {
        message.success('删除设备角色成功')
        get_role()
      })
    }

    function delete_netzone(item) {
      delete_func({
        url: getCmdbNetzoneList + item.id + '/'
      }).then(() => {
        message.success('删除网络区域成功')
        get_netzone()
      })
    }

    function delete_attribute(item) {
      delete_func({
        url: getAttributeList + '/' + item.id + '/'
      }).then(() => {
        message.success('删除网络属性成功-正在重新查询网络属性')
        get_attribute()
      })
    }

    function delete_framework(item) {
      delete_func({
        url: getFrameworkList + '/' + item.id + '/'
      }).then(() => {
        message.success('删除网络架构成功-正在重新查询网络架构')
        get_framework()
      })
    }

    function delete_rack(item) {
      delete_func({
        url: get_cmdb_rack + '/' + item.id + '/'
      }).then(() => {
        message.success('删除网络机柜成功-正在重新查询机柜')
        get_rack()
      })
    }

    function delete_server_vendor(item) {
      delete_func({
        url: getServerVendorList + '/' + item.id + '/'
      }).then(() => {
        message.success('删除服务器供应商成功')
        get_server_vendor()
      })
    }

    function delete_server_model(item) {
      delete_func({
        url: getCmdbServerModelList + '/' + item.id + '/'
      }).then(() => {
        message.success('删除成功')
        get_server_model()
      })
    }

    function delete_cmdb_account(item) {
      delete_func({
        url: getcmdb_accountList + '/' + item.id + '/'
      }).then(() => {
        message.success('删除成功')
        get_cmdb_account()
      })
    }

    function get_idc() {
      get({
        url: getCmdbIdcList,
        data: () => {
          return {
            limit: 1000
          }
        }
      }).then((res) => {
        //  //console.log(res.results)
        const idc_list: { value: any; label: any }[] = []
        idc_options.length = 0
        res.results.forEach((item: { id: any; name: any }) => {
          const dict = {
            value: item.id,
            label: item.name
          }
          idc_list.push(dict)
        })
        idc_options.push(...idc_list)
      })
    }

    function get_cmdb_idc_model() {
      get({
        url: getCmdbIdcModelList,
        data: () => {
          return {
            limit: 99999,
            _: Date.now()
          }
        }
      }).then((res) => {
        const idc_model_list = []
        res.results.forEach((item) => {
          const dict = {
            value: item.id,
            label: item.name
          }
          idc_model_list.push(dict)
        })
        idc_model_options.push(...idc_model_list)
      })
    }

    function edit_hardware_model(item) {
      console.log('编辑硬件型号', item)
      post({
        url: getCmdbModelList + '/' + item.id + '/'
      })
    }
    function click_add_netrack() {
      get_idc()
      add_rack_show.value = true
    }

    onMounted(get_idc_model)
    onMounted(get_cmdb_idc_model)
    onMounted(get_vendor)
    onMounted(get_role)
    onMounted(get_idc)
    onMounted(get_netzone)
    onMounted(get_attribute)
    onMounted(get_framework)
    onMounted(get_rack)
    onMounted(get_server_vendor)
    onMounted(get_server_account)
    onMounted(get_server_model)
    onMounted(get_cmdb_account)
    // onMounted(get_cmdb_protocol)
    return {
      model_count,
      role_count,
      netzone_count,
      attribute_count,
      framework_count,
      rack_count,
      get_vendor,
      get_idc,
      get_cmdb_idc_model,
      AddVendorConfirm,
      CancelAddVendor,

      AddDeviceTypeConfirm,
      CancelAddDeviceType,

      AddModelConfirm,
      AddNetworkModelConfirm,
      CancelAddNetworkModel,
      CancelModel,

      AddRoleConfirm,
      CancelRole,

      AddNetzoneConfirm,
      CancelAddNetzone,

      AddAttributeConfirm,
      CancelAddAttribute,

      AddFrameworkConfirm,
      CancelAddFramework,

      AddRackConfirm,
      AddCmdbConfirm,
      CancelAddRack,
      CancelAddCmdb,

      AddServerVendorConfirm,
      CancelAddServerVendor,

      AddServerModelConfirm,
      CancelAddServerModel,

      AddCmdbAccountConfirm,
      CancelAddCmdbAccount,

      AddConnectTypeConfirm,
      CancelAddConnectType,

      add_vendor_show,
      add_vendor_form,

      add_connect_type_show,
      add_connect_type_form,

      add_devicetype_show,
      add_devicetype_form,
      vendor_options,
      idc_options,
      idc_model_options,
      server_vendor_options,
      user_role_options,

      add_model_show,
      add_model_form,
      model_options,

      add_role_show,
      add_role_form,

      add_cmdb_account_show,
      add_cmdb_account_form,

      add_framework_show,
      add_framework_form,

      add_attribute_show,
      add_attribute_form,

      add_rack_show,
      add_network_model_show,
      add_cmdb_show,
      add_rack_form,
      add_network_model_form,
      add_cmdb_form,

      add_server_vendor_show,
      add_server_vendor_form,

      add_server_model_show,
      add_server_model_form,

      add_netzone_show,
      add_netzone_form,
      role_options,

      model_keyword,
      role_keyword,
      netzone_keyword,
      net_attribute_keyword,
      net_framework_keyword,
      net_rack_keyword,
      model_filter_func,
      role_filter_func,
      netzone_filter_func,
      net_attributefilter_func,
      net_frameworkfilter_func,
      net_rackfilter_func,
      get_idc_model,
      get_role,
      get_netzone,
      get_attribute,
      get_framework,
      get_rack,
      get_server_vendor,
      get_server_account,
      get_server_model,
      get_cmdb_account,
      // get_cmdb_protocol,
      model_list,
      model_page,
      model_pageSize,
      model_pageSizes,
      model_pageCount,

      delete_model,
      delete_role,
      delete_netzone,
      delete_attribute,
      delete_framework,
      delete_rack,
      dialog_test,
      delete_server_vendor,
      delete_server_model,
      delete_cmdb_account,
      // delete_cmdb_protol,

      edit_hardware_model,

      role_list,
      role_page,
      role_pageSize,
      role_pageSizes,
      role_pageCount,

      netzone_list,
      netzone_page,
      netzone_pageSize,
      netzone_pageSizes,
      netzone_pageCount,

      attribute_list,
      attribute_page,
      attribute_pageSize,
      attribute_pageSizes,
      attribute_pageCount,

      framework_list,
      framework_page,
      framework_pageSize,
      framework_pageSizes,
      framework_pageCount,

      rack_list,
      rack_page,
      rack_pageSize,
      rack_pageSizes,
      rack_pageCount,

      server_vendor_list,
      server_vendor_page,
      server_vendor_pageSize,
      server_vendor_pageSizes,
      server_vendor_pageCount,

      server_account_list,
      server_account_page,
      server_account_pageSize,
      server_account_pageSizes,
      server_account_pageCount,

      server_model_list,
      server_model_page,
      server_model_pageSize,
      server_model_pageSizes,
      server_model_pageCount,

      cmdb_account_list,
      cmdb_account_page,
      cmdb_account_pageSize,
      cmdb_account_pageSizes,
      cmdb_account_pageCount,

      cmdb_protocol_list,
      cmdb_protocol_page,
      cmdb_protocol_pageSize,
      cmdb_protocol_pageSizes,
      cmdb_protocol_pageCount,

      server_vendor_tableColumns,
      server_account_tableColumns,
      server_model_tableColumns,
      cmdb_account_tableColumns,
      cmdb_protocol_tableColumns,
      rowKey,
      // detail_tableColumns,
      model_tableColumns,
      role_tableColumns,
      netzone_tableColumns,
      attribute_tableColumns,
      framework_tableColumns,
      rack_tableColumns,
      click_add_netrack,
      delete_server_account
    }
  }
})
</script>

<style scoped></style>
