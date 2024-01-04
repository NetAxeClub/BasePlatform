import { FormItemRule } from 'naive-ui'

/**
 * 校验下拉数字时校验不通过
 * @param _rule
 * @param value 
 */
export const validateSelect = (_rule:FormItemRule, value: string | number):boolean => {
  return !!(value || typeof value === 'number')
}