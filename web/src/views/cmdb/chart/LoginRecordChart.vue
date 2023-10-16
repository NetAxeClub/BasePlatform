<template>
  <n-card
    :content-style="{ padding: '10px' }"
    :header-style="{ padding: '10px' }"
    :segmented="true"
  >
    <template #header>
      <!--      <n-skeleton text style="width: 50%" v-if="loading" />-->
      <!--      <template v-else>-->
      <div class="text-sm">登录用户排行榜TOP7</div>
      <!--      </template>-->
    </template>
    <div class="chart-item-container">
      <!--      <n-skeleton text v-if="loading" :repeat="4" />-->
      <!--      <template v-else>-->
      <div ref="login_record_Chart" class="chart-item"></div>
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
  name: 'LoginRecordChart',
  setup() {
    const get = useGet()
    const loading = ref(true)
    const login_record_Chart = ref<HTMLDivElement | null>(null)
    const login_record_option = {
      tooltip: {
        trigger: 'axis'
      },
      // legend: {
      //   data: ['Profit', 'Expenses', 'Income']
      // },
      grid: {
        left: '0%',
        right: '5%',
        top: '5%',
        bottom: '3%',
        containLabel: true
      },
      xAxis: [
        {
          type: 'category',
          // boundaryGap: false,
          splitLine: { show: true },
          axisLabel: {
            interval: 0,
            rotate: 40
          },
          data: []
        }
      ],
      yAxis: [
        {
          type: 'value',
          axisTick: {
            show: true
          }
        }
      ],
      series: [
        {
          name: '登录次数',
          type: 'bar', //柱状图
          stack: 'LoginRecord',
          emphasis: {
            //折线图的高亮状态。
            focus: 'series' //聚焦当前高亮的数据所在的系列的所有图形。
          },
          data: [],
          barWidth: 40,
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
        // {
        //   name: "FailTask",
        //   type: "bar",
        //   stack: "ConfigTrend",
        //   emphasis: {
        //     focus: "series",
        //   },
        //   data: [],
        //   barWidth : 20,
        //
        // },
      ]
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
          useEcharts(login_record_Chart.value as HTMLDivElement).setOption(
            login_record_option
          )
        })
      }, 1000)
    }
    const updateChart = () => {
      useEcharts(login_record_Chart.value as HTMLDivElement).resize()
    }

    function echarts_init() {
      // nextTick(() => {
      useEcharts(login_record_Chart.value as HTMLDivElement).setOption(
        login_record_option
      )
      // })
      nextTick(() => {
        get({
          url: cmdb_chart,
          data: () => {
            return {
              login_record: 1
            }
          }
        }).then((res) => {
          // console.log('login_record', res)
          //.slice(-7)
          res.data.forEach((item) => {
            login_record_option.xAxis[0].data.push(item.admin_login_user_name)
            login_record_option.series[0].data.push(item.sum_count)
            // login_record_option.series[1].data.push(item.failtask)
            useEcharts(login_record_Chart.value as HTMLDivElement).setOption(
              login_record_option
            )
          })
        })
      })
    }

    // onMounted(init)
    onMounted(echarts_init)
    onBeforeUnmount(() => {
      dispose(login_record_Chart.value as HTMLDivElement)
    })
    return {
      echarts_init,
      login_record_option,
      loading,
      updateChart,
      login_record_Chart
    }
  }
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
