<template>
  <n-card
      :content-style="{ padding: '10px' }"
      :header-style="{ padding: '10px' }"
      :segmented="true"
  >
    <template #header>
      <!--      <n-skeleton text style="width: 50%" v-if="loading" />-->
      <!--      <template v-else>-->
      <div class="text-sm">原子事件事件仅8:30-17:30计算为工作时间</div>
      <!--      </template>-->
    </template>
    <div class="chart-item-container">
      <!--      <n-skeleton text v-if="loading" :repeat="4" />-->
      <!--      <template v-else>-->
      <div ref="eventCommitTimeChart" class="chart-item"> </div>
      <!--      </template>-->
    </div>
  </n-card>
</template>

<script lang="ts">
import useEcharts from '@/hooks/useEcharts'
import { defineComponent, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { dispose } from 'echarts'
import { automation_chart } from '@/api/url'
import useGet from '@/hooks/useGet'
export default defineComponent({
  name: 'EventCommitTimeChart',
  setup() {
    const get = useGet()
    const event_commit_time_option = {
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
          name: '原子事件发生的时间分布',
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
    const loading = ref(true)
    const eventCommitTimeChart = ref<HTMLDivElement | null>(null)
    const init = () => {

      setTimeout(() => {
        loading.value = false
        nextTick(() => {
          useEcharts(eventCommitTimeChart.value as HTMLDivElement).setOption(event_commit_time_option)
        })
      }, 1000)
    }
    const updateChart = () => {
      useEcharts(eventCommitTimeChart.value as HTMLDivElement).resize()
    }
    function echarts_init() {
      // nextTick(() => {
      useEcharts(eventCommitTimeChart.value as HTMLDivElement).setOption(event_commit_time_option)
      // })
      nextTick(() => {
        get({
          url: automation_chart,
          data: () => {
            return {
              event_commit_time: 1,
            }
          },
        }).then((res) => {
          // console.log('event_commit_time_trend', res)
          const item = res.data
          // res.data.forEach((item)=>{
            // event_commit_time_option.xAxis.data.push(item.log_time)
            event_commit_time_option.series[0].data.push(
                { value:item.not_work_time,name:'非工作时间' },
                { value:item.work_time_count,name:'工作时间' },
                // { value:item.not_work_time,name:'非工作时间' },
            )
            useEcharts(eventCommitTimeChart.value as HTMLDivElement).setOption(event_commit_time_option)
          // })
        })
      })
    }

    // onMounted(init)
    onMounted(echarts_init)
    onBeforeUnmount(() => {
      dispose(eventCommitTimeChart.value as HTMLDivElement)
    })
    return {
      event_commit_time_option,
      echarts_init,
      loading,
      eventCommitTimeChart,
      updateChart,
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
