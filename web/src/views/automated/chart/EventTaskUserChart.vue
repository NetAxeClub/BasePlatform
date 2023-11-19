<template>
  <n-card
      :content-style="{ padding: '10px' }"
      :header-style="{ padding: '10px' }"
      :segmented="true"
  >
    <template #header>
      <!--      <n-skeleton text style="width: 50%" v-if="loading" />-->
      <!--      <template v-else>-->
      <div class="text-sm">用户使用事件数量</div>
      <!--      </template>-->
    </template>
    <div class="chart-item-container">
      <!--      <n-skeleton text v-if="loading" :repeat="4" />-->
      <!--      <template v-else>-->
      <div ref="eventTaskUserChart" class="chart-item"></div>
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
  name: 'EventTaskUserChart',
  setup() {
    const loading = ref(true)
    // const eventTaskUserChart = ref<HTMLDivElement | null>(null)
    const eventTaskUserChart = ref<HTMLDivElement | null>(null)
    const get = useGet()
    const event_task_user_option = {
      tooltip: {
        trigger: 'axis',
      },
      // legend: {
      //   data: ['Profit', 'Expenses', 'Income']
      // },
      grid: {
        left: '0%',
        right: '5%',
        top: '5%',
        bottom: '3%',
        containLabel: true,
      },
      xAxis: [
        {
          type: 'category',
          // boundaryGap: false,
          splitLine: { show: true },
          axisLabel: {
            interval: 0,
            rotate: 40,
          },
          data: [],
        },
      ],
      yAxis: [
        {
          type: 'value',
          axisTick: {
            show: true,
          },


        },
      ],
      series: [
        {
          name: '用户使用事件数量',
          type: 'bar',//柱状图
          stack: 'Category',
          emphasis: {//折线图的高亮状态。
            focus: 'series',//聚焦当前高亮的数据所在的系列的所有图形。
          },
          data: [],
          barWidth: 20,
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
                '#ff7da1',
              ]
              return colorList[params.dataIndex % colorList.length]
            },
          },
        },

      ],
    }
    const init = () => {

      setTimeout(() => {
        loading.value = false
        nextTick(() => {
          const echartInstance = useEcharts(eventTaskUserChart.value as HTMLDivElement)
          echartInstance.setOption(event_task_user_option)
        })
      }, 1000)
    }
    const updateChart = () => {
      useEcharts(eventTaskUserChart.value as HTMLDivElement).resize()
    }

    function echarts_init() {
      // nextTick(() => {
      useEcharts(eventTaskUserChart.value as HTMLDivElement).setOption(event_task_user_option)
      // })
      nextTick(() => {
        get({
          url: automation_chart,
          data: () => {
            return {
              event_task_user: 1,
            }
          },
        }).then((res) => {
          // console.log('event_task_user_res', res)
          // 去掉第一位取值为空的
          res.data.slice(1, 10).forEach((item) => {
            event_task_user_option.xAxis[0].data.push(item.commit_user)
            // event_task_user_option.radar.indicator.push({
            //   name:item['idc__name'],max:1000
            // })
            event_task_user_option.series[0].data.push(item['sum_count'])
            // event_task_user_option.radar.indicator = [
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
            useEcharts(eventTaskUserChart.value as HTMLDivElement).setOption(event_task_user_option)
          })
        })
      })
    }

    // onMounted(init)
    onMounted(echarts_init)
    onBeforeUnmount(() => {
      dispose(eventTaskUserChart.value as HTMLDivElement)
    })
    return {
      echarts_init,
      event_task_user_option,
      loading,
      eventTaskUserChart,
      // eventTaskUserChart,/
      updateChart,
    }
  },
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
