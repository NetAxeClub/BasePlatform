<template>
  <n-card
    :content-style="{ padding: '10px' }"
    :header-style="{ padding: '10px' }"
    :segmented="true"
  >
    <template #header>
      <!--      <n-skeleton text style="width: 50%" v-if="loading" />-->
      <!--      <template v-else>-->
      <div class="text-sm">模块原子事件数量</div>
      <!--      </template>-->
    </template>
    <div class="chart-item-container">
      <!--      <n-skeleton text v-if="loading" :repeat="4" />-->
      <!--      <template v-else>-->
      <div ref="taskModuleChart" class="chart-item"></div>
      <!--      </template>-->
    </div>
  </n-card>
</template>

<script lang="ts">
import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { dispose, graphic } from 'echarts'
import useEcharts from '@/hooks/useEcharts'
import useGet from '@/hooks/useGet'
import { automation_chart } from '@/api/url'
export default defineComponent({
  name: 'TaskModuleChart',
  setup() {
    const loading = ref(true)
    // const taskModuleChart = ref<HTMLDivElement | null>(null)
    const taskModuleChart = ref<HTMLDivElement | null>(null)
    const get = useGet()
    const event_task_module_option = {
      title: {
        // text: 'Referer of a Website',
        // subtext: 'Fake Data',
        left: 'center'
      },
      tooltip: {
        trigger: 'item'
      },
      // legend: {
      //   orient: 'vertical',
      //   left: 'left'
      // },
      series: [
        {
          name: '模块原子事件数量',
          type: 'pie',
          radius: '50%',
          data: [
            // { value: 1048, name: 'Search Engine' },
            // { value: 735, name: 'Direct' },
            // { value: 580, name: 'Email' },
            // { value: 484, name: 'Union Ads' },
            // { value: 300, name: 'Video Ads' }
          ],
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          },
          itemStyle: {
            color: function (params) {
              //注意，如果颜色太少的话，后面颜色不会自动循环，最好多定义几个颜色
              var colorList = [
                '#3cb2ef',
                '#37d8ff',
                '#71f6f9',
                '#aefdca',
                '#fff065',
                '#ffae8b',
                '#ff7da1'
              ]
              return colorList[params.dataIndex % colorList.length]
            }
          }
        }
      ]
    }
    const init = () => {
      setTimeout(() => {
        loading.value = false
        nextTick(() => {
          const echartInstance = useEcharts(
            taskModuleChart.value as HTMLDivElement
          )
          echartInstance.setOption(event_task_module_option)
        })
      }, 1000)
    }
    const updateChart = () => {
      useEcharts(taskModuleChart.value as HTMLDivElement).resize()
    }
    function echarts_init() {
      // nextTick(() => {
      useEcharts(taskModuleChart.value as HTMLDivElement).setOption(
        event_task_module_option
      )
      // })
      nextTick(() => {
        get({
          url: automation_chart,
          data: () => {
            return {
              event_task_module: 1
            }
          }
        }).then((res) => {
          // console.log('event_task_module_trend', res)
          res.data.forEach((item) => {
            // event_task_module_option.xAxis.data.push(item.log_time)
            // event_task_module_option.radar.indicator.push({
            //   name:item['idc__name'],max:1000
            // })
            event_task_module_option.series[0].data.push({
              value: item['sum_count'],
              name: item['task']
            })
            // event_task_module_option.radar.indicator = [
            //   { name: '广州华新园', max: 50 },
            //   { name: '合肥B3', max: 5 },
            //   { name: '合肥A2', max: 4 },
            //   { name: '上海嘉定', max: 3 },
            //   { name: '北京酒仙桥', max: 5 },
            //   { name: '北京鲁谷', max: 25 },
            //   { name: '北京大族', max: 80 },
            //   { name: '北京中信', max: 15 },
            //   { name: '香港将军澳', max: 10 },
            // ]
            useEcharts(taskModuleChart.value as HTMLDivElement).setOption(
              event_task_module_option
            )
          })
        })
      })
    }

    // onMounted(init)
    onMounted(echarts_init)
    onBeforeUnmount(() => {
      dispose(taskModuleChart.value as HTMLDivElement)
    })
    return {
      echarts_init,
      event_task_module_option,
      loading,
      taskModuleChart,
      // taskModuleChart,/
      updateChart
    }
  }
})
</script>

<style lang="scss" scoped>
.chart-item-container {
  width: 100%;
  .chart-item {
    height: 220px;
  }
}
</style>
