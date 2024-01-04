<template>
  <div ref="playerRef"></div>
</template>

<script setup lang="ts">
import {ref, onMounted, watch, nextTick} from 'vue'
import * as AsciinemaPlayer from 'asciinema-player'
import 'asciinema-player/dist/bundle/asciinema-player.css'

const props = defineProps({
  src: [String, Object],
  opts: Object
})

const playerRef = ref()
const player = ref()

watch(() => props.src, () => {
  nextTick(() => {
    createPlayer()
  })
})

const createPlayer = () => {
  if(player.value) {
    player.value.dispose()
  }
  if (!props.src) {
    return
  }
  player.value = AsciinemaPlayer.create(props.src, playerRef.value, {
    speed: 1,
    autoPlay: false,
    fontSize: 12,
    theme: 'tango',
    ...(props.opts || {})
  })
}

const play = () => {
  player.value.play()
}

const pause = () => {
  player.value.pause()
}

onMounted(() => {
  createPlayer()
})

defineExpose({
  play,
  pause
})

</script>