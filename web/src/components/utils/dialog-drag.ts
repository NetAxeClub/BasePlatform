const getTranslateValues = (element:HTMLElement) => {
  const style = window.getComputedStyle(element)
  const matrix = style.transform
  if (matrix === 'none') {
    return {x: 0, y: 0}
  }
  const values = matrix.split('(')[1].split(')')[0].split(',')
  return { x: parseFloat(values[values.length - 2]), y: parseFloat(values[values.length - 1]) }
}


const listeners: { name: string; listener: (e: MouseEvent) => void }[] = []

export function drag (wrap: HTMLElement) {
  const range = {
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
  }
  wrap.style.cursor = 'move'
  const parent = wrap.parentElement
  if (!parent) {
    return
  }
  let startX = 0
  let startY = 0
  let status = ''
  wrap.addEventListener('mousedown', (e: MouseEvent) => {
    e.preventDefault()
    status = 'down'
    const top = parseFloat(parent.style.top || '0')
    range.left = -((document.documentElement.clientWidth - parent.clientWidth) / 2)
    range.right = Math.abs(range.left)
    const origin = -((document.documentElement.clientHeight - parent.clientHeight) / 2)
    range.top = origin - top
    range.bottom = Math.abs(origin) - top
    const translateVal = getTranslateValues(parent)
    startX = e.clientX - (translateVal.x || 0)
    startY = e.clientY - (translateVal.y || 0)
    const handleMove = (e: MouseEvent) => {
      if (status !== 'down') return
      const moveX = e.clientX
      const moveY = e.clientY
      let distX = moveX - startX
      let distY = moveY - startY
      if (distX <= range.left) {
        distX = range.left
      }
      if (distX >= range.right) {
        distX = range.right
      }
      if (distY <= range.top) {
        distY = range.top
      }
      if (distY >= range.bottom) {
        distY = range.bottom
      }
      parent.style.transform = `translate(${distX}px, ${distY}px)`
    }
    const handleUp = () => {
      status = 'up'
      document.removeEventListener('mousemove', handleMove)
      document.removeEventListener('mouseup', handleUp)
    }
    listeners.push(
      {
        name: 'mousemove',
        listener: handleMove,
      },
      {
        name: 'mouseup',
        listener: handleUp,
      }
    )
    document.addEventListener('mousemove', handleMove)
    document.addEventListener('mouseup', handleUp)
    wrap.addEventListener('mouseup', () => {
      handleUp()
    })
  })
}

export function unDrag (wrap: HTMLElement) {
  listeners.forEach((it: any) => {
    wrap.removeEventListener(it.name, it.listener)
  })
  listeners.length = 0
}
