export async function loadJson(path) {
  const url = `${import.meta.env.BASE_URL}${path.replace(/^\.\//,'').replace(/^\//,'')}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Impossibile caricare ${url}`);
  return response.json();
}

export const indicators = {
  profilo_pubblico: { label: 'Profilo sociofunzionale', unit: '', kind: 'categorical' },
  popolazione_rif: { label: 'Abitanti (2023)', unit: '', kind: 'continuous' },
  famiglie_rif: { label: 'Famiglie (2023)', unit: '', kind: 'continuous' },
  abitazioni_rif: { label: 'Abitazioni (2023)', unit: '', kind: 'continuous' },
  densita_pop_rif: { label: 'Densità abitativa (2023)', unit: ' ab./km²', kind: 'continuous' },
  dislivello_sezione_m: { label: 'Dislivello', unit: ' m', kind: 'continuous' },
  servizi_5_min: { label: 'Servizi entro 5 minuti', unit: '', kind: 'continuous' },
  servizi_15_min: { label: 'Servizi entro 15 minuti', unit: '', kind: 'continuous' },
  tempo_fermata_min: { label: 'Tempo alla fermata', unit: ' min', kind: 'continuous', inverse: true },
  passaggi_totali: { label: 'Passaggi del TPL', unit: '', kind: 'continuous' },
  indice_sociofunzionale: { label: 'Indice sociofunzionale', unit: '', kind: 'continuous' },
};
export function number(value,digits=0){const n=Number(value);if(!Number.isFinite(n))return '–';return new Intl.NumberFormat('it-IT',{maximumFractionDigits:digits}).format(n)}
export function sum(features,field){return features.reduce((acc,f)=>acc+(Number(f.properties?.[field])||0),0)}
export function quantileBreaks(features,field,classes=5){const values=features.map(f=>Number(f.properties?.[field])).filter(Number.isFinite).sort((a,b)=>a-b);if(!values.length)return[0,1];const breaks=[];for(let i=0;i<=classes;i++){const idx=Math.min(values.length-1,Math.round((values.length-1)*i/classes));breaks.push(values[idx])}return[...new Set(breaks)]}
