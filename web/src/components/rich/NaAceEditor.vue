<template>
   <v-ace-editor v-model:value="currentVal" :lang="lang" :theme="theme" :style="{height: computedHeight}" :readonly="computedReadonly"></v-ace-editor>
</template>
<script setup lang="ts">
import {VAceEditor} from 'vue3-ace-editor'
import {ref, computed, watch} from 'vue'
import ace from 'ace-builds'
import themeMonokai from 'ace-builds/src-noconflict/theme-monokai'
import themeChrome from 'ace-builds/src-noconflict/theme-chrome'

import modePython  from 'ace-builds/src-noconflict/mode-python'
import modeYaml from 'ace-builds/src-noconflict/mode-yaml'
import modeHtml from 'ace-builds/src-noconflict/mode-html'
import modeJson from 'ace-builds/src-noconflict/mode-json'
import modeJava from 'ace-builds/src-noconflict/mode-java'
import modeGo from 'ace-builds/src-noconflict/mode-golang'
import modeSass from 'ace-builds/src-noconflict/mode-sass'
import modeCss from 'ace-builds/src-noconflict/mode-css'
import modeNginx from 'ace-builds/src-noconflict/mode-nginx'
import modeText from 'ace-builds/src-noconflict/mode-text'
import modeSql from 'ace-builds/src-noconflict/mode-sql'
import modeXml from 'ace-builds/src-noconflict/mode-xml'
import modeTypescript from 'ace-builds/src-noconflict/mode-typescript'
import modeDjango from 'ace-builds/src-noconflict/mode-django'
import modeNunjucks from 'ace-builds/src-noconflict/mode-nunjucks'

const emit = defineEmits(['update:value', 'change'])

export type LangType = 'nunjucks' | 'python' | 'yaml' | 'html' | 'json' | 'java' | 'golang' | 'sass' | 'css' | 'sql' | 'xml' | 'typescript' | 'text' | 'nginx' | 'django'
export type ThemeType = 'monokai' | 'chrome'

const modes = {
  'python': modePython,
  'yaml': modeYaml,
  'html': modeHtml,
  'json': modeJson,
  'java': modeJava,
  'golang': modeGo,
  'sass': modeSass,
  'css': modeCss,
  'sql': modeSql,
  'xml': modeXml,
  'typescript': modeTypescript,
  'text': modeText,
  'nginx': modeNginx,
  'django': modeDjango,
  'nunjucks': modeNunjucks
}
const themes = {
  chrome: themeChrome,
  monokai: themeMonokai
}


const setModuleUrl = () => {
  for (let key in modes) {
    ace.config.setModuleUrl(`ace/mode/${key}`, (modes as any)[key])
  }
  for (let key in themes) {
    ace.config.setModuleUrl(`ace/theme/${key}`, (themes as any)[key])
  }
}
setModuleUrl()

interface Props {
  value: string
  lang?: LangType
  theme?: ThemeType
  height?: number
  disabled?: boolean
  readonly?: boolean
  options?: any
}

const props = withDefaults(defineProps<Props>(), {
  value: '',
  lang: 'text',
  theme: 'monokai',
  options: {
    fontSize: 14
  }
})

const computedHeight = computed(() => {
  return props.height ? props.height + 'px' : '300px'
})

const computedReadonly = computed(() => {
  return !!(props.disabled || props.readonly)
})

const currentVal = ref(props.value)

watch(() => props.value, () => {
  currentVal.value = props.value
})
watch(() => currentVal.value, () => {
  emit('update:value', currentVal.value)
  emit('change', currentVal.value)
})

</script>
<style lang="scss">
.ace-editor-wrap {
  padding: 20px 0;
  &.monokai {
    background-color: #272822;
  }
}
</style>