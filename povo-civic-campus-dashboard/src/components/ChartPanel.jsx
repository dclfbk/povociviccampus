import ReactECharts from 'echarts-for-react';
import { groupBy, sum } from '../lib/data';

export default function ChartPanel({ features, activeIndicator, aggregate, onCategoryClick }) {
  const grouped = groupBy(features, 'profilo_pubblico');
  const rows = Object.entries(grouped).map(([name, items]) => ({
    name,
    value: aggregate === 'sezioni' ? items.length : sum(items, aggregate),
  })).sort((a,b)=>b.value-a.value);

  const option = {
    animationDuration: 350,
    grid: { left: 24, right: 24, top: 30, bottom: 20, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', splitLine: { lineStyle: { color: '#eceef3' } } },
    yAxis: { type: 'category', data: rows.map(r=>r.name), axisLabel: { width: 180, overflow: 'truncate' } },
    series: [{ type: 'bar', data: rows.map(r=>r.value), itemStyle: { borderRadius: [0,4,4,0] } }],
  };

  return <ReactECharts option={option} style={{ height: 300 }} onEvents={{ click: p => onCategoryClick?.(p.name) }} />;
}
