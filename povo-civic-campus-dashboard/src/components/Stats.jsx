import { mean, number, sum } from '../lib/data';

export default function Stats({ sections, services }) {
  const stats = [
    ['Abitanti', number(sum(sections,'popolazione_rif'))],
    ['Famiglie', number(sum(sections,'famiglie_rif'))],
    ['Sezioni', number(sections.length)],
    ['Servizi', number(services.length)],
    ['Indice civico medio', number(mean(services,'indice_civico_score'),1)],
  ];
  return <div className="stats-grid">{stats.map(([label,value])=><div className="stat" key={label}><strong>{value}</strong><span>{label}</span></div>)}</div>;
}
