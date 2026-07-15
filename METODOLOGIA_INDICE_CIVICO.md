# Indice civico dei servizi di Povo — versione 1.0

L’indice sintetizza tre attributi già calcolati nel dataset:

- **funzione relazionale**: peso 50%; Alta = 100, Media = 50, Bassa = 0;
- **utenza prevalente**: peso 30%; prevalentemente citizens = 100, entrambi = 70, prevalentemente city users/visitatori = 30;
- **natura del soggetto/servizio**: peso 20%; pubblico o comunitario = 100, misto/convenzionato = 70, privato/economico = 30.

Formula:

`indice_civico_score = 0,50 × funzione_relazionale + 0,30 × utenza + 0,20 × natura`

## Quattro categorie

- **80–100 — Presidio civico ad alta intensità**: forte capacità di generare relazione e valore comunitario.
- **65–79,9 — Servizio civico-relazionale**: servizio utile con una componente civica e relazionale significativa.
- **50–64,9 — Servizio di utilità territoriale**: contribuisce alla vita quotidiana del territorio, ma con minore intensità relazionale.
- **0–49,9 — Servizio prevalentemente funzionale/attrattivo**: orientato soprattutto alla funzione specifica, al consumo o all’attrazione di utenti esterni.

L’indice non misura la qualità assoluta del servizio e non sostituisce una valutazione locale. Per i nuovi record OSM e Overture la categoria va assegnata solo dopo avere compilato o stimato in modo verificabile i tre attributi di base.
