import { baseURL } from './axios.config'

export const baseAddress = baseURL

export const WebRouter = '/rbac/system/menu/web_router/'
export const WebPermission = '/rbac/system/menu/web_permission/'

export const getTaskList = baseAddress + '/task_list'

export const test = '/test'

export const login = '/api/login'

export const updateUserInfo = '/updateUser'

export const addUserInfo = '/addUser'

export const getMenuListByRoleId = '/api/getMenusByRoleId'

export const getAllMenuByRoleId = '/api/getAllMenuByRoleId'

export const deleteUserById = '/deleteUserById'

export const getDepartmentList = '/getDepartmentList'

export const addDepartment = '/addDepartment'

export const getRoleList = '/getRoleList'

export const getMenuList = '/getMenuList'

export const getParentMenuList = '/getParentMenuList'

export const getTableList = '/getTableList'

export const getCardList = '/getCardList'

export const getCommentList = '/getCommentList'

// 调度管理
export const getdispach = baseAddress + '/backend/dispatch_page/'
// 任务列表
export const jobcenterTaskUrl = baseAddress + '/backend/jobCenter/'
// 网络设备
export const get_device_expand = baseAddress + '/backend/networklist/'
// 获取webssh登录日志
export const getLoginRecordList = baseAddress + '/asset/login_record/'
export const get_server_expand = baseAddress + '/backend/server_cmdb_expand/'
// 采集方案
export const deviceCollect = baseAddress + '/backend/deviceCollect/'
// webssh
export const deviceWebSshLogin = baseAddress + '/backend/deviceWebSsh/'
export const serverWebSsh = baseAddress + '/backend/serverWebSsh/'

// 未知
export const deviceInfoChange = baseAddress + '/backend/deviceInfoChange/'
export const getperiodic_taskList = baseAddress + '/backend/periodic_task/'
// 拓扑图
export const get_topology = baseAddress + '/topology/index/'
export const topology_show = baseAddress + '/topology/show/'
// media路径
export const media_url = baseAddress + '/media/'
export const topology_media_img = baseAddress + '/media/topology/img/'
export const topology_icon = baseAddress + '/topology/topology_icon/'
// 获取业务对应表
export const getBgbuList = baseAddress + '/users/bgbu/'
// 获取变更路径(废弃ing)
export const get_api_request_log = baseAddress + '/backend/api_request_log/'
export const getinterval_schedule = baseAddress + '/backend/interval_schedule/'

export const get_cmdb_rack = baseAddress + '/asset/cmdb_rack/'
export const device_import_url = baseAddress + '/asset/import_template'
export const device_import_excel_path =
  baseAddress + '/media/cmdbExcelTemplate/import-demo.xlsx/'
export const getCmdbIdcList = baseAddress + '/asset/cmdb_idc/'
export const getCmdbRackList = baseAddress + '/asset/cmdb_rack/'
export const getCmdbRoleList = baseAddress + '/asset/cmdb_role/'
export const getVendorList = baseAddress + '/asset/cmdb_vendor/'
export const getFrameworkList = baseAddress + '/asset/framework/'
export const getAttributeList = baseAddress + '/asset/attribute/'
export const getCmdbModelList = baseAddress + '/asset/cmdb_model/'
export const device_import_template = baseAddress + '/asset/import_template'
export const getCategoryList = baseAddress + '/asset/cmdb_category/'
export const getCmdbNetzoneList = baseAddress + '/asset/cmdb_netzone/'
export const getcmdb_accountList = baseAddress + '/asset/cmdb_account/'
export const get_cmdb_idc_model = baseAddress + '/asset/cmdb_idc_model'
export const device_account_url = baseAddress + '/asset/device_account'
export const server_account_url = baseAddress + '/asset/server_account/'
export const getCmdbIdcModelList = baseAddress + '/asset/cmdb_idc_model/'
export const getNetworkDeviceList = baseAddress + '/asset/asset_networkdevice/'
export const getServerDeviceList = baseAddress + '/asset/asset_server/'
export const getServerVendorList = baseAddress + '/asset/cmdb_server_vendor/'

export const getContainerList = baseAddress + '/asset/container/'
export const getCmdbServerModelList = baseAddress + '/asset/cmdb_server_model/'
export const cmdb_chart = baseAddress + '/asset/cmdbChart'
export const get_git_config_tree = baseAddress + '/config_center/git_config'
// 采集方案
export const getCollection_planList =
  baseAddress + '/automation/api/collection_plan/'
// 采集规则
export const collection_rule_api =
  baseAddress + '/automation/api/collection_rule/'
// 自动化工作流图形
export const automation_chart = baseAddress + '/automation/automation_chart/'
// 自动化工作流 原子事件
export const AutoWorkFlow = baseAddress + '/automation/api/auto_work_flow/'
// 采集规则APIVIEW
export const collection_rule_url = baseAddress + '/automation/collection_rule/'
// 采集规则匹配方法
export const collection_match_rule_url =
  baseAddress + '/automation/api/collection_match_rule/'
// 接口利用率
export const getInterfaceUsedList =
  baseAddress + '/int_utilization/interfaceused/'

// 合规性检查结果
export const get_compliance_results =
  baseAddress + '/config_center/compliance_results'
export const ttp_parse = baseAddress + '/config_center/ttp_parse'
export const config_compliance =
  baseAddress + '/config_center/config_compliance/'
export const config_center_api = baseAddress + '/config_center/'
export const config_template = baseAddress + '/config_center/config_template/'
export const fsm_parse = baseAddress + '/config_center/fsm_parse'
export const jinja2_parse = baseAddress + '/config_center/jinja2_parse'
export const config_center = baseAddress + '/config_center'
// 插件管理
export const plugin_tree = baseAddress + '/system/plugin_tree'
