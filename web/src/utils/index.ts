import { DialogApiInjection } from 'naive-ui/es/dialog/src/DialogProvider'
import { MessageApiInjection } from 'naive-ui/es/message/src/MessageProvider'
import { NotificationApiInjection } from 'naive-ui/es/notification/src/NotificationProvider'
import ClipboardJS from 'clipboard'

export const isEmpty = (val:any) => {
  return val === '' || val === null || val === undefined
}

/**
 * 用于缓存全局
 */
export const GLOABAL = {
  message: null as MessageApiInjection | null,
  notification: null as NotificationApiInjection | null,
  dialog: null as DialogApiInjection | null
}

const _messageMehods = ['destroyAll', 'create', 'error', 'info', 'loading', 'success', 'warning']

const _noticeMthods = ['create', 'destroyAll', 'error', 'info', 'success', 'warning']

const _dialogMehods = ['destroyAll', 'create', 'error', 'info', 'success', 'warning']
/**
 * 创建初始化消息方法
 */
const _createMessageMethod = (type: string) => {
  return (...args:any[]) => {
    // if (!GLOABAL.notification) {
    //   console.error('消息未初始化')
    // }
    (GLOABAL.message as any)[type](...args)
  }
}

const _createNotificationMethod = (type:string) => {
  return (...args:any[]) => {
    // if (!GLOABAL.message) {
    //   console.error('通知未初始化')
    // }
    (GLOABAL.notification as any)[type](...args)
  }
}

const _createDialogMethod = (type:string) => {
  return (...args:any[]) => {
    // if (!GLOABAL.dialog) {
    //   console.error('弹框未初始化')
    // }
    (GLOABAL.dialog as any)[type](...args)
  }
}


/**
 * 消息弹框
 * @param args
 */
const Message = {} as MessageApiInjection

_messageMehods.forEach(type => {
  (Message as any)[type] = _createMessageMethod(type)
})

const Notification = {} as NotificationApiInjection

_noticeMthods.forEach(type => {
  (Notification as any)[type] = _createNotificationMethod(type)
})

const Dialog = {} as DialogApiInjection

_dialogMehods.forEach(type => {
  (Dialog as any)[type] = _createDialogMethod(type)
})

/**
 * 复制文本
 * @param val
 */
export const copy = (val:string) => {
  const button = document.createElement('button')
  const clip = new ClipboardJS(button, {
    text: () => val
  })
  clip.on('success', () => {
    Message.success('复制成功')
  })
  button.click()
}


export {
  Message,
  Notification,
  Dialog
}