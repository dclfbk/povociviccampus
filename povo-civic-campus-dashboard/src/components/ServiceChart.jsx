import ReactECharts from 'echarts-for-react';

export default function ServiceChart({ services, field='categoria_indice_civico' }) {
  const counts = services.reduce((a,f)=>{ const k=f.properties?.[field] || 'Non classificato'; a[k]=(a[k]||0)+1; return a; },{});
  const data = Object.entries(counts).map(([name,value])=>({name,value})).sort((a,b)=>b.value-a.value);
  const option = {
    tooltip: { trigger:'item' },
    legend: { bottom: 0, type:'scroll' },
    series: [{ type:'pie', radius:['42%','68%'], center:['50%','42%'], label:{ show:false }, data }]
  };
  return <ReactECharts option={option} style={{height:300}} />;
}
