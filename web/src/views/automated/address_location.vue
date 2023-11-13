<template>
  <div class="main-container">
    <BsTable show-filter-column :columns="columns" :data="tableData" :initShowColumns="['name']"/>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, nextTick } from 'vue'
import BsTable from './components/BsTable/index.vue'

const tableData = [{
  name: '张三',
  age: 10,
  address: '达大厦',
  age1: 'dasdsa'
}, {
  name: '李四',
  age: 22,
  address: '打撒所',
  age1: 'dasdsa'
}]

const columns = [
  {
    title: 'Name',
    key: 'name'
  },
  {
    title: 'Age',
    key: 'age'
  },
  {
    title: 'Address',
    key: 'address'
  }, 
  {
    title: 'Age1',
    key: 'age1'
  },
  {
    title: 'Address1',
    key: 'address1'
  }
]
</script>

<style lang="scss" scoped></style>
