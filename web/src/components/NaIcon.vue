<template>
  <i :class="props.prefix + props.name"></i>
</template>

<script setup lang="ts">
type Props = {
  /**icon前缀*/
  prefix: string
  /**icon名称*/
  name: string
}
const props:Props = defineProps({
  prefix: {
    default: 'na-icon-'
  },
  name: {
    required: true,
    type: String
  }
})
</script>