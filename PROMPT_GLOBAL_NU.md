# Prompt: global-nu.org — il sito della Bari global analysis

> Prompt per Claude Code sul Mac Pro. Modello: **Claude Opus 5** (`claude-opus-5`),
> sia per le sessioni di costruzione sia per l'automazione giornaliera.
> Cartella di lavoro: `~/Desktop/Ricerca/global-nu` (questo file vive lì).
> Aggiungere anche, come directory ausiliarie di sola lettura:
> `~/Documents/My Home Page - Claude` (sito personale) e
> `~/Desktop/JUNO_2026` (release e materiali dell'analisi).

---

## Contesto e obiettivo

Sono Antonio Marrone, Full Professor of Theoretical Physics, Università di Bari
e INFN. Il nostro gruppo (Capozzi, Giarè, Lisi, Marrone, Melchiorri, Palazzo)
produce da oltre vent'anni analisi globali delle oscillazioni di neutrini.
Vogliamo esporle alla comunità su un sito dedicato, **global-nu.org**, che deve
diventare un punto di riferimento per la comunità del neutrino:
"infinitamente meglio di NuFit". Il sito è **interamente in inglese**.

Il dominio global-nu.org **non è ancora stato acquistato** e la prossima
release (JUNO 2026) sarà pronta tra circa un mese. Quindi: **si sviluppa e si
prova tutto in locale**; GitHub e il dominio entrano solo nella fase di lancio
(vedi Fasi). Nulla va costruito in modo che debba essere rifatto al lancio.

## Regole non negoziabili

Leggi `CLAUDE.md` e `SKILLS.md` del progetto del sito personale
(`~/Documents/My Home Page - Claude`): quelle regole nascono da errori reali e
valgono anche qui. In particolare:

1. **Nessun numero fisico dalla memoria.** Ogni valore con una fonte —
   parametri, range, sigma — si verifica sulla fonte primaria PRIMA di
   scriverlo: tabella del paper (arXiv/journal, via `PdfReader` o pagina
   arXiv), file di release. Se la fonte non è raggiungibile: segnaposto
   dichiarato, mai un numero plausibile.
2. **Convenzioni esplicite.** Il gruppo usa δm² = m₂² − m₁² > 0 e
   Δm² = m₃² − (m₁² + m₂²)/2. NuFit usa Δm²₃₁, Valencia Δm²₃₁ (NO) / Δm²₂₃ (IO).
   I valori NON sono confrontabili a colpo d'occhio: ogni confronto passa per
   una conversione documentata nel codice e nella pagina.
3. **I sorgenti dell'analisi non entrano mai nel sito né nel repo.** Solo
   prodotti esportati (tabelle, figure, file dati).
4. **Verificare eseguendo, non deducendo.** Build reale, jsdom per il JS,
   link verificati contro il filesystem, contrasto WCAG dei temi via test.
5. **Igiene del sito pubblico:** niente note-a-sé ("TODO", "scaffold",
   percorsi locali) sulle pagine; nomi file senza spazi/parentesi/apostrofi.
6. La password INFN e ogni altra credenziale non si scrivono mai, da nessuna
   parte.

## Architettura

Sito **statico puro** (HTML + CSS + JS minimale), build system proprio sul
modello di quello del sito personale — studialo prima di scrivere una riga
(`build.py`, `site-src/`, `serve.sh`, protezione `shield_math`, escaping del
frontmatter, token CSS dei due temi):

```
global-nu/
  site-src/
    content/          # Markdown con frontmatter, uno per pagina
    templates/        # base.html + varianti
    assets/           # css, js, fonts, vendor/katex (tutto self-hosted)
    data/             # YAML/JSON: releases, history, resources, conferences
  data-exports/       # prodotti esportati dalle release (input del build)
  tools/              # export release, fetcher, test
  build.py
  site/               # OUTPUT (mai editato a mano)
  serve.sh            # preview locale
  update-daily        # job giornaliero (fase Automazione)
```

- **Niente CDN esterni**: KaTeX, font e JS self-hosted (robustezza e nessuna
  dipendenza; su GitHub Pages non ci sono i vincoli INFN, ma la regola resta).
- **Due temi** (chiaro/scuro) via token CSS, nessun colore hard-coded; test di
  contrasto WCAG sul modello di `tools/tests/test_theme.js` del sito personale.
- **Git locale fin dal primo commit.** Repo inizializzato subito. Per ora
  si committa anche `site/` (al lancio servirà a GitHub Pages; se si sceglierà
  il deploy via Action si ristrutturerà allora). Il `.gitignore` esclude
  cache, `.venv`, log e file temporanei.
- **Identità visiva propria**, scelta su mockup: PRIMA di costruire le pagine,
  proponi 2–3 mockup di homepage con stili distinti (es. "collaborazione
  scientifica" scuro con accento distintivo; variante chiara; variante densa
  tipo data-driven). Aprili nel browser e procedi SOLO dopo l'approvazione di
  Antonio. Stile autonomo dal sito personale (Editorial avorio/oro): i due
  siti devono essere riconoscibili come cose diverse.

## Le pagine

| Pagina | Contenuto | Aggiornamento |
|---|---|---|
| **Home** | hero, ultima release in evidenza, teaser news, link rapidi | auto (teaser) |
| **Results** | una sezione per release; al lancio la release 2025 (arXiv:2503.07752, PRD 111 093006): best fit e range dei sei parametri nelle NOSTRE convenzioni, tabelle e mappe Δχ², figure, dati scaricabili, autori, BibTeX. Slot 2026 predisposto ma vuoto finché il paper non è su arXiv | manuale, a release |
| **Parameter history** | evoluzione dei parametri 2000→oggi per TRE gruppi: Bari, Valencia (de Salas/Forero/Tórtola/Valle), NuFit — vedi sezione dedicata | manuale |
| **arXiv digest** | sperimentale + teorico, generato con AI, con link arXiv/INSPIRE/DOI | giornaliero |
| **Neutrino News** | news a scalare: si pubblica solo quando c'è materiale pronto | giornaliero |
| **Conferences** | prossime e recenti: date, sede, link, highlight delle appena concluse | giornaliero |
| **Resources** | esperimenti, data release, banche dati (PDG, NuFIT, INSPIRE…), review; curati in YAML | manuale + check link |
| **Search** | ricerca in linguaggio naturale su INSPIRE-HEP, arXiv, Crossref, OpenAlex, client-side; riparti da `site-src/content/Search.md` + `assets/js/search.js` del sito personale | statico |
| **About** | il gruppo, la serie di paper, come citarci, contatti | manuale |

In testa a ogni pagina generata automaticamente: *"This page is generated
automatically with AI and may contain errors"* + timestamp dell'ultimo
aggiornamento riuscito.

### Parameter history (requisito, non opzione)

Storia dei sei parametri di oscillazione dal 2000 a oggi, compilata **dai
paper pubblicati** (i file χ² storici non esistono più):

- **Bari**: la serie di analisi globali del gruppo dal 2000 in poi (Fogli,
  Lisi, Marrone, Montanino, Palazzo, Rotunno, Capozzi, …). Recupera la lista
  dei paper da INSPIRE (author search) e conferma con Antonio la lista prima
  di estrarre i numeri.
- **Valencia**: de Salas, Forero, Tórtola, Valle e predecessori.
- **NuFit**: Esteban, González-García, Maltoni, Schwetz e predecessori
  (incluse le release intermedie su nu-fit.org quando citabili).

Regole di compilazione:

1. Ogni punto (gruppo, anno, parametro, best fit, range) cita il paper
   d'origine: arXiv ID, tabella, e convenzione usata. Tutto in un file
   `site-src/data/history.yaml` leggibile e verificabile a mano.
2. Estrazione SOLO dalla fonte primaria (PDF o pagina arXiv, `PdfReader`).
   Nessun valore "ricordato". Punto non verificabile = punto assente,
   mai interpolato.
3. Conversione tra convenzioni di Δm² esplicita e documentata; sulla pagina
   una nota metodologica dice come leggere il confronto.
4. La pagina mostra la timeline per parametro (grafico interattivo o SVG
   statico con i tre gruppi distinguibili in entrambi i temi) e il progresso
   della precisione nel tempo.
5. Questo è un lavoro lungo: falla come sotto-fase con checkpoint, e proponi
   ad Antonio la lista dei paper PRIMA di estrarre i numeri.

### Opzioni per essere più di NuFit (proponile, decide Antonio)

1. **Δχ² explorer interattivo** — curve navigabili client-side (zoom, overlay
   NO/IO, lettura dei valori al cursore) dai dati della release.
2. **Dati machine-readable a URL stabili** — es. `data/v2025/parameters.json`,
   schema documentato, pensati per essere scaricati via script e citati.
3. **Feed RSS/Atom** per news e digest.
4. **Methodology** — come si fa un'analisi globale: χ², convenzioni, dataset;
   valore pedagogico, attira studenti.

## Fasi

**Fase 0 — Studio.** Leggi CLAUDE.md/SKILLS.md del sito personale, `build.py`,
la struttura di `site-src/`, i fetcher di `news-update`, `ingest_digest.py`.
Estendi/adatta, non reinventare. Non toccare nulla del sito personale in
questa fase.

**Fase 1 — Scheletro + mockup.** Struttura del progetto, `build.py` adattato,
`serve.sh`, git init. Poi i 2–3 mockup di homepage → STOP per approvazione.

**Fase 2 — Pagine e release 2025.** Tutte le pagine del nucleo con la release
2025 (numeri verificati su arXiv:2503.07752/PRD). Search funzionante.
Parameter history come sotto-fase con il suo checkpoint (lista paper →
approvazione → estrazione → verifica).

**Fase 3 — Automazione locale.** Job giornaliero (launchd) che: esegue i
fetcher (arXiv, conferenze), invoca Claude Code headless (`claude -p`, modello
`claude-opus-5`) per digest/news, fa il build e (per ora) si ferma lì —
niente push finché non c'è GitHub. Comando manuale equivalente. Log degli
aggiornamenti riusciti/falliti.

**Fase 4 — Lancio (quando Antonio ha dominio e via libera).**
1. Organizzazione GitHub (nome proposto: `global-nu`) + repo, prima privato
   per backup, poi pubblico.
2. GitHub Pages (repo pubblico) + file `CNAME` + record DNS presso il
   registrar (4 A record di Pages + CNAME www) + HTTPS enforced.
3. Il job giornaliero acquisisce `git commit && git push`.
4. Verifica end-to-end: dominio → 200, HTTPS ok, pagine generate aggiornate.

**Fase 5 — Integrazione col sito personale (solo a sito lanciato).** Le pagine
`Neutrino-News`, `Search` e `Results` del sito personale diventano versioni
sintetiche, nello stile Editorial del sito personale, con link "full version
on global-nu.org". Un solo fetch al giorno alimenta entrambi i siti: i fetcher
scrivono i dati una volta, i due build li consumano. Eliminare i doppioni,
non le pagine. Qui valgono TUTTE le regole del CLAUDE.md del sito personale
(publish.sh, .htaccess, verifica juno2026 → 401 dopo ogni publish).

## Verifiche (per dichiarare chiusa una fase)

- `python3 build.py` pulito; preview locale controllata nel browser.
- Test tema/contrasto WCAG su tutti i colori nuovi (entrambi i temi).
- JS testato con jsdom (search, explorer, lightbox se c'è).
- Link interni verificati contro il filesystem; link esterni campionati.
- Numeri fisici: ricontrollo finale di ogni valore contro la fonte citata.
- Automazione: almeno un ciclo completo del job giornaliero eseguito
  davvero, con log verificato.

## Cosa NON fare

- Non caricare mai su GitHub i sorgenti dell'analisi, né dati non pubblici
  (release 2026 prima che il paper sia su arXiv).
- Non usare CDN o risorse esterne runtime.
- Non copiare lo stile del sito personale.
- Non inventare descrizioni, sommari o numeri: fonte o segnaposto.
- Non chiedere conferma per ogni piccolezza: i checkpoint sono i mockup
  (Fase 1), la lista paper della history (Fase 2), il lancio (Fase 4).
