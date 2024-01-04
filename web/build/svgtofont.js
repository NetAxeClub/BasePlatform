import svgtofont from 'svgtofont'
import fs from 'fs'
import fsExtra from 'fs-extra'
import path from 'path'

const currentDirname = path.dirname(import.meta.url).replace('file:///', '')
async function start () {
  const outDir = path.join(currentDirname, '../src/assets/font')
  const prefix = 'na-icon'
  // 删除font目录内容
  try {
    if (fs.existsSync(outDir)) {
      await fsExtra.rm(outDir, {recursive: true})
    }
  } catch (e) {
    console.error(e)
  }
  svgtofont({
    src: path.join(currentDirname, '../src/svg'),
    dist: outDir,
    fontName: prefix,
    css: true,
    startUnicode: 0xea01, // unicode start number
    svgicons2svgfont: {
      fontHeight: 1000,
      normalize: true
    },
    // website = null, no demo html files
    website: {
      title: 'NetAxe',
      // Must be a .svg format image.
      logo: '',
      version: '1.0.0',
      meta: {
        description: '',
        keywords: ''
      },
      description: '',
      // Add a Github corner to your website
      // Like: https://github.com/uiwjs/react-github-corners
      corners: {
        // url: 'https://github.com/jaywcjlove/svgtofont',
        url: '',
        width: 62, // default: 60
        height: 62, // default: 60
        bgColor: '#dc3545' // default: '#151513'
      },
      links: [
        {
          title: 'Font Class',
          url: 'index.html'
        }
      ],
      footerInfo: `<div>
      <div>提示：使用时前加na-icon前缀</div>
        <div>例如：user图标，使用时如：&lt;i class="na-icon-user"&gt;&lt;/i&gt;</div>
      </div>`
    }
  }).then(() => {
    // 生成json数据
    const files = fs.readdirSync(path.join(currentDirname, '../src/svg'))
    let jsonObj = []
    files.forEach(file => {
      const name = file.replace('.svg', '')
      jsonObj.push(prefix + '-' + name)
    })
    // 写入json文件
    fs.writeFileSync(path.join(currentDirname, '../src/assets/font/icons.json'), JSON.stringify(jsonObj))
  })
}

start()