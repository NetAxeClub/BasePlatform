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
// 采集方案
export const deviceCollect = baseAddress + '/backend/deviceCollect/'
// webssh
export const deviceWebSshLogin = baseAddress + '/backend/deviceWebSsh/'
export const automation_chart = baseAddress + '/backend/automationChart/'
// 未知
export const deviceInfoChange = baseAddress + '/backend/deviceInfoChange/'
export const getperiodic_taskList = baseAddress + '/backend/periodic_task/'
// 拓扑图
export const get_topology = baseAddress + '/topology/index/'
export const topology_show = baseAddress + '/topology/show/'
export const topology_media_img = baseAddress + '/media/topology/img/'
export const topology_icon = baseAddress + '/topology/topology_icon/'
// 获取业务对应表
export const getBgbuList = baseAddress + '/users/bgbu/'
// 获取变更路径(废弃ing)
export const get_api_request_log = baseAddress + '/backend/api_request_log/'
export const getinterval_schedule = baseAddress + '/backend/interval_schedule/'

export const get_cmdb_rack = baseAddress + '/asset/cmdb_rack/'
export const device_import_url = baseAddress + '/asset/excel/'
export const getCmdbIdcList = baseAddress + '/asset/cmdb_idc/'
export const getCmdbRackList = baseAddress + '/asset/cmdb_rack/'
export const getCmdbRoleList = baseAddress + '/asset/cmdb_role/'
export const getVendorList = baseAddress + '/asset/cmdb_vendor/'
export const getFrameworkList = baseAddress + '/asset/framework/'
export const getAttributeList = baseAddress + '/asset/attribute/'
export const getCmdbModelList = baseAddress + '/asset/cmdb_model/'
export const device_import_template = baseAddress + '/asset/excel/'
export const getCategoryList = baseAddress + '/asset/cmdb_category/'
export const getCmdbNetzoneList = baseAddress + '/asset/cmdb_netzone/'
export const getcmdb_accountList = baseAddress + '/asset/cmdb_account/'
export const get_cmdb_idc_model = baseAddress + '/asset/cmdb_idc_model'
export const device_account_url = baseAddress + '/asset/device_account/'
export const getCmdbIdcModelList = baseAddress + '/asset/cmdb_idc_model/'
export const getNetworkDeviceList = baseAddress + '/asset/asset_networkdevice/'

export const get_git_config_tree = baseAddress + '/config_center/git_config'

export const getCollection_planList = baseAddress + '/automation/collection_plan/'

export const getInterfaceUsedList = baseAddress + '/int_utilization/interfaceused/'

// 合规性检查结果
export const get_compliance_results = baseAddress + '/config_center/compliance_results'
export const ttp_parse = baseAddress + '/config_center/ttp_parse'
export const config_compliance = baseAddress + '/config_center/config_compliance/'
export const config_center_api = baseAddress + '/config_center/'
export const config_template = baseAddress + '/config_center/config_template/'
export const fsm_parse = baseAddress + '/config_center/fsm_parse'
export const jinja2_parse = baseAddress + '/config_center/jinja2_parse'
export const config_center = baseAddress + '/config_center'