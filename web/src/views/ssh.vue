<template>
  <div class="sshcontainer">
    <div :id="device_id" style="padding: 10px"></div>
  </div>
</template>
<script lang="ts">
import {
  // computed,
  defineComponent,
  // h,
  nextTick,
  onMounted,
  // reactive,
  // Ref,
  ref,
  // shallowReactive
} from 'vue'
// import LyXterm from "@/components/terminal/xterm";
// import { deviceWebSshLogin } from '@/api/url'
// import useGet from '@/hooks/useGet'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
// import { AttachAddon } from 'xterm-addon-attach'
// import router from '@/router'
export default defineComponent({
  name: 'Ssh',
  // components: {LyXterm},
  setup() {
    const WebSocketProxy = new Proxy(WebSocket, {
      construct: function (target, arg) {
        try {
          return new target(...arg)
        } catch (error) {
          return error
        }
      }
    })
    var terminalSocket = ref(null)
    var term = ref(null)

    const device_id = ref('')
    const wsurl = ref('')

    // const get = useGet()

    function initSocket() {
      // webssh_list.length = 0
      //console.log(window.location.search)
      let url = window.location.href
      let getqyinfo = url.split('?')[1]
      let getqys = new URLSearchParams('?' + getqyinfo)
      let id = getqys.get('id')
      let remote_ip = getqys.get('remote_ip')
      var terminal_id = id
      device_id.value = id!
      const ws_scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const ws_url =
        ws_scheme +
        '://' +
        window.location.host +
        '/base_platform/ws/ssh/' +
        device_id.value +
        '/?' +
        remote_ip
      terminalSocket.value = new WebSocketProxy(ws_url)
      nextTick(() => {
        terminalSocket.value.onerror = function (e) {
          console.log(e)
        }
        terminalSocket.value.onopen = function () {
          console.log('连接成功！')
          let init_width = 9
          let init_height = 15
          const _width = window.innerWidth
          const _height = window.innerHeight
          var cols = Math.floor(_width / init_width)
          var rows = Math.floor(_height / init_height)
          term.value = new Terminal({
            rendererType: 'canvas', //渲染类型
            rows: rows, //行数
            cols: cols, // 不指定行数，自动回车后光标从下一行开始
            fontSize: 15,
            scrollback: 500, //终端中的回滚量
            convertEol: true, //启用时，光标将设置为下一行的开头
            cursorBlink: true, //光标闪烁
            disableStdin: false, //是否应禁用输入。
            cursorStyle: 'block', //光标样式
            theme: {
              foreground: '#00ff00', //字体
              background: 'black', //背景色#060101
              cursor: '#00ff00' //设置光标
            }
          })
          console.log(terminal_id)
          // const attachAddon = new AttachAddon(terminalSocket)
          // const attachAddon = new AttachAddon(terminalSocket)
          term.value.open(document.getElementById(terminal_id))
          const fitAddon = new FitAddon() // 全屏插件
          // term.loadAddon(attachAddon)
          term.value.loadAddon(fitAddon)
          // term.fitAddon.fit()
          term.value.focus()
          // var input = localStorage.getItem('init_cmd')
          var input = 'terminal monitor'
          // socketOpen = true
          if (input.length > 0) {
            terminalSocket.value.send(input)
            terminalSocket.value.send('\r')
          }
          term.value.onData((val) => {
            terminalSocket.value.send(val)
          })
          // term.write('terminal monitor')
          terminalSocket.value.onmessage = function (evt) {
            var received_msg = evt.data.toString()
            //console.log('接受消息：', received_msg)
            // term.onData((received_msg) => {
            term.value.write(received_msg)
            // })
          }

          terminalSocket.value.onclose = function (event) {
            //console.log('连接关闭！', event)
          }
          terminalSocket.value.onerror = function (event) {
            //console.log('连接异常！', event)
          }
        }
      })
      // })
    }

    onMounted(initSocket)

    return {
      device_id,
      wsurl,

      initSocket,

      terminalSocket,

      term
    }
  }
})
</script>

<style lang="scss" scoped>
.sshcontainer {
  background: black;
  height: 100%;
  width: 100%;
  /*background: black;*/
  /*padding: 10px;*/
  overflow: hidden;
}
</style>
