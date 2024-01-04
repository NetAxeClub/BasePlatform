import { Dialog } from '.'

/**
 * 通用二次删除确认弹框
 * @param content
 * @returns 
 */
export const commonDelDialog = (content:string = '确定删除?') => {
  return new Promise((resolve, reject) => {
    Dialog.warning({
      title: '提示',
      content,
      positiveText: '确定',
      negativeText: '取消',
      onPositiveClick: () => {
        resolve('确定')
      },
      onNegativeClick: () => {
        reject('取消')
      }
    })
  })
}