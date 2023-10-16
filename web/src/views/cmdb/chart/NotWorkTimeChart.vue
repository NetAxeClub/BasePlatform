<template>
  <n-card
      :content-style="{ padding: '10px' }"
      :header-style="{ padding: '10px' }"
      :segmented="true"
  >
    <template #header>
      <!--      <n-skeleton text style="width: 50%" v-if="loading" />-->
      <!--      <template v-else>-->
      <div class="text-sm"> 仅8:30-17:30暂未统计法定节假日</div>
      <!--      </template>-->
    </template>
    <div class="chart-item-container">
      <!--      <n-skeleton text v-if="loading" :repeat="4" />-->
      <!--      <template v-else>-->
      <div ref="not_work_time_Chart" class="chart-item"></div>
      <!--      </template>-->
    </div>
  </n-card>
</template>

<script lang="ts">
import useEcharts from '@/hooks/useEcharts'
import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { dispose, graphic } from 'echarts'
// import { cmdb_chart } from '@/api/url'
import { cmdb_chart } from '@/api/url'
import useGet from '@/hooks/useGet'

export default defineComponent({
  name: 'NotWorkTimeChart',
  setup() {
    const get = useGet()
    const loading = ref(true)
    const not_work_time_Chart = ref<HTMLDivElement | null>(null)
    const not_work_time_option = {
      grid: {
        left: '12%',
        right: '5%',
        top: '5%',
        bottom: '3%',
        containLabel: true,
      },
      tooltip: {
        trigger: 'item',
      },
      series: [
        {
          name: '登录时间比例',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 10,
            borderColor: '#fff',
            borderWidth: 2,
          },
          emphasis: {
            label: {
              show: true,
              fontSize: '16',
              fontWeight: 'bold',
            },
          },
          labelLine: {
            show: true,
            length: 5,
            length2: 5,
            smooth: true,
          },
          data: [
            // { value: 1969, name: '广州华新园' },
            // { value: 743, name: '合肥B3' },
            // { value: 1594, name: '合肥A2' },
            // { value: 1347, name: '上海嘉定' },
            // { value: 635, name: '北京酒仙桥' },
            // { value: 635, name: '北京大族' },
            // { value: 635, name: '北京中信' },
            // { value: 635, name: '香港将军澳' },
          ],
        },
      ],
    }

    const init = () => {
      // const option = {
      //   grid: {
      //     left: '2%',
      //     right: '5%',
      //     top: '5%',
      //     bottom: '3%',
      //     containLabel: true,
      //   },
      //   tooltip: {
      //     trigger: 'axis',
      //   },
      //   yAxis: {
      //     type: 'category',
      //     data: ['一月', '二月', '三月', '四月', '五月', '六月'],
      //     boundaryGap: 0,
      //     axisTick: {
      //       show: false,
      //     },
      //   },
      //   xAxis: {
      //     type: 'value',
      //     boundaryGap: 0,
      //   },
      //   series: [
      //     {
      //       data: [480, 289, 711, 618, 393, 571, 470],
      //       type: 'bar',
      //       smooth: true,
      //       showSymbol: false,
      //       barWidth: 'auto',
      //       itemStyle: {
      //         borderRadius: [0, 15, 15, 0],
      //         opacity: 0.8,
      //         color: new graphic.LinearGradient(1, 0, 0, 1, [
      //           {
      //             offset: 0,
      //             color: 'rgba(12, 124, 182)',
      //           },
      //           {
      //             offset: 1,
      //             color: 'rgba(244, 187, 236)',
      //           },
      //         ]),
      //       },
      //     },
      //   ],
      // }
      setTimeout(() => {
        loading.value = false
        nextTick(() => {
          useEcharts(not_work_time_Chart.value as HTMLDivElement).setOption(not_work_time_option)
        })
      }, 1000)
    }
    const updateChart = () => {
      useEcharts(not_work_time_Chart.value as HTMLDivElement).resize()
    }

    function echarts_init() {
      // nextTick(() => {
      useEcharts(not_work_time_Chart.value as HTMLDivElement).setOption(not_work_time_option)
      // })
      nextTick(() => {
        get({
          url: cmdb_chart,
          data: () => {
            return {
              cmdb_login_time: 1,
            }
          },
        }).then((res) => {
          // console.log('not_work_time', res)
          const item = res.data
          //.slice(-7)
          // res.data.forEach((item) => {
          // not_work_time_option.xAxis[0].data.push(item.admin_login_user_name)
          not_work_time_option.series[0].data.push({ value: item.work_time_count, name: '工作时间登录' })
          not_work_time_option.series[0].data.push({ value: item.not_work_time, name: '非工作时间登录' })
          // not_work_time_option.series[1].data.push(item.failtask)
          useEcharts(not_work_time_Chart.value as HTMLDivElement).setOption(not_work_time_option)
          // })
        })
      })
    }

    // onMounted(init)
    onMounted(echarts_init)
    onBeforeUnmount(() => {
      dispose(not_work_time_Chart.value as HTMLDivElement)
    })
    return {
      echarts_init,
      not_work_time_option,
      loading,
      updateChart,
      not_work_time_Chart,
    }
  },
})
</script>

<style lang="scss" scoped>
.chart-item-container {
  width: 100%;

  .chart-item {
    height: 180px;
  }
}
</style>
