import ReactECharts from 'echarts-for-react';

const COLORS = ['#1a0dab','#5f4bc7','#8b80df','#2b7a78','#d28537','#8d4b7b','#52606d','#ba4a4a'];

export default function DistributionChart({
  title,
  description,
  rows,
  selected = [],
  onToggle,
  valueLabel = 'servizi',
}) {
  const total = rows.reduce((sum, row) => sum + row.value, 0);
  const sorted = [...rows].sort((a,b)=>b.value-a.value || a.label.localeCompare(b.label, 'it'));
  const palette = Object.fromEntries(rows.map((r,i)=>[r.label, COLORS[i % COLORS.length]]));

  const stackedOption = {
    animationDuration: 250,
    grid: { left: 0, right: 0, top: 4, bottom: 24, containLabel: false },
    tooltip: {
      trigger: 'item',
      formatter: p => `${p.seriesName}<br><b>${p.value.toLocaleString('it-IT')} ${valueLabel}</b> · ${total ? (p.value/total*100).toFixed(1) : 0}%`,
    },
    xAxis: {
      type: 'value', max: total || 1, show: true,
      axisLabel: { formatter: value => total ? `${Math.round(value/total*100)}%` : '0%' },
      splitLine: { show: false }, axisLine: { show: false }, axisTick: { show: false },
    },
    yAxis: { type: 'category', data: ['Composizione'], show: false },
    series: rows.map(row => ({
      name: row.label,
      type: 'bar',
      stack: 'totale',
      data: [row.value],
      barWidth: 28,
      itemStyle: {
        color: palette[row.label],
        opacity: selected.length && !selected.includes(row.label) ? 0.25 : 1,
        borderColor: selected.includes(row.label) ? '#111827' : '#ffffff',
        borderWidth: selected.includes(row.label) ? 2 : 1,
      },
      emphasis: { focus: 'series' },
    })),
  };

  const barsOption = {
    animationDuration: 250,
    grid: { left: 8, right: 45, top: 8, bottom: 8, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name}<br><b>${p[0].value.toLocaleString('it-IT')} ${valueLabel}</b>` },
    xAxis: { type: 'value', minInterval: 1, axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: '#eceef3' } } },
    yAxis: { type: 'category', inverse: true, data: sorted.map(r=>r.label), axisLine: { show:false }, axisTick: { show:false }, axisLabel: { width: 190, overflow: 'break', lineHeight: 15, color: '#303543' } },
    series: [{
      type: 'bar',
      data: sorted.map(row => ({
        value: row.value,
        itemStyle: {
          color: palette[row.label],
          opacity: selected.length && !selected.includes(row.label) ? 0.22 : 0.92,
          borderColor: selected.includes(row.label) ? '#111827' : 'transparent',
          borderWidth: selected.includes(row.label) ? 2 : 0,
          borderRadius: [0,4,4,0],
        },
      })),
      barMaxWidth: 23,
      label: { show: true, position: 'right', color: '#191c2b', fontWeight: 700 },
    }],
  };

  const click = params => onToggle?.(params.seriesName || params.name);

  return <section className="chart-card">
    <div className="chart-heading">
      <h3>{title}</h3>
      <p>{description}</p>
    </div>
    <div className="percent-explainer">
      <b>Composizione percentuale</b>
      <span>La barra mostra il peso di ogni gruppo sul totale filtrato; le barre sotto riportano i valori assoluti.</span>
    </div>
    <ReactECharts option={stackedOption} style={{height:72}} onEvents={{click}} notMerge />
    <ReactECharts option={barsOption} style={{height:Math.max(210, sorted.length*43)}} onEvents={{click}} notMerge />
  </section>;
}
