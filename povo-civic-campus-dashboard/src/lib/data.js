export async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`Impossibile caricare ${path}`);
  return response.json();
}

export const indicators = {
  popolazione_rif: { label: 'Abitanti', unit: '', kind: 'continuous' },
  famiglie_rif: { label: 'Famiglie', unit: '', kind: 'continuous' },
  abitazioni_rif: { label: 'Abitazioni', unit: '', kind: 'continuous' },
  densita_pop_rif: { label: 'Densità abitativa', unit: ' ab./km²', kind: 'continuous' },
  dislivello_sezione_m: { label: 'Dislivello', unit: ' m', kind: 'continuous' },
  servizi_5_min: { label: 'Servizi entro 5 minuti', unit: '', kind: 'continuous' },
  servizi_15_min: { label: 'Servizi entro 15 minuti', unit: '', kind: 'continuous' },
  tempo_fermata_min: { label: 'Tempo alla fermata', unit: ' min', kind: 'continuous', inverse: true },
  passaggi_totali: { label: 'Passaggi del TPL', unit: '', kind: 'continuous' },
  indice_sociofunzionale: { label: 'Indice sociofunzionale', unit: '', kind: 'continuous' },
  profilo_pubblico: { label: 'Profilo sociofunzionale', unit: '', kind: 'categorical' },
};

export function number(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '–';
  return new Intl.NumberFormat('it-IT', { maximumFractionDigits: digits }).format(n);
}

export function sum(features, field) {
  return features.reduce((acc, f) => acc + (Number(f.properties?.[field]) || 0), 0);
}

export function mean(features, field) {
  const values = features.map(f => Number(f.properties?.[field])).filter(Number.isFinite);
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
}

export function groupBy(features, field) {
  return features.reduce((acc, feature) => {
    const key = feature.properties?.[field] ?? 'Non classificato';
    (acc[key] ||= []).push(feature);
    return acc;
  }, {});
}

export function quantileBreaks(features, field, classes = 5) {
  const values = features.map(f => Number(f.properties?.[field])).filter(Number.isFinite).sort((a,b)=>a-b);
  if (!values.length) return [0,1];
  const breaks = [];
  for (let i=0; i<=classes; i++) {
    const idx = Math.min(values.length-1, Math.round((values.length-1)*i/classes));
    breaks.push(values[idx]);
  }
  return [...new Set(breaks)];
}
