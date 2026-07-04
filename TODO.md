# Povo Civic Campus — Piano di lavoro

Questo documento descrive le principali azioni di analisi previste dal progetto **Povo Civic Campus**.

Ogni azione è strutturata secondo lo stesso schema:

- descrizione;
- dati necessari;
- metodologia;
- output attesi.

L’obiettivo generale è costruire una lettura spaziale, civica e progettuale della circoscrizione di Povo, con particolare attenzione alla relazione tra comunità locale, FBK, Università, servizi, spazi pubblici e percorsi.

---

## 1. Definire il perimetro territoriale di Povo

### Descrizione

Questa azione serve a definire con precisione l’area di studio.

Povo non deve essere considerata in modo generico o approssimativo, ma attraverso il confine ufficiale della circoscrizione. Il perimetro è necessario per ritagliare tutti gli altri dati: servizi, rete stradale, percorsi pedonali, dati demografici, spazi verdi, documenti istituzionali e luoghi di interesse.

L’obiettivo è costruire una base geografica comune su cui sviluppare tutte le analisi successive.

### Dati necessari

- Confine ufficiale della Circoscrizione di Povo.
- Eventuali sotto-aree o località interne: Povo centro, Oltrecastello, Sprè, Gabbiolo, Panté, ecc.
- Base cartografica comunale.
- Ortofoto o cartografia di riferimento.
- OpenStreetMap come base di confronto.

### Metodologia

1. Recuperare il confine ufficiale della circoscrizione dal Comune di Trento.
2. Importare il confine in QGIS o in ambiente Python/GIS.
3. Verificare la coerenza geometrica del perimetro.
4. Usare il confine come area di ritaglio per tutti gli altri dataset.
5. Eventualmente individuare e mappare le località interne alla circoscrizione.

### Output attesi

- Layer geografico del confine di Povo.
- Mappa base della circoscrizione.
- Dataset di riferimento per il ritaglio spaziale.
- Prima descrizione territoriale dell’area di studio.

---

## 2. Costruire l’inventario dei servizi e degli spazi

### Descrizione

Questa azione serve a costruire un inventario georeferenziato dei servizi, degli spazi pubblici e dei luoghi di interesse presenti a Povo.

Il punto di partenza è il file della mappatura dei servizi della circoscrizione, da integrare con OpenStreetMap e con i dataset del Comune di Trento.

L’obiettivo non è solo elencare i servizi, ma capire dove si trovano, a quale categoria appartengono, quali popolazioni servono e quale potenziale hanno come luoghi di relazione.

### Dati necessari

- File della mappatura servizi della Circoscrizione di Povo.
- OpenStreetMap / Overpass API.
- Dataset del Comune di Trento.
- Indirizzi e coordinate dei servizi.
- Eventuali informazioni su orari, accessibilità, target, modalità di accesso.
- Informazioni su sale pubbliche, biblioteca, centro civico, casa sociale, spazi culturali e aree verdi.

### Metodologia

1. Pulire il file dei servizi.
2. Normalizzare nomi, indirizzi, categorie e descrizioni.
3. Geocodificare gli indirizzi.
4. Estrarre da OpenStreetMap i punti di interesse presenti nella circoscrizione.
5. Integrare i dataset comunali rilevanti.
6. Confrontare le fonti:
   - servizi presenti nel file ma assenti in OSM;
   - servizi presenti in OSM ma assenti nel file;
   - servizi presenti in entrambe le fonti;
   - servizi con informazioni incomplete.
7. Riclassificare i luoghi in categorie funzionali.

### Output attesi

- Dataset geocodificato dei servizi.
- Mappa dei servizi e degli spazi.
- Tabella di confronto tra file locale, Comune e OpenStreetMap.
- Classificazione dei luoghi per funzione.
- Elenco dei dati mancanti o da verificare.

---

## 3. Analizzare le centralità locali

### Descrizione

Questa azione serve a individuare i luoghi che strutturano la vita quotidiana e civica di Povo.

Non tutti i servizi hanno lo stesso peso. Alcuni luoghi funzionano come nodi territoriali perché concentrano attività, servizi, incontri, passaggi o valore simbolico.

L’obiettivo è identificare le centralità locali e capire come si relazionano tra loro e con FBK/Università.

### Dati necessari

- Dataset dei servizi geocodificati.
- Localizzazione di piazze, centro civico, biblioteca, casa sociale, parchi, scuole, mercato.
- OpenStreetMap.
- Dataset comunali.
- Eventi e comunicazioni della circoscrizione.
- Sedute del consiglio circoscrizionale.
- Eventuali dati su fermate bus e percorsi.

### Metodologia

1. Identificare i luoghi con maggiore concentrazione di servizi.
2. Individuare i luoghi più ricorrenti nelle comunicazioni pubbliche della circoscrizione.
3. Analizzare quali luoghi compaiono nei documenti del consiglio circoscrizionale.
4. Classificare le centralità per funzione:
   - civica;
   - commerciale;
   - culturale;
   - educativa;
   - sociale;
   - paesaggistica;
   - scientifico-universitaria.
5. Mappare le relazioni tra centralità.

### Output attesi

- Mappa delle centralità locali.
- Schede sintetiche dei principali nodi.
- Classificazione delle centralità.
- Prima lettura della struttura territoriale di Povo.

---

## 4. Mappare FBK e Università come attrattori territoriali

### Descrizione

Questa azione serve a leggere FBK e Università non solo come edifici, ma come generatori di flussi quotidiani.

La presenza di lavoratori, studenti, ricercatori, dottorandi, visiting researcher e ospiti internazionali modifica il funzionamento del territorio. Queste persone producono domanda di mobilità, ristorazione, servizi, spazi di incontro, luoghi di studio, eventi e occasioni di relazione.

L’obiettivo è capire come questi flussi si collocano nello spazio di Povo e quanto interagiscono con i servizi e gli spazi della circoscrizione.

### Dati necessari

- Localizzazione delle sedi FBK.
- Localizzazione delle sedi universitarie.
- Stime sul numero di persone presenti quotidianamente.
- Informazioni su orari di ingresso/uscita.
- Eventi pubblici o semi-pubblici.
- Fermate bus.
- Parcheggi.
- Percorsi pedonali.
- Servizi vicini.
- Ristorazione e bar.

### Metodologia

1. Mappare le sedi FBK e universitarie.
2. Identificarle come attrattori principali.
3. Raccogliere o stimare i flussi quotidiani.
4. Individuare le fasce orarie più rilevanti:
   - mattina;
   - pausa pranzo;
   - pomeriggio;
   - sera;
   - eventi.
5. Analizzare quali servizi si trovano in prossimità degli attrattori.
6. Costruire una matrice tra popolazioni temporanee e bisogni.

### Output attesi

- Mappa degli attrattori FBK/Università.
- Profilo delle popolazioni temporanee.
- Matrice popolazioni / bisogni.
- Prima analisi della domanda potenziale di servizi.
- Individuazione dei luoghi più rilevanti per i city users.

---

## 5. Analizzare la prossimità tra FBK, Università e servizi

### Descrizione

Questa azione serve a capire quali servizi e spazi di Povo siano effettivamente raggiungibili da FBK e Università.

La prossimità non va misurata solo in linea d’aria. È necessario considerare la rete reale dei percorsi, i tempi a piedi e, nel caso di Povo, anche la pendenza.

L’obiettivo è distinguere tra luoghi semplicemente vicini e luoghi realmente accessibili.

### Dati necessari

- Posizione di FBK.
- Posizione delle sedi universitarie.
- Dataset geocodificato dei servizi.
- Rete pedonale OpenStreetMap.
- Stradario comunale.
- Dati altimetrici.
- Fermate bus.
- Eventuali informazioni su marciapiedi, scalinate, attraversamenti.

### Metodologia

1. Calcolare la distanza lineare tra FBK/Università e i servizi.
2. Calcolare la distanza su rete pedonale.
3. Calcolare i tempi medi a piedi.
4. Integrare la pendenza per correggere i tempi.
5. Classificare i servizi in fasce:
   - 0–5 minuti;
   - 5–10 minuti;
   - 10–15 minuti;
   - 15–20 minuti;
   - oltre 20 minuti.
6. Confrontare accessibilità teorica e accessibilità reale.

### Output attesi

- Tabella servizi / distanza / tempo da FBK.
- Mappa delle prossimità.
- Isocrone standard.
- Isocrone corrette per pendenza.
- Classificazione dei servizi realmente accessibili.

---

## 6. Analizzare l’accessibilità morfologica

### Descrizione

Questa azione è centrale per Povo.

La circoscrizione è in salita e la morfologia collinare condiziona fortemente gli spostamenti. Un luogo vicino in metri può essere poco accessibile se richiede un percorso ripido, poco leggibile o poco confortevole.

L’obiettivo è costruire una lettura dell’accessibilità che tenga conto di pendenza, dislivello, scalinate e continuità dei percorsi.

### Dati necessari

- DEM/DTM oppure isolinee.
- Rete pedonale OpenStreetMap.
- Stradario comunale.
- Scalinate.
- Percorsi pedonali.
- Attraversamenti.
- Fermate bus.
- Eventuali dati su illuminazione, marciapiedi, superficie, sicurezza.

### Metodologia

1. Importare DEM/DTM o curve di livello.
2. Calcolare la pendenza del territorio.
3. Campionare quota e pendenza lungo la rete pedonale.
4. Attribuire un costo a ogni segmento della rete.
5. Calcolare percorsi e tempi pesati per dislivello.
6. Distinguere i percorsi in salita da quelli in discesa.
7. Individuare i principali punti di attrito spaziale.

### Output attesi

- Mappa delle pendenze.
- Rete pedonale pesata per dislivello.
- Mappa degli attriti spaziali.
- Isocrone morfologiche.
- Elenco dei percorsi critici.
- Confronto tra accessibilità geometrica e accessibilità effettiva.

---

## 7. Analizzare i percorsi tra FBK e Povo

### Descrizione

Questa azione serve a individuare i percorsi che possono diventare assi di relazione tra il polo scientifico-universitario e la comunità locale.

Non interessa solo sapere se un luogo è raggiungibile, ma anche come lo si raggiunge. Il percorso stesso può diventare uno spazio di relazione, orientamento, racconto e attivazione civica.

L’obiettivo è analizzare i collegamenti principali tra FBK, Università e i nodi civici di Povo.

### Dati necessari

- Rete pedonale.
- Rete stradale.
- Pendenze.
- Fermate bus.
- Attraversamenti.
- Marciapiedi.
- Servizi lungo i percorsi.
- Punti di interesse.
- Spazi pubblici intermedi.
- Fotografie o rilievi sul campo.

### Metodologia

1. Identificare i percorsi principali:
   - FBK → Piazza Manci;
   - FBK → Biblioteca;
   - FBK → Casa sociale;
   - FBK → Centro civico;
   - FBK → ristorazione/bar;
   - Università → centro di Povo.
2. Calcolare lunghezza, tempo e dislivello.
3. Individuare servizi e spazi lungo i percorsi.
4. Valutare leggibilità, sicurezza e comfort.
5. Identificare punti di sosta e micro-spazi.
6. Proporre eventuali percorsi narrativi o segnaletica.

### Output attesi

- Mappa dei percorsi principali.
- Schede percorso.
- Elenco di punti critici.
- Elenco di punti di interesse lungo i percorsi.
- Proposta di asse pedonale narrativo FBK–Povo.

---

## 8. Analizzare la mobilità e il trasporto pubblico

### Descrizione

Questa azione serve a capire come Povo è raggiunta e attraversata dai flussi di mobilità.

La relazione tra FBK, Università e circoscrizione dipende anche da bus, parcheggi, fermate, percorsi pedonali di accesso e collegamenti con Trento città.

L’obiettivo è capire come le persone arrivano a Povo, dove si concentrano i flussi e quali punti possono diventare nodi di interscambio o di relazione.

### Dati necessari

- Fermate bus.
- Linee del trasporto pubblico.
- Orari, se disponibili.
- Parcheggi.
- Stalli bici.
- Colonnine di ricarica.
- Rete pedonale.
- Rete ciclabile.
- Mobility manager d’area.
- Dati comunali sulla mobilità.
- OpenStreetMap.

### Metodologia

1. Mappare fermate bus e linee.
2. Identificare le fermate più rilevanti per FBK, Università e centro di Povo.
3. Mappare parcheggi e infrastrutture per biciclette.
4. Analizzare connessioni tra fermate e servizi.
5. Valutare accessibilità a piedi dalle fermate.
6. Collegare il tema della mobilità ai documenti del consiglio circoscrizionale.

### Output attesi

- Mappa della mobilità.
- Mappa fermate / servizi / attrattori.
- Analisi dei nodi di accesso.
- Elenco criticità.
- Indicazioni per migliorare la connessione tra trasporto pubblico, FBK e spazi civici.

---

## 9. Analizzare la popolazione residente

### Descrizione

Questa azione serve a capire chi vive a Povo e come la popolazione è distribuita nello spazio.

La relazione con FBK e Università deve essere costruita senza perdere di vista la comunità residente. Per questo è importante analizzare struttura demografica, densità, distribuzione per età e prossimità ai servizi.

L’obiettivo è confrontare la Povo dei residenti con la Povo dei city users.

### Dati necessari

- Dati ISTAT.
- Sezioni di censimento.
- Popolazione residente.
- Età.
- Famiglie.
- Indicatori demografici disponibili.
- Confine della circoscrizione.
- Servizi geocodificati.
- Spazi civici.
- Fermate bus.

### Metodologia

1. Scaricare o recuperare le sezioni di censimento.
2. Ritagliare le sezioni sulla circoscrizione di Povo.
3. Calcolare indicatori demografici.
4. Mappare densità e distribuzione della popolazione.
5. Analizzare la distanza dai servizi principali.
6. Confrontare distribuzione dei residenti e localizzazione degli attrattori FBK/Università.

### Output attesi

- Mappa demografica.
- Profilo della popolazione residente.
- Indicatori per sezione di censimento.
- Confronto residenti / city users.
- Individuazione di aree più o meno servite.

---

## 10. Analizzare la vita civica e gli eventi

### Descrizione

Questa azione serve a capire quali luoghi sono effettivamente usati dalla comunità.

La mappa dei servizi dice cosa esiste, ma non sempre dice cosa è vivo, attivato, frequentato o riconosciuto. I canali social e le comunicazioni della circoscrizione aiutano a osservare eventi, iniziative, temi ricorrenti e spazi utilizzati.

L’obiettivo è distinguere tra spazi semplicemente presenti e spazi realmente attivati.

### Dati necessari

- Pagina Instagram della circoscrizione.
- Pagina Facebook della circoscrizione.
- Sito del Comune.
- Locandine.
- Calendari eventi.
- Comunicazioni pubbliche.
- Luoghi citati negli eventi.
- Associazioni coinvolte.
- Target dichiarati.

### Metodologia

1. Raccogliere post, immagini, locandine e comunicazioni.
2. Estrarre:
   - titolo evento;
   - data;
   - luogo;
   - tema;
   - target;
   - associazioni coinvolte.
3. Geocodificare i luoghi degli eventi.
4. Classificare gli eventi per tema.
5. Mappare gli spazi più attivati.
6. Valutare possibili connessioni con FBK e Università.

### Output attesi

- Dataset degli eventi.
- Mappa degli spazi attivati.
- Classificazione tematica.
- Matrice evento / luogo / target.
- Elenco di possibili collaborazioni FBK–Povo.

---

## 11. Analizzare le sedute del Consiglio circoscrizionale

### Descrizione

Questa azione serve a ricostruire l’agenda politica e amministrativa della circoscrizione.

Le sedute del Consiglio circoscrizionale e delle commissioni permettono di capire quali temi sono discussi formalmente, quali luoghi vengono citati, quali problemi emergono e quali decisioni vengono prese.

L’obiettivo è collegare la mappa fisica del territorio con l’agenda civica e istituzionale.

### Dati necessari

- Pagine delle sedute del Consiglio circoscrizionale.
- Convocazioni.
- Ordini del giorno.
- Verbali.
- Delibere.
- Allegati pubblici.
- Eventuali documenti dell’Albo pretorio.
- Testi relativi alle commissioni.
- Metadata: data, tipo seduta, luogo, oggetto.

### Metodologia

1. Scaricare le pagine e i documenti pubblici.
2. Costruire un corpus testuale.
3. Estrarre:
   - temi;
   - luoghi;
   - soggetti;
   - decisioni;
   - problemi;
   - richieste al Comune.
4. Cercare riferimenti a:
   - FBK;
   - Fondazione Bruno Kessler;
   - Università;
   - studenti;
   - Via Sommarive;
   - mobilità;
   - sicurezza;
   - verde;
   - spazi pubblici.
5. Classificare i documenti per tema.
6. Collegare i luoghi citati alla mappa.

### Output attesi

- Archivio locale dei documenti.
- Corpus testuale.
- Tabella seduta / tema / luogo / decisione.
- Analisi delle frequenze tematiche.
- Timeline dell’agenda circoscrizionale.
- Mappa dei luoghi discussi.

---

## 12. Analizzare la qualità dei dati territoriali

### Descrizione

Questa azione serve a valutare completezza, coerenza e aggiornamento delle fonti disponibili.

Il progetto usa fonti diverse: Comune, circoscrizione, OpenStreetMap, ISTAT, social, documenti istituzionali. Ognuna ha punti di forza e limiti. Confrontarle permette di capire dove i dati sono solidi e dove invece servono verifiche o integrazioni.

L’obiettivo è produrre una base dati affidabile e, dove possibile, migliorare anche OpenStreetMap.

### Dati necessari

- File servizi della circoscrizione.
- OpenStreetMap.
- Dataset comunali.
- Osservazioni sul campo.
- Documenti e comunicazioni pubbliche.
- Orari e informazioni di accessibilità.
- Indirizzi e coordinate.

### Metodologia

1. Confrontare gli stessi oggetti tra fonti diverse.
2. Identificare:
   - oggetti mancanti;
   - duplicati;
   - errori di indirizzo;
   - coordinate errate;
   - categorie incoerenti;
   - orari mancanti;
   - accessibilità non documentata.
3. Assegnare uno stato di qualità a ogni elemento.
4. Documentare le correzioni necessarie.
5. Preparare eventuali contributi a OpenStreetMap.

### Output attesi

- Tabella di qualità dati.
- Elenco dei servizi da verificare.
- Elenco dei servizi da aggiornare in OSM.
- Note metodologiche.
- Dataset pulito e documentato.

---

## 13. Individuare gli spazi ponte

### Descrizione

Questa azione è una delle più importanti del progetto.

Gli spazi ponte sono luoghi capaci di mettere in relazione comunità residente, associazioni, FBK, Università e city users. Possono essere spazi civici, culturali, informali, verdi, educativi o di passaggio.

L’obiettivo è capire quali luoghi possono diventare punti di contatto tra la vita locale e il polo scientifico-universitario.

### Dati necessari

- Mappa dei servizi.
- Mappa degli spazi civici.
- Accessibilità da FBK/Università.
- Eventi e vita civica.
- Sedute del consiglio.
- Demografia.
- Percorsi pedonali.
- Pendenze.
- Informazioni su target e usi.
- Dati qualitativi da osservazione o interviste.

### Metodologia

1. Definire criteri per identificare gli spazi ponte:
   - accessibilità;
   - uso civico;
   - vicinanza a FBK/Università;
   - presenza di servizi;
   - potenziale di attivazione;
   - valore simbolico;
   - disponibilità di spazi.
2. Assegnare un punteggio o una valutazione qualitativa.
3. Costruire schede per i luoghi candidati.
4. Classificare gli spazi per potenziale:
   - alto;
   - medio;
   - basso.
5. Individuare azioni possibili per ciascun luogo.

### Output attesi

- Atlante degli spazi ponte.
- Mappa degli spazi ponte.
- Schede luogo.
- Matrice spazio / target / azione.
- Lista prioritaria dei luoghi da attivare.

---

## 14. Individuare gap e criticità

### Descrizione

Questa azione serve a identificare gli elementi che oggi limitano la relazione tra Povo, FBK e Università.

I gap possono essere fisici, informativi, organizzativi, simbolici o legati alla qualità dei dati. Riconoscerli permette di passare da una semplice descrizione del territorio a una diagnosi progettuale.

L’obiettivo è capire cosa impedisce ai flussi quotidiani generati da FBK e Università di diventare relazioni più stabili con il territorio.

### Dati necessari

- Risultati delle analisi precedenti.
- Accessibilità.
- Percorsi.
- Eventi.
- Sedute del consiglio.
- Dati demografici.
- Mappa dei servizi.
- Qualità dati.
- Osservazioni sul campo.
- Eventuali interviste o confronti con stakeholder.

### Metodologia

1. Raccogliere criticità emerse dalle diverse analisi.
2. Classificarle per tipo:
   - accessibilità;
   - comunicazione;
   - uso degli spazi;
   - dati;
   - mobilità;
   - relazione istituzionale;
   - percezione;
   - servizi.
3. Collegare ogni gap a luoghi specifici quando possibile.
4. Valutare priorità e impatto.
5. Collegare ogni criticità a possibili azioni.

### Output attesi

- Elenco dei gap.
- Mappa delle criticità.
- Matrice gap / causa / possibile azione.
- Priorità di intervento.
- Base per le raccomandazioni finali.

---

## 15. Individuare opportunità e azioni pilota

### Descrizione

Questa azione serve a trasformare l’analisi in proposte operative.

L’obiettivo non è solo descrivere Povo, ma individuare azioni concrete per rafforzare la relazione tra circoscrizione, comunità locale, FBK e Università.

Le azioni possono essere leggere, sperimentali e progressive.

### Dati necessari

- Spazi ponte.
- Gap e criticità.
- Eventi esistenti.
- Disponibilità di spazi civici.
- Temi ricorrenti nella comunità.
- Competenze FBK/Università.
- Associazioni e soggetti locali.
- Percorsi e accessibilità.
- Dati sulla comunicazione pubblica.

### Metodologia

1. Collegare ogni opportunità a uno spazio o a un tema.
2. Distinguere azioni a breve, medio e lungo periodo.
3. Valutare fattibilità, impatto e attori coinvolti.
4. Costruire un primo piano di azione.
5. Definire possibili iniziative pilota.
6. Collegare le azioni agli output del sito web e delle mappe.

### Output attesi

- Lista di opportunità.
- Piano di azione.
- Proposte pilota.
- Matrice azione / luogo / attori / tempi.
- Raccomandazioni operative.

---

## 16. Costruire il sito web del progetto

### Descrizione

Questa azione serve a rendere pubblici e navigabili i risultati del progetto.

Il sito web deve raccontare il progetto, mostrare le mappe, spiegare i dati, visualizzare gli output e rendere comprensibile il percorso di analisi.

L’obiettivo è produrre uno strumento utile sia per la comunicazione pubblica sia per lo sviluppo del lavoro.

### Dati necessari

- Testi descrittivi.
- Mappe statiche.
- Mappe interattive.
- Dataset puliti.
- Grafici.
- Schede luogo.
- Raccomandazioni.
- Immagini.
- Logo e template grafico.
- Documentazione metodologica.

### Metodologia

1. Definire la struttura del sito.
2. Preparare le sezioni principali:
   - progetto;
   - territorio;
   - dati;
   - mappe;
   - analisi;
   - spazi ponte;
   - raccomandazioni;
   - metodologia.
3. Integrare mappe interattive.
4. Pubblicare dataset e documentazione.
5. Costruire pagine narrative o data stories.
6. Aggiornare il sito man mano che le analisi avanzano.

### Output attesi

- Sito web pubblico del progetto.
- Mappe interattive.
- Pagine narrative.
- Sezione dati.
- Sezione metodologia.
- Sezione raccomandazioni.
- Documentazione riusabile.

---

## 17. Documentare il metodo e rendere il progetto riproducibile

### Descrizione

Questa azione serve a garantire trasparenza e riusabilità.

Il progetto deve essere documentato in modo che altri possano capire da dove vengono i dati, come sono stati trattati, quali scelte metodologiche sono state fatte e come riprodurre le analisi.

L’obiettivo è costruire un progetto aperto, verificabile e riusabile.

### Dati necessari

- Elenco delle fonti.
- Script.
- Notebook.
- Parametri di analisi.
- Versioni dei dataset.
- Licenze.
- Metadati.
- Note metodologiche.
- Decisioni progettuali.

### Metodologia

1. Documentare ogni fonte dati.
2. Separare dati grezzi e dati elaborati.
3. Scrivere script riproducibili.
4. Mantenere un changelog.
5. Documentare licenze e vincoli d’uso.
6. Spiegare le scelte metodologiche.
7. Pubblicare README specifici per ogni cartella.

### Output attesi

- Documentazione metodologica.
- README di progetto.
- README per le cartelle dati.
- Script commentati.
- Changelog.
- Metadata dei dataset.
- Licenze chiare.
