# Povo Civic Campus Dashboard

Dashboard React/Vite con:

- MapLibre GL JS e stile OpenFreeMap Liberty;
- ECharts;
- mappa delle 95 sezioni di censimento;
- indicatori demografici e sociofunzionali;
- selezione e aggregazione per profilo;
- servizi con indice civico;
- ingressi FBK, Povo 0, Povo 1 e Povo 2;
- interfaccia pronta per 12 isocrone pedonali (4 origini × 5/10/15 minuti).

## Avvio

```bash
npm install
npm run dev
```

## Build statico

```bash
npm run build
npm run preview
```

## Dati

I file sono in `public/data/`:

- `sezioni.geojson`
- `servizi.geojson`
- `confine.geojson`
- `campus.json`
- `isocrone.geojson`

`isocrone.geojson` è inizialmente vuoto. Le feature future devono avere almeno:

```json
{
  "origine": "fbk",
  "minuti": 5
}
```

con `origine` fra `fbk`, `povo0`, `povo1`, `povo2` e `minuti` fra 5, 10, 15.

## Nota

La grafica è ispirata a un linguaggio editoriale e di ricerca contemporaneo, senza loghi o marchi.
