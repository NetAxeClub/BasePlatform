import { FormItemRule } from 'naive-ui'

/**
 * 校验下拉数字时校验不通过
 * @param _rule
 * @param value 
 */
export const validateSelect = (_rule:FormItemRule, value: string | number):boolean => {
  return !!(value || typeof value === 'number')
}

/**
 * 手机/电话校验
 */
export const telphone = (val:string):boolean => {
  return /((^[1-9]\d{6,7})|(^0[1-9]\d{1,2}-[1-9]\d{6,7})|(^1[3-9]\d{9}))$/.test(val)
}
/**
 * 固话校验
 * @param val
 * @returns 
 */
export const telephone = (val:string):boolean => {
  return /((^[1-9]\d{6,7})|(^0[1-9]\d{1,2}-[1-9]\d{6,7}))$/.test(val)
}

/**
 * 手机号校验
 * @param val
 * @returns 
 */
export const mobilephone = (val:string):boolean => {
  return /^1[3-9]\d{9}$/.test(val)
}

/**
 * ipv4校验
 * @param val
 * @returns 
 */
export const ipv4 = (val:string):boolean => {
  return /^((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.){3}(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])$/.test(val)
}

/**
 * ipv6校验
 * @param val 
 * @returns 
 */
export const ipv6 = (val:string):boolean => {
  return /^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$/.test(val)
}

/**
 * host校验
 * @param val
 * @returns 
 */
export const host = (val:string):boolean => {
  return /^((?!-)[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,6}$/.test(val)
}
/**
 * 邮箱校验
 */
export const mail = (val:string):boolean => {
  return /^[a-zA-Z\d_.-]{1,}@[a-zA-Z\d-]{1,}(\.[a-zA-Z\d]{1,}){1,}$/.test(val)
}

/**
 * 批量邮箱校验
 * @param val 邮箱
 * @param split 邮箱间间隔
 */
export const mails = (val:string, split = ';'):boolean => {
  if (!val) {
    return false
  } else {
    let arr = val.split(split)
    return arr.every(el => mail(el))
  }
}
