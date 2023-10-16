<template>
  <n-card
    :content-style="{ padding: '10px' }"
    :header-style="{ padding: '10px' }"
    :segmented="true"
  >
    <template #header>
      <!--      <n-skeleton text style="width: 50%" v-if="loading"/>-->
      <!--      <template v-else>-->
      <div class="text-sm"
        >最近一次接口利用率
        <span style="font-weight: bold">总数:{{ total_count }}</span>
      </div>
      <!--      </template>-->
    </template>
    <div class="chart-item-container">
      <!--      <n-skeleton text v-if="loading" :repeat="4"/>-->
      <!--      <template v-else>-->
      <div ref="InterfaceUsedChart" class="chart-item"></div>
      <!--      </template>-->
    </div>
  </n-card>
</template>

<script lang="ts">
  import { dispose, graphic } from 'echarts'
  import useEcharts from '@/hooks/useEcharts'
  import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
  import { cmdb_chart } from '@/api/url'
  import useGet from '@/hooks/useGet'

  // var colorArr = ['#218de0', '#01cbb3', '#85e647', '#5d5cda', '#05c5b0', '#c29927']
  // var colorAlpha = [
  //   'rgba(60,170,211,0.05)',
  //   'rgba(1,203,179,0.05)',
  //   'rgba(133,230,71,0.05)',
  //   'rgba(93,92,218,0.05)',
  //   'rgba(5,197,176,0.05)',
  //   'rgba(194,153,39,0.05)',
  // ]

  export default defineComponent({
    name: 'InterfaceUsedChart',
    setup() {
      const total_count = ref(0)
      const get = useGet()
      const loading = ref(true)
      const InterfaceUsedChart = ref<HTMLDivElement | null>(null)
      const interface_used_option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'shadow',
          },
        },
        legend: {},
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true,
        },
        xAxis: [
          {
            type: 'category',
            data: [],
          },
        ],
        yAxis: [
          {
            type: 'value',
          },
        ],
        series: [
          {
            name: '已使用',
            type: 'bar',
            stack: 'Ad',
            emphasis: {
              focus: 'series',
            },
            data: [],
            label: {
              normal: {
                show: true,
                position: 'inside',
              },
              formatter: '已使用{@value}',
            },
          },
          {
            name: '未使用',
            type: 'bar',
            stack: 'Ad',
            emphasis: {
              focus: 'series',
            },
            data: [],
            label: {
              normal: {
                show: true,
                position: 'inside',
              },
              formatter: '{@value}',
            },
          },
          {
            name: '总计数目',
            type: 'bar',
            stack: 'Ad',
            emphasis: {
              focus: 'series',
            },
            data: [],
            label: {
              normal: {
                show: true,
                position: 'top',
              },
              formatter: '{@value}',
            },
          },
        ],
      }
      // const init = () => {
      //   setTimeout(() => {
      //     loading.value = false
      //     nextTick(() => {
      //       useEcharts(InterfaceUsedChart.value as HTMLDivElement).setOption(interface_used_option)
      //     })
      //   }, 1000)
      // }
      const updateChart = () => {
        useEcharts(InterfaceUsedChart.value as HTMLDivElement).resize()
      }

      function echarts_init() {
        // nextTick(() => {
        useEcharts(InterfaceUsedChart.value as HTMLDivElement).setOption(interface_used_option)
        // })
        nextTick(() => {
          get({
            url: cmdb_chart,
            data: () => {
              return {
                interface_used: 1,
                bgbu: '["16"]',
                token: '1',
              }
            },
          }).then((res) => {
            console.log('interface_used', res)
            total_count.value = res['total']
          // 添加接口分类
            interface_used_option.xAxis[0]['data'].push(...res.category_list)
            // interface_used_option.series[].data.push(item.value)
             // 添加已使用
            res.used.forEach((item, index) => {
              // interface_used_option.xAxis.data.push(item.name)
              interface_used_option.series[0].data.push(item.value)
              useEcharts(InterfaceUsedChart.value as HTMLDivElement).setOption(
                interface_used_option
              )
            })
            // 添加未使用
            res.unused_list.forEach((item, index) => {
              // interface_used_option.xAxis.data.push(item.name)
              interface_used_option.series[1].data.push(item.value)
              useEcharts(InterfaceUsedChart.value as HTMLDivElement).setOption(
                interface_used_option
              )
            })
            res.total_count_list.forEach((item, index) => {
              // interface_used_option.xAxis.data.push(item.name)
              interface_used_option.series[2].data.push(item.value)
              useEcharts(InterfaceUsedChart.value as HTMLDivElement).setOption(
                interface_used_option
              )
            })
          })
        })
      }

      // onMounted(init)
      onMounted(echarts_init)
      onBeforeUnmount(() => {
        dispose(InterfaceUsedChart.value as HTMLDivElement)
      })
      return {
        echarts_init,
        interface_used_option,
        loading,
        InterfaceUsedChart,
        updateChart,
        total_count,
      }
    },
  })
</script>

<style lang="scss" scoped>
  .chart-item-container {
    width: 100%;

    .chart-item {
      height: 350px;
    }
  }
</style>
