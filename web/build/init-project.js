import fs from 'fs'
import path from 'path'
import yaml from 'js-yaml'
import minimist from 'minimist'
import simpleGit from 'simple-git'
import os from 'os'

console.log(os.type)
const argv = minimist(process.argv.slice(2))
const stage = argv.stage
const branch = argv.branch
const env = argv.env
if (!stage) {
  throw new Error('请在执行脚本时指定--stage参数')
}
let currentDirname = ''
if (os.type().indexOf('Windows') > -1) {
  currentDirname = path.dirname(import.meta.url).replace('file:///', '')
} else {
  currentDirname = path.dirname(import.meta.url).replace('file://', '')
}

function _projectInit (project, projectInitPath) {
  if (project.uninit) {
    console.log('该项目无初始化文件生成\n')
    return
  }
  // 生成子项目初始化文件
  fs.writeFileSync(projectInitPath, `import '@/project/${project.pathname}/init'
import route1 from '@/project/${project.pathname}/router'
  
export const projectNames = ['${project.pathname}']
export const routes = [
  ...route1
]`, {encoding: 'utf8'})
  // 生成前端代理及全局注入配置文件
  let envStr = env || project.env || 'development'
  const jsonObj = {
    port: project.port,
    proxy: project.proxy || {},
    envConfig: (() => {
      if (project.envConfig && project.envConfig[envStr]) {
        return  project.envConfig[envStr]
      }
      return {}
    })()
  }
  fs.writeFileSync(path.join(currentDirname, '../proxy.json'), JSON.stringify(jsonObj), {encoding: 'utf8'})
}
function start () {
  // 读取配置文件
  let gitConfig = {}
  let gitConfigPath = path.join(currentDirname, '../config/project.local.yml')

  if (!fs.existsSync(gitConfigPath)) {
    gitConfigPath = path.join(currentDirname, '../config/project.yml')
  }

  gitConfig = yaml.load(fs.readFileSync(gitConfigPath, 'utf8'))

  const project = gitConfig.project.filter(el => el.pathname === stage)[0]
  // 从git上拉取代码并创建目录
  const projectInitPath =  path.join(currentDirname, '../src/project-init.ts')
  if (project) {
    if (fs.existsSync(path.join(currentDirname, `../src/project/${project.pathname}`))) {
      _projectInit(project, projectInitPath)
      console.log(`${project.pathname}已存在\n`)
      return
    }
    console.log('------------------------------项目初始化导入开始----------------------------------------\n')
    // 删除project-init.ts文件
    if (fs.existsSync(projectInitPath)) {
      fs.rmSync(projectInitPath)
    }
    let usrStr = ''
    let remote = project.url
    if ((gitConfig.username && gitConfig.password) || (project.username && project.password)) {
      usrStr = `${project.username || gitConfig.username}:${project.password || gitConfig.password}@`
      remote = `https://${usrStr}${project.url.replace('https://', '')}`
    }
    simpleGit().clone(remote, path.join(currentDirname, `../src/project/${project.pathname}`), {
      '--branch': branch || project.branch
    })
      .then(() => {
        // 初始化project-init.ts文件
        _projectInit(project, projectInitPath)
        console.log('------------------------------项目初始化导入成功----------------------------------------\n')
      })
      .catch((err) => console.error('failed: ', err))
  }
}

start()
