import { App, DirectiveBinding, createApp } from 'vue'
import NaLoading from '@/components/NaLoading.vue'

/**
 * 创建加载dom
 * @param el
 */
const createSpin = (el:Element) => {
  el.className = el.className + ' na-loading-wrap'
  const div = document.createElement('div')
  div.setAttribute('class', 'na-loading-mask')
  const text = el.getAttribute('naloading-text')
  const options:any = {show: true}
  if (text) {
    options.text = text
  }
  const app = createApp(NaLoading, options)
  el.appendChild(div)
  app.mount(div)
}

/**
 * 移除加载dom
 * @param el
 */
const removeSpin = (el:Element) => {
  el.className = el.className.split(' ').filter(c => c !== 'na-loading-wrap').join(' ').trim()
  const child = el.querySelector('.na-loading-mask')
  if (child) {
    el.removeChild(child)
  }
}

const loading = {
  mounted (el:Element, binding:DirectiveBinding) {
    if (binding.value) {
      createSpin(el)
    }
  },
  beforeUpdate () {   
  },
  updated (el:Element, binding:DirectiveBinding) {
    if (binding.value) {
      createSpin(el)
    } else {
      removeSpin(el)
    }
  },
  beforeUnmount () {
  },
  unmounted () { 
  }
}

const install = (app:App) => {
  app.directive('naloading', loading)
}

export default {
  install
}