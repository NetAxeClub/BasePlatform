<template>
  <div class="main-container">
    <n-modal v-model:show="add_fsm_modal_show" preset="dialog" title="新建文件">
      <n-form
        ref="formRef"
        :model="add_fsm_model"
        label-placement="left"
        label-width="auto"
        require-mark-placement="right-hanging"
        size="small"
        :style="{
          maxWidth: '640px'
        }"
      >
        <n-form-item label="文件名" path="inputConfigPartName">
          <n-input v-model:value="add_fsm_model.name" placeholder="Input" />
        </n-form-item>
      </n-form>

      <template #action>
        <div style="display: flex; justify-content: flex-end">
          <n-button round type="primary" @click="add_fsm_template_modal_btn">
            确认
          </n-button>
        </div>
      </template>
    </n-modal>
    <n-card>
      <n-tabs
        class="card-tabs"
        default-value="config_file_tab"
        @update:value="tab_change"
        size="large"
        animated
        style="margin: 0 -4px"
        pane-style="padding-left: 4px; padding-right: 4px; box-sizing: border-box;"
      >
        <n-tab-pane name="config_file_tab" tab="文件查看">
          <div
            style="
              width: 20%;
              padding: 10px;
              border-top: 1px solid #000;
              background-color: white;
              float: left;
            "
          >
            <n-space vertical :size="12">
              <n-input v-model:value="pattern" placeholder="搜索" />
              <n-space :size="12">
                <n-switch v-model:value="showIrrelevantNodes">
                  <template #checked> 展示搜索无关的节点 </template>
                  <template #unchecked> 隐藏搜索无关的节点 </template>
                </n-switch>

                <n-button
                  round
                  type="primary"
                  size="tiny"
                  @click="add_fsm_file"
                >
                  新建
                </n-button>
              </n-space>
              <n-tree
                :show-irrelevant-nodes="showIrrelevantNodes"
                :pattern="pattern"
                :data="tree_data"
                :default-expand-all="false"
                :readonly="true"
                virtual-scroll
                :node-props="nodeProps"
                style="height: 600px"
                block-line
              />
            </n-space>
          </div>
          <div
            v-show="detail_show"
            style="
              width: 80%;
              height: 100%;
              padding: 0px;
              float: right;
              border-top: 1px solid #000;
              background-color: white;
            "
          >
            <n-card
              title="插件内容"
              size="huge"
              :bordered="false"
              content-style="padding: 0;"
            >
              <template #header-extra>
                <n-space>
                  <n-button type="info" size="small" @click="saveFSMcontent">
                    保存
                  </n-button>
                </n-space>
              </template>
              <v-ace-editor
                v-model:value="content"
                lang="python"
                theme="monokai"
                style="height: 820px"
                :options="ace_option"
              />
              <template #footer></template>
              <template #action> </template>
            </n-card>
          </div>
        </n-tab-pane>
      </n-tabs>
    </n-card>
  </div>
</template>

<script lang="ts">
import { defineComponent, h, nextTick, onMounted, ref } from 'vue'
import _ from 'lodash'
import { plugin_tree } from '@/api/url'
import { TreeOption } from 'naive-ui'
import { FormInst, useMessage } from 'naive-ui'
import useGet from '@/hooks/useGet'
import usePost from '@/hooks/usePost'
// import usePut from '@/hooks/usePut'
import ace from 'ace-builds'
import { VAceEditor } from 'vue3-ace-editor'
import modePythonUrl from 'ace-builds/src-noconflict/mode-python?url'
ace.config.setModuleUrl('ace/mode/python', modePythonUrl)
import themeMonokaiUrl from 'ace-builds/src-noconflict/theme-monokai?url'
ace.config.setModuleUrl('ace/theme/monokai', themeMonokaiUrl)
// 语法检查 暂时用不上
// import ace from 'ace-builds'
// import workerJsonUrl from 'ace-builds/src-noconflict/worker-json?url'
// ace.config.setModuleUrl('ace/mode/json_worker', workerJsonUrl)
export default defineComponent({
  name: 'PluginTree',
  components: {
    VAceEditor
  },
  setup() {
    const add_fsm_model = ref({
      name: ''
    })
    const vendor_options = ref([
      {
        label: 'hp_comware',
        value: 'hp_comware'
      },
      {
        label: 'huawei_vrp',
        value: 'huawei_vrp'
      }
    ])
    const current_filename = ref('')
    const fsm_parse_modal_show = ref(false)
    const add_fsm_modal_show = ref(false)
    const formRef = ref<FormInst | null>(null)
    const form_commit_trace = ref<FormInst | null>(null)
    const get = useGet()
    const post = usePost()
    const change_file = ref(null)
    const change_file_option = ref([])
    const tree_data = ref([])
    const detail_show = ref(false)
    const content = ref('')
    // 默认搜索内容
    const pattern = ref('')
    const showRangeRadio = ref(false)
    const showCommitRadio = ref(false)
    const message = useMessage()
    const ace_option = ref({ fontSize: 14 })
    // 获取配置文件树
    function get_config_tree() {
      get({
        url: plugin_tree,
        data: () => {
          return {
            get_tree: 1
          }
        }
      }).then((res) => {
        res.data.forEach((item) => {
          //console.log(item)
          tree_data.value = []
          nextTick(() => {
            tree_data.value.push(item)
          })
          // tree_data.value.push(item)
          // console.log(item)
        })
        // console.log(tree_data)
      })
    }
    // 配置文件树 节点点击事件
    function nodeProps({ option }: { option: TreeOption }) {
      return {
        onClick() {
          current_filename.value = option.key
          if (option.children?.length > 0) {
            message.info('还有子元素不做查询')
            detail_show.value = false
            return
          } else {
            // message.info('当前选中最后一层元素做查询' + option.label)
            get({
              url: plugin_tree,
              data: () => {
                return {
                  filename: option.key
                }
              }
            }).then((res) => {
              if (res) {
                detail_show.value = true
                content.value = res.data
              }
            })
          }
        }
        // onContextmenu (e: MouseEvent): void {
        //   optionsRef.value = [option]
        //   showDropdownRef.value = true
        //   xRef.value = e.clientX
        //   yRef.value = e.clientY
        //   console.log(e.clientX, e.clientY)
        //   e.preventDefault()
        // }
      }
    }
    // 标签页切换清空diff内容
    function tab_change(value) {
      console.log(value)
    }
    // 保存fsm内容
    function saveFSMcontent() {
      post({
        url: plugin_tree,
        data: {
          save_fsm_template: content.value,
          filename: current_filename.value
        }
      }).then((res) => {
        console.log(res)
        if (res.code == 200) {
          message.success(res.msg)
        } else {
          message.error(res.msg)
        }
      })
    }
    // 新增文件
    function add_fsm_template_modal_btn() {
      post({
        url: plugin_tree,
        data: {
          add_fsm_platform: add_fsm_model.value.name
        }
      }).then((res) => {
        console.log(res)
        if (res.code == 200) {
          message.success(res.msg)
          add_fsm_modal_show.value = false
          nextTick(() => {
            get_config_tree()
          })
        } else {
          message.error(res.msg)
        }
      })
    }
    // 新建模板
    function add_fsm_file() {
      add_fsm_modal_show.value = true
    }
    onMounted(get_config_tree)
    // onBeforeMount(() => {
    //   //console.log('2.组件挂载页面之前执行----onBeforeMount')
    //   initSocket()
    // })
    // console.log(createData())
    return {
      // tree_data,
      formRef,
      form_commit_trace,
      size: ref<'small' | 'medium' | 'large'>('medium'),
      get_config_tree,
      tree_data,
      showIrrelevantNodes: ref(false),
      nodeProps,
      content,
      detail_show,
      pattern,
      range: ref([118313526e4, Date.now()]),
      showRangeRadio,
      showCommitRadio,
      change_file,
      change_file_option,
      tab_change,
      ace_option,
      saveFSMcontent,
      fsm_parse_modal_show,
      vendor_options,
      add_fsm_template_modal_btn,
      current_filename,
      add_fsm_model,
      add_fsm_modal_show,
      add_fsm_file
    }
  }
})
</script>
<style lang="scss" scoped>
.n-form.n-form--inline {
  width: 100%;
  display: inline-flex;
  align-items: flex-start;
  align-content: space-around;
  height: 5px;
}
</style>
