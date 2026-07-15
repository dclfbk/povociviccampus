# Povo Civic Campus — Inventario dei dati e degli output

*Aggiornato al 15/07/2026 — catalogo operativo per tracciabilità, qualità e riuso*

## Quadro generale

| Indicatore | Valore | Nota |
| --- | --- | --- |
| Dataset/output censiti | 33 | Include fonti, intermedi e prodotti finali |
| File disponibili in questa sessione | 4 | File fisicamente presenti in /mnt/data |
| Prodotti finali | 10 | Output pronti o quasi pronti per pubblicazione |
| Elementi da verificare | 13 | Qualità, aggiornamento o completezza da controllare |
| Atti circoscrizionali censiti | 23 | Convocazioni e verbali 2025–2026 |

### Ambiti coperti

| Ambito | Copertura attuale | Principali output | Criticità nota |
| --- | --- | --- | --- |
| Servizi e POI | Alta | Mappatura servizi, 5 CSV tematici, categorie uMap, indice civico | Verifica periodica di aperture/chiusure |
| Demografia | Alta | Sezioni ISTAT, indicatori socio-demografici, cluster sociofunzionali | Allineamento temporale tra fonti |
| Mobilità | Media-alta | GTFS urbano/extraurbano, linee per sezione, fermate | Confermare versioni GTFS e linee attive |
| Accessibilità fisica | Media | Pendenze, isocrone, DTM/LiDAR, prossimità servizi | Pipeline ancora da consolidare |
| Partecipazione e percezione | In sviluppo | Mappa affettiva / luoghi caldi-freddi | Serve raccolta dati partecipativa strutturata |
| Atti e priorità civiche | Alta | Corpus convocazioni/verbali, temi e richieste territoriali | Mancano alcuni verbali 2026 e allegati deliberativi |

### Uso consigliato del catalogo

1. Usare “Inventario dati” come registro principale dei file e dei prodotti.
2. Aggiornare Stato disponibilità, Stato qualità e Data ultimo controllo a ogni modifica.
3. Compilare Script/pipeline e Dipendenze per rendere ogni output riproducibile.
4. Non pubblicare dati personali o contatti senza una revisione privacy.

## Inventario dati

| ID | Ambito | Tipo elemento | Nome file / output | Formato | Descrizione sintetica | Fonte primaria | Script / pipeline | CRS / riferimento | Disponibilità | Stato qualità | Data/versione | Uso previsto | Dipendenze | Prossima azione |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DAT-001 | Perimetro | Fonte | circoscrizione.geojson | GeoJSON | Confine della Circoscrizione di Povo | Comune di Trento / dato territoriale | — | Da confermare; destinazione WGS84 | Non disponibile qui | Verificato | Versione usata nel progetto | Filtro spaziale di tutte le analisi | — | Archiviare copia master con metadati |
| DAT-002 | Demografia | Fonte | R04_Trentino-Alto Adige_2023_sezioni.xlsx | XLSX | Dati ISTAT 2023 per sezioni di censimento | ISTAT | Importazione e selezione record | Codici sezione ISTAT | Non disponibile qui | Verificato | 2023 | Indicatori demografici e sociali | DAT-003 | Registrare campi effettivamente utilizzati |
| DAT-003 | Demografia | Fonte | sezioni_censimento.geojson | GeoJSON | Geometrie delle sezioni di censimento | ISTAT / Comune | Join spaziale e tabellare | CRS originale da verificare; output WGS84 | Non disponibile qui | Verificato | Versione progetto | Unità spaziale di analisi | DAT-002 | Conservare versione originale e trasformata |
| DAT-004 | Servizi | Fonte | Mappatura Servizi - Circoscrizione di Povo Luglio 2026.xlsx | XLSX | Questionario strutturato dei servizi; 40 risposte, 30 colonne | Circoscrizione di Povo / soggetti erogatori | Pulizia e normalizzazione | Indirizzi testuali; coordinate da geocodifica | Disponibile | In lavorazione | Luglio 2026 | Anagrafe servizi e base per mappe/indici | — | Completare controllo, geocodifica e versionamento |
| DAT-005 | Servizi | Intermedio | Form Responses 1 | Foglio XLSX | Foglio sorgente del questionario servizi | DAT-004 | Normalizzazione campi | — | Disponibile | In lavorazione | Luglio 2026 | Input per derivati tematici | DAT-004 | Mantenere immutato come raw data |
| DAT-006 | Servizi | Prodotto finale | commercio_e_servizi_di_prossimita.csv | CSV | Servizi commerciali e di prossimità | DAT-004 + verifiche | Script di separazione per map category | WGS84 se geocodificato | Non disponibile qui | Da verificare | Luglio 2026 | Layer uMap e analisi prossimità | DAT-004 | Rigenerare dalla versione master |
| DAT-007 | Servizi | Prodotto finale | cultura_socialita_e_spazi_comuni.csv | CSV | Cultura, socialità e spazi comuni | DAT-004 + verifiche | Script di separazione per map category | WGS84 se geocodificato | Non disponibile qui | Da verificare | Luglio 2026 | Layer uMap e analisi offerta civica | DAT-004 | Rigenerare dalla versione master |
| DAT-008 | Servizi | Prodotto finale | 5 CSV tematici della mappatura | CSV | Cinque file tematici ottenuti dal questionario | DAT-004 | Pipeline di pulizia e split | WGS84 se geocodificato | Non disponibile qui | Da verificare | Luglio 2026 | Pubblicazione e mappe tematiche | DAT-004 | Elencare i 5 nomi definitivi nel repository |
| DAT-009 | Servizi | Campo derivato | map category | Attributo | Categoria cartografica assegnata a ogni servizio | DAT-004 | Regole di riclassificazione | — | Non disponibile qui | Verificato | Luglio 2026 | Simbologia uMap/QGIS | DAT-004 | Documentare dizionario categorie |
| DAT-010 | Servizi | Campo derivato | indice_civico | Numero/classe | Indice composito citizens–city users e fruibilità civica | DAT-004 + classificazioni | Calcolo composito | — | Non disponibile qui | Da verificare | Luglio 2026 | Assegnazione a 4 classi | DAT-004,DAT-009 | Salvare formula e pesi nel foglio metodologia |
| DAT-011 | Servizi | Campo derivato | classe_indice_civico | Categoria | Quattro classi del profilo civico del punto di interesse | DAT-010 | Soglie del composito | — | Non disponibile qui | Da verificare | Luglio 2026 | Legenda e analisi tipologica | DAT-010 | Confermare nomi e soglie finali |
| DAT-012 | POI | Fonte | foursquare_povo.geojson | GeoJSON | Punti di interesse estratti da Foursquare | Foursquare | DuckDB / query spaziale | WGS84 | Non disponibile qui | Obsoleto | Estrazione 2026 su dati non aggiornati | Confronto e recall POI | DAT-001 | Non usare come fonte autorevole senza verifica |
| DAT-013 | POI | Intermedio | foursquare_povo_quality.geojson | GeoJSON | POI Foursquare con indicatori di qualità | Foursquare + controlli | Pipeline quality | WGS84 | Non disponibile qui | Da verificare | 2026 | Filtraggio e confronto | DAT-012 | Documentare criteri quality |
| DAT-014 | POI | Fonte | Overture Maps places | GeoParquet/GeoJSON | POI Overture, spesso derivati da pagine Facebook | Overture Maps Foundation | DuckDB spatial | WGS84 | Non disponibile qui | Critico | 2026 | Confronto con OSM e questionario | DAT-001 | Usare solo come segnalazione da validare |
| DAT-015 | POI | Fonte | OSM Overpass Povo | GeoJSON | Elementi OSM del territorio: servizi, strutture, luoghi | OpenStreetMap | Overpass QL / export GeoJSON | WGS84 | Non disponibile qui | In lavorazione | 2026 | Base geografica e controllo incrociato | DAT-001 | Salvare query e data estrazione |
| DAT-016 | Mobilità | Fonte | google_transit_urbano_tte.zip | GTFS ZIP | GTFS urbano Trentino Trasporti | Trentino Trasporti | Script GTFS 06–08 | WGS84 per stops/shapes | Non disponibile qui | Verificato | Versione progetto 2026 | Linee e fermate urbane | DAT-001,DAT-003 | Archiviare feed con data di validità |
| DAT-017 | Mobilità | Fonte | GTFS extraurbano | GTFS ZIP | Linee extraurbane con fermate nella circoscrizione | Trentino Trasporti | Script GTFS 06–08 | WGS84 | Non disponibile qui | Da verificare | 2026 | Integrare linee extraurbane nelle sezioni | DAT-001,DAT-003 | Registrare nome/versione feed |
| DAT-018 | Mobilità | Prodotto finale | linee_urbane_povo.geojson | GeoJSON | Linee urbane che attraversano o servono Povo | DAT-016 | Estrazione shapes/trips/stops | WGS84 | Non disponibile qui | Da verificare | 2026 | Layer cartografico mobilità | DAT-016 | Confermare elenco linee attive |
| DAT-019 | Mobilità | Prodotto finale | linee_extraurbane_povo.geojson | GeoJSON | Linee extraurbane con fermate nella circoscrizione | DAT-017 | Estrazione shapes/trips/stops | WGS84 | Non disponibile qui | Da verificare | 2026 | Layer cartografico mobilità | DAT-017 | Confermare elenco linee attive |
| DAT-020 | Analisi territoriale | Prodotto finale | sezioni_povo_cluster_sociofunzionali_v3.geojson | GeoJSON | Sezioni con indicatori sociofunzionali, cluster e linee di trasporto | DAT-002,003,004,016,017 | Script 06–08 + join spaziali | WGS84 | Non disponibile qui | In lavorazione | v3, luglio 2026 | Mappa coropletica/categorica finale | DAT-002,003,016,017 | Validare CRS e campi linee urbane/extraurbane |
| DAT-021 | Analisi territoriale | Campo derivato | cluster_sociofunzionale | Categoria | Cluster delle sezioni in base a profilo sociale e funzionale | DAT-020 | Clustering / regole definite negli script | — | Non disponibile qui | Da verificare | v3 | Lettura tipologica del territorio | DAT-020 | Documentare algoritmo, scaling e variabili |
| DAT-022 | Mobilità | Campo derivato | linee_urbane | Testo/elenco | Numeri delle linee urbane con almeno una fermata nella sezione | DAT-016,003 | Spatial join fermate-sezioni | — | Non disponibile qui | Da verificare | v3 | Informazione per sezione | DAT-016,DAT-003 | Controllare duplicati e ordinamento |
| DAT-023 | Mobilità | Campo derivato | linee_extraurbane | Testo/elenco | Numeri delle linee extraurbane con almeno una fermata nella sezione | DAT-017,003 | Spatial join fermate-sezioni | — | Non disponibile qui | Da verificare | v3 | Informazione per sezione | DAT-017,DAT-003 | Controllare duplicati e ordinamento |
| DAT-024 | Accessibilità | Fonte | LiDAR 2009 PAT DTM 1m | GeoTIFF | Modello digitale del terreno provinciale a 1 metro | Provincia autonoma di Trento / SIAT | Download massivo e mosaico | CRS PAT da verificare | Non disponibile qui | Storico | 2009 | Pendenza, dislivello, accessibilità | DAT-001 | Documentare limiti di aggiornamento |
| DAT-025 | Accessibilità | Prodotto intermedio | indice_tiles_lidar.shp | Shapefile | Poligoni di ingombro dei file TIFF LiDAR | DAT-024 | Script di indicizzazione raster | CRS dei TIFF | Non disponibile qui | Da verificare | 2026 | Selezione tile necessarie | DAT-024 | Salvare anche in GeoPackage |
| DAT-026 | Accessibilità | Prodotto finale | pendenza_povo | Raster/GeoJSON | Pendenza del terreno e indicatori per sezioni/percorsi | DAT-024 | Calcolo slope e zonal statistics | CRS metrico locale | Non disponibile qui | In sviluppo | 2026 | Accessibilità pedonale e ciclabile | DAT-024,DAT-003 | Definire classi di pendenza |
| DAT-027 | Accessibilità | Prodotto finale | isocrone_servizi_povo | GeoJSON | Aree raggiungibili a piedi/mezzi in tempi definiti | Rete OSM + servizi | Routing / isocrone | WGS84 | Non disponibile qui | In sviluppo | 2026 | Analisi prossimità e copertura | DAT-015,DAT-004 | Scegliere motore e profili di mobilità |
| DAT-028 | Partecipazione | Prodotto in sviluppo | mappa_affettiva_povo | GeoJSON/Survey | Luoghi percepiti come vitali, marginali, caldi o freddi | Raccolta partecipativa | Epicollect/Survey123/uMap da scegliere | WGS84 | Non disponibile qui | Da progettare | 2026 | Integrare dimensione emotiva del territorio | DAT-001 | Definire questionario, consenso e scala emotiva |
| DAT-029 | Atti pubblici | Corpus | convocazioni_consiglio_povo_2025_2026 | PDF | Convocazioni del Consiglio circoscrizionale | Comune di Trento | Raccolta documentale | — | Disponibile | Verificato | 2025–2026 | Analisi temi, priorità e cronologia | — | Mantenere indice per data e tipo |
| DAT-030 | Atti pubblici | Corpus | verbali_consiglio_povo_2025_2026 | PDF | Verbali delle sedute disponibili | Comune di Trento | Raccolta documentale | — | Disponibile | In lavorazione | 2025–2026 | Analisi decisioni, voti e richieste | — | Recuperare verbali mancanti e allegati |
| DAT-031 | Atti pubblici | Campo derivato | temi_delibere_e_verbali | Tabella/CSV | Temi territoriali estratti dagli atti | DAT-029,030 | Text mining / codifica manuale | — | Non disponibile qui | In sviluppo | 2026 | Confronto tra domanda istituzionale e dati | DAT-029,DAT-030 | Definire tassonomia temi |
| DAT-032 | Visualizzazione | Prodotto finale | uMap Povo Civic Campus | Mappa web | Mappa multilayer con servizi, mobilità, sezioni e indicatori | Output del progetto | Configurazione uMap | WGS84 | Non disponibile qui | In lavorazione | 2026 | Comunicazione pubblica | DAT-006:028 | Registrare URL, owner e data ultimo update |
| DAT-033 | Repository | Prodotto finale | povociviccampus | Git repository | Repository con script, dati, documentazione e mappe | Progetto | Git | — | Non disponibile qui | In lavorazione | 2026 | Riproducibilità e pubblicazione | Tutti | Definire struttura /data/raw /processed /outputs /docs |

## Atti circoscrizione

| ID | Data seduta | Anno | Tipo | Nome file | Disponibilità | Temi principali / note |
| --- | --- | --- | --- | --- | --- | --- |
| ATT-001 | 27/05/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-martedi-27-maggio-2025__01__convocazione-2bprot-2bn-2b185530-2bdd-2b19-05-2025.pdf | Disponibile | Insediamento, convalida eletti, presidente e vicepresidenza |
| ATT-002 | 27/05/2025 | 2025 | Verbale | seduta-consiglio-circoscrizionale-povo-di-martedi-27-maggio-2025__02__27-05-2025-verbale-2bn-2b5-povo.pdf | Disponibile | Insediamento del Consiglio 2025 |
| ATT-003 | 23/06/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-lunedi-23-giugno-2025__01__prot-2b241803-2bdd-2b17-06-2025-convocazione-2badunanza-2b23-06-2025.pdf | Disponibile | Priorità bilancio, commissioni, parchi, viabilità, Sprè |
| ATT-004 | 23/06/2025 | 2025 | Verbale | seduta-consiglio-circoscrizionale-povo-di-lunedi-23-giugno-2025__02__verbale-2bn-2b6-adunanza-2bdd-2b23-06-2025.pdf | Disponibile | Commissioni, Povo Insieme, priorità opere |
| ATT-005 | 04/08/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-lunedi-4-agosto-2025__01__prot-2b280461-2bdd-2b25-07-2025-convocazione-2badunanza-2b04-08-2025.pdf | Disponibile | Commissioni, Cimirlo, usi civici, attività diretta |
| ATT-006 | 04/08/2025 | 2025 | Verbale | seduta-consiglio-circoscrizionale-povo-di-lunedi-4-agosto-2025__02__verbale-2b7-25c2-25b0-2badunanza-2bdel-2bconsiglio-2bdi-2bpovo-04-08-2025.pdf | Disponibile | Costituzione commissioni e gruppi di lavoro |
| ATT-007 | 16/09/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-martedi-16-settembre-2025__01__convocazione-adunanza-16-09-2025.pdf | Disponibile | Protezione civile, viabilità, priorità bilancio |
| ATT-008 | 16/09/2025 | 2025 | Verbale | seduta-consiglio-circoscrizionale-povo-di-martedi-16-settembre-2025__02__16-09-2025-verbale-2bn-2b8-povo.pdf | Disponibile | Piano protezione civile e cartografie di rischio |
| ATT-009 | 16/10/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-giovedi-16-ottobre-2025__01__convocazione-adunanza-16-10-2025.pdf | Disponibile | Zona 30, CRM, gemellaggio, Povo Educa |
| ATT-010 | 16/10/2025 | 2025 | Integrazione convocazione | seduta-consiglio-circoscrizionale-povo-di-giovedi-16-ottobre-2025__02__prot-2b358226-2bdd-2b10-10-2025-integrazione-convocazione-2badunanza-2b16-10-2025.pdf | Disponibile | Comitato gestione scuola infanzia |
| ATT-011 | 19/11/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-mercoledi-19-novembre-2025__01__prot-2b399763-2bdd-2b13-11-2025-convocazione-2badunanza-2b19-11-2025.pdf | Disponibile | Bookcrossing, rete interaziendale, linea 13 |
| ATT-012 | 16/12/2025 | 2025 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-martedi-16-dicembre-2025__01__prot-2b456128-2bdd-2b09-12-2025-convocazione-2badunanza-2b16-12-2025.pdf | Disponibile | DUP, controllo vicinato, Povo Educa |
| ATT-013 | 16/12/2025 | 2025 | Verbale | seduta-consiglio-circoscrizionale-povo-di-martedi-16-dicembre-2025__02__verbale-2bseduta-2b16-12.pdf | Disponibile | Bilancio, opere, trasporto intermodale, Marzola |
| ATT-014 | 28/01/2026 | 2026 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-mercoledi-28-gennaio-2026__01__prot-2bn-2b20870-2bdd-2b22-01-2026-convocazione-2badunanza-2b28-01-2026.pdf | Disponibile | Risorse, contributi, Marzola, torrette, videosorveglianza |
| ATT-015 | 28/01/2026 | 2026 | Verbale | seduta-consiglio-circoscrizionale-povo-di-mercoledi-28-gennaio-2026__02__28-01-2026-verbale-2bpovo.pdf | Disponibile | Budget 2026, contributi, attività e beni comuni |
| ATT-016 | 23/02/2026 | 2026 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-lunedi-23-febbraio-2026__01__convocazione-adunanza-23-02-2026.pdf | Disponibile | Gemellaggio, sicurezza Sprè, pensiline bus |
| ATT-017 | 23/02/2026 | 2026 | Verbale | seduta-consiglio-circoscrizionale-povo-di-lunedi-23-febbraio-2026__02__23-02-2026-verbale-2bn-2b2-povo.pdf | Disponibile | Pro Loco, procedure deliberative, gemellaggio |
| ATT-018 | 26/03/2026 | 2026 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-giovedi-26-marzo-2026__01__prot-2b87454-2bdd-2b19-03-2026-povo-convocazione-2badunanza-2b26-03-2026.pdf | Disponibile | Animatore di comunità, innovazione circoscrizioni |
| ATT-019 | 26/03/2026 | 2026 | Verbale | seduta-consiglio-circoscrizionale-povo-di-giovedi-26-marzo-2026__02__verbale.pdf | Disponibile | Mappatura territoriale e mappa affettiva |
| ATT-020 | 28/04/2026 | 2026 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-martedi-28-aprile-2026__01__prot-2b122511-2bdd-2b22-04-2026-convocazione-2badunanza-2b28-04-2026.pdf | Disponibile | Parco Oltrecastello, biodiversità urbana |
| ATT-021 | 28/04/2026 | 2026 | Verbale | seduta-consiglio-circoscrizionale-povo-di-martedi-28-aprile-2026__02__28-04-2026-verbale-2bn-2b4-povo.pdf | Disponibile | Attività dirette e miglioramenti parco |
| ATT-022 | 20/05/2026 | 2026 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-mercoledi-20-maggio-2026__01__prot-2b215892-2bdd-2b14-05-2026-convocazione-2bconsiglio-2bpovo.pdf | Disponibile | PRG, illuminazione, innovazione circoscrizioni |
| ATT-023 | 16/06/2026 | 2026 | Convocazione | seduta-consiglio-circoscrizionale-povo-di-martedi-16-giugno-2026__01__prot-2b244597-2bdd-2b10-06-2026-convocazione-2badunanza-2b16-06-2026.pdf | Disponibile | Operatore ecologico, priorità bilancio, illuminazione |

## Metodologia e regole

*Metodologia, convenzioni e regole di qualità*

| Tema | Regola attuale | Applicazione | Rischio | Evidenza da conservare | Stato |
| --- | --- | --- | --- | --- | --- |
| Raw vs processed | I dati sorgente non vanno sovrascritti | Cartelle /data/raw e /data/processed | Perdita di tracciabilità | Hash, data download, fonte | Da applicare |
| CRS | Conservare CRS originale; pubblicare GeoJSON in EPSG:4326 | Tutti gli output web | Disallineamenti e geometrie errate | EPSG e comando di trasformazione | Da consolidare |
| Geocodifica | Conservare indirizzo originale e coordinate con metodo/confidenza | Mappatura servizi | Coordinate non verificabili | Provider, data, score e revisione manuale | Da applicare |
| POI esterni | OSM/Foursquare/Overture sono fonti di supporto, non verità assoluta | Controllo e arricchimento | Attività chiuse o duplicati | Fonte e data ultimo controllo | Applicata parzialmente |
| Indice civico | Formula, pesi e soglie devono essere versionati | Classificazione in 4 classi | Risultato non riproducibile | Foglio formula + test casi limite | Da documentare |
| Cluster sezioni | Salvare variabili, scaling, algoritmo e random seed | cluster sociofunzionali | Cluster instabili o non interpretabili | Script e tabella variabili | Da documentare |
| GTFS | Conservare feed originale e periodo di validità | Linee urbane/extraurbane | Linee non più attive | feed_info, calendar, data estrazione | Da applicare |
| Privacy | Separare dati di contatto dalla versione pubblica | Questionario servizi e raccolta affettiva | Esposizione dati personali | Versione pubblica anonimizzata | Necessaria |
| Aggiornamento | Ogni dataset deve avere data ultimo controllo e responsabile | Catalogo e repository | Dati obsoleti | Registro revisioni | Da applicare |

## Gap e priorità

| Priorità | Azione | Motivazione | Output atteso | Dipendenze | Responsabile | Stato |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Congelare una versione master della mappatura servizi | È il dataset più ricco e più recente | XLSX raw + CSV pulito + changelog | DAT-004 | Da assegnare | Da fare |
| 2 | Ricostruire e versionare i 5 CSV tematici | I file sono stati prodotti ma non sono disponibili in questa sessione | 5 CSV con nomi definitivi | DAT-004 | Da assegnare | Da fare |
| 3 | Documentare formula dell’indice civico e quattro classi | È essenziale per interpretabilità e riuso | Scheda metodologica + test | DAT-010,011 | Da assegnare | Da fare |
| 4 | Validare il GeoJSON v3 e il CRS | È il principale output integrato | sezioni_povo_cluster_sociofunzionali_v3 validato | DAT-020 | Da assegnare | Da fare |
| 5 | Salvare feed GTFS urbano ed extraurbano con data di validità | Le linee cambiano nel tempo | Archivio feed + metadata | DAT-016,017 | Da assegnare | Da fare |
| 6 | Creare dizionario dei campi | Molti attributi derivati non sono autoesplicativi | data_dictionary.csv | Tutti | Da assegnare | Da fare |
| 7 | Definire protocollo per la mappa affettiva | Serve coerenza metodologica e privacy | Questionario + schema GeoJSON + consenso | DAT-028 | Da assegnare | Da fare |
| 8 | Completare corpus verbali e allegati | Mancano alcune sedute e documenti deliberativi | Archivio documentale completo | DAT-029,030 | Da assegnare | In corso |

---

Fonte: conversione del file `Inventario_dati_Povo_Civic_Campus_2026.xlsx`, aggiornato al 15 luglio 2026.
