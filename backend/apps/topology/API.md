# 拓扑图 API 文档

## 1. 拓扑管理接口

### 1.1 获取拓扑列表
**接口**: `GET /api/topology/list/`

**响应**:
```json
{
  "code": 200,
  "data": [{"name": "拓扑1", "parent": "root"}],
  "msg": "获取拓扑数据成功"
}
```

### 1.2 创建拓扑
**接口**: `POST /api/topology/create/`

**请求体**:
```json
{
  "create_graph": {
    "name": "新拓扑",
    "nodes": [],
    "links": []
  }
}
```

**响应**:
```json
{
  "code": 200,
  "msg": "新建拓扑图成功"
}
```

## 2. 拓扑显示接口

### 2.1 获取拓扑详情
**接口**: `GET /api/topology/show/?graph=<拓扑名>`

**响应**:
```json
{
  "code": 200,
  "data": {"name": "拓扑1", "nodes": [], "links": []},
  "msg": "获取拓扑数据成功"
}
```

### 2.2 保存拓扑
**接口**: `POST /api/topology/show/`

**请求体**:
```json
{
  "save_graph": {
    "name": "拓扑名",
    "nodes": [],
    "links": []
  }
}
```

### 2.3 删除节点
**接口**: `POST /api/topology/show/`

**请求体**:
```json
{
  "name": "拓扑名",
  "del_nodes": ["节点ID1", "节点ID2"]
}
```

### 2.4 添加手动连线
**接口**: `POST /api/topology/show/`

**请求体**:
```json
{
  "name": "拓扑名",
  "a_name": "设备A名称",
  "b_name": "设备B名称",
  "a_device": "设备A IP",
  "b_device": "设备B IP",
  "a_interface": "接口A",
  "b_interface": "接口B"
}
```

### 2.5 删除连线
**接口**: `POST /api/topology/show/`

**请求体**:
```json
{
  "name": "拓扑名",
  "del_link": "连线ID"
}
```

### 2.6 删除拓扑
**接口**: `DELETE /api/topology/show/?graph=<拓扑名>`

## 3. 图标库接口

### 3.1 获取图标树
**接口**: `GET /api/topology/icons/`

**响应**:
```json
{
  "code": 200,
  "data": [{"name": "目录1", "children": []}],
  "msg": "获取图标库成功"
}
```

### 3.2 创建目录
**接口**: `POST /api/topology/icons/`

**请求体**:
```json
{
  "dir_name": "新目录",
  "current_path": "/"
}
```

### 3.3 上传图标
**接口**: `POST /api/topology/icons/`

**请求体**: FormData
- `upload_path`: 上传路径
- `filename`: 文件名
- `icons`: 图标文件

### 3.4 删除图标
**接口**: `DELETE /api/topology/icons/?delete_path=<路径>`
