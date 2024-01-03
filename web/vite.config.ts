import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'
import eslint from 'vite-plugin-eslint'
import path from 'path'
import fs  from 'fs'

// 读取代理及前端配置
let proxy = {}
let define = {}
let port = 8080
if (fs.existsSync(path.resolve(__dirname, 'proxy.json'))) {
  const proxyConfig = JSON.parse(fs.readFileSync(path.resolve(__dirname, 'proxy.json'), 'utf-8'))
  let proxyTmp = proxyConfig.proxy || {}
  for (let key in proxyTmp) {
    proxy[key] = {
      target: proxyTmp[key].target,
      ws: proxyTmp[key].ws || true,
      changeOrigin: true,
      // rewrite: (path) => path.replace(proxyTmp[key].url, '')
    }
  }
  define = (() => {
    let cfg = proxyConfig.envConfig
    if (cfg) {
      let result = {}
      for (let key in cfg) {
        result['import.meta.env.' + key] = JSON.stringify(cfg[key])
      }
      return result
    }
    return {}
  })()
  port = proxyConfig.port || 8080
}
// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    eslint(),
    AutoImport({
      imports: [
        'vue',
        {
          'naive-ui': [
            'useDialog',
            'useMessage',
            'useNotification',
            'useLoadingBar'
          ]
        }
      ]
    }),
    Components({
      resolvers: [NaiveUiResolver()]
    })
  ],
  define: {
    ...define
  },
  server: {
    port,
    proxy
  },
  resolve: {
    alias: [
      {
        find: '@/',
        replacement: path.resolve(__dirname, 'src') + '/',
      }
    ]
  }
})
