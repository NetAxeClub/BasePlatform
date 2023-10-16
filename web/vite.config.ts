import vue from '@vitejs/plugin-vue'
import viteSvgIcons from 'vite-plugin-svg-icons'
// @ts-ignore
import path from 'path'
import { loadEnv } from 'vite'
import vitePluginCompression from 'vite-plugin-compression'
import ViteComponents from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

import vueJsx from '@vitejs/plugin-vue-jsx'

export default ({mode}) => {
  const env = loadEnv(mode, './')
  return {
    base: '/',
    plugins: [
      vue(),
      viteSvgIcons({
        iconDirs: [path.resolve(process.cwd(), 'src/icons')],
        symbolId: 'icon-[dir]-[name]',
      }),
      vitePluginCompression({
        threshold: 1024 * 10,
      }),
      ViteComponents({
        resolvers: [NaiveUiResolver()],
      }),
      vueJsx(),
    ],
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: '@use "./src/styles/variables.scss" as *;',
        },
      },
    },
    resolve: {
      alias: [
        {
          find: '@/',
          replacement: path.resolve(process.cwd(), 'src') + '/',
        },
      ],
    },
    server: {
      open: true,
      port: 32200,
      proxy: {
        '/base_platform': {
          target: env.VITE_BASIC_URL,
          ws: true, //代理websockets
          changeOrigin: true, // 
          rewrite: (path: string) => path.replace(/^\/base_platform/, '/base_platform'),
        },
        '/rbac': {
          target: env.VITE_RBAC_URL,
          ws: true, //代理websockets
          changeOrigin: true, // 
          rewrite: (path: string) => path.replace(/^\/rbac/, '/rbac'),
        },
      }
    },
  }
}
