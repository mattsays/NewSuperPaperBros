# Port nativo macOS e ricompilazione PAL

Questa modifica aggiunge una build ARM64 per Apple Silicon e un profilo separato per **Super Paper Mario Europa, revisione 1 (R8PP01)**. Il codice PowerPC del disco viene tradotto e compilato in un eseguibile nativo; il renderer usa Metal. Il gioco richiede il dump personale della revisione corrispondente.

## Perché serve un profilo PAL

Il codice PAL non può usare direttamente gli indirizzi della ricompilazione USA. Funzioni, globali, aree di piccoli dati e modulo REL occupano posizioni differenti. Riutilizzare gli indirizzi USA porta già durante l'avvio a chiamare routine hardware Wii prive di un dispositivo corrispondente sul Mac.

`tools/prepare-spm-eu1.py` verifica gli eseguibili del disco e prepara `runtime-eu1` senza modificare il runtime USA originale. Applica la mappa di `tools/macos/spm-eu1-addresses.json` e genera il profilo `wiicompiled/projects/spm-eu1`. Le mappe pubbliche provengono da [SeekyCt/spm-decomp](https://github.com/SeekyCt/spm-decomp), commit `bb6e5f6ef84e4b13808e317d687e8990f6fd7be6`: per EU1 il progetto usa esplicitamente i simboli EU0, perché gli indirizzi coincidono.

La corrispondenza USA→PAL è ricavata da nomi di simboli, ordinamento e sequenze di tipo/dimensione. Le voci dedotte restano sperimentali. I riferimenti SDK più importanti sono verificati separatamente leggendo le istruzioni del DOL con `verify-eu1-sdk.py`.

| Elemento | PAL Rev 1 |
| --- | --- |
| ID disco | `R8PP01` |
| SHA-256 main.dol | `c853aafb4beb7504d5ab8c81445c3dc7cc244a4486c70d9eaed71639c41049cf` |
| SHA-256 relF.bin compresso | `9aa3d707395fc3b89354bf889ca332565f067e30243c66f5af48532689aca2eb` |
| SHA-1 REL decompresso | `29c78007559996dee6b615005fa3369d4cc1f5e3` |
| SDA r13 | `0x805B5F00` |
| SDA2 r2 | `0x805B7260` |
| Arena/stack iniziale | `0x805C7740` |
| REL caricato | `0x80C464E0` |
| BSS del REL | `0x80F65000` |
| Prologo REL | `0x80C84D54` |

Le basi REL e BSS sono state misurate dalla tabella dei moduli collegati durante un avvio PAL e confrontate con il log del loader. La posizione stimata inizialmente era insufficiente: arrivava al modulo ma non trovava il suo prologo. Il valore finale coincide con il caricamento reale. Il byte di revisione nella partizione estratta può essere zero anche se il disco esterno è Rev 1; l'identificazione usa quindi gli hash del codice.

WPAD, KPAD e le altre chiamate native sono rimappate al relativo SDK PAL. Sia l'inizializzatore WPAD interno sia quello pubblico entrano nello stesso stato nativo, evitando il tentativo di avviare l'hardware USB/Bluetooth della Wii. Non vengono introdotti accessi MMIO che restituiscono arbitrariamente zero.

I globali di gioco `now_seq`, `next_seq` e `gp` hanno corrispondenze esplicite ricavate dai simboli PAL. Per queste variabili, associare soltanto simboli anonimi per dimensione può scegliere un indirizzo adiacente e impedire al runtime di riconoscere correttamente la sequenza corrente.

## Italiano e altre lingue

Il launcher PAL offre italiano, inglese, francese, tedesco e spagnolo. Passa `SPM_LANGUAGE` al processo del gioco; l'override PAL di `SCGetLanguage` restituisce il codice Wii corrispondente. Per l'italiano è `5`, come in `wii/sc.h` del progetto spm-headers. Il gioco legge i propri file `files/msg/IT`, senza sostituire testi o usare traduzioni esterne.

Il profilo PAL salva in `~/Library/Application Support/NewSuperPaperBrosPAL`, distinto da quello USA (`NewSuperPaperBros`). Il titolo NAND PAL è `00010000/52385050`. La selezione del disco verifica DOL, REL e FST; l'RVZ originale rimane intatto.

## Icona, risoluzione e 16:10

Il launcher AppKit e il gioco hanno l'icona Pixl già usata dal progetto, convertita in ICNS con dimensioni standard e Retina. Il gioco viene aperto attraverso Launch Services, così macOS registra correttamente il suo identificatore e l'icona del Dock.

La risoluzione interna è selezionabile nel launcher: 480p, 720p, 1080p, 1440p, 4K oppure dimensione dello schermo. La scelta viene salvata conservando le altre impostazioni. Il menu F10 permette cambiamenti durante il gioco.

La modalità **16:10 (Mac)** usa `aspect_mode = 4`. Imposta un viewport 16:10 e adatta le proiezioni 16:9 aggiungendo visuale verticale, mantenendo la larghezza. Non allarga gli sprite e non taglia lateralmente l'HUD. I piccoli viewport usati per renderizzare texture restano invariati. Anche puntatore e layout delle interfacce tengono conto della nuova proporzione. Le modalità preesistenti conservano i loro valori 0–3.

L'HUD è inoltre ancorato al bordo superiore: PV e barra del 3D a sinistra, punti al centro, monete a destra. Icone e cifre si spostano insieme, mantenendo dimensioni, spaziatura e margine superiore rispetto al 16:9. La correzione delle matrici è limitata alle chiamate di `hudDisp` e dei suoi aiutanti: non sposta mondo, dialoghi o menu. Poiché SPM disegna l'HUD con una camera prospettica, l'offset dipende dalla profondità per conservare lo stesso allineamento anche fra elementi disegnati su piani diversi. Le animazioni che nascondono l'HUD rimangono libere di oltrepassare il bordo.

## Texture HD

Il caricamento delle sostituzioni era già presente nel renderer. Il launcher aggiunge attivazione/disattivazione persistente e un comando per installare un pacchetto estratto. `tools/macos/install-hd-textures.py` scarica e verifica il pacchetto DDS 4× di **Razius**, quindi lo installa nel profilo dell'app scelta. L'archivio è fissato con SHA-256, e viene validato prima dell'estrazione.

Il pacchetto è parziale: contiene 1.952 file DDS e il renderer ne indicizza 1.915 come sostituzioni uniche. Alcuni elementi localizzati PAL mantengono la grafica originale. Il log opzionale `SPM_TEXTURE_LOG=1` dimostra il caricamento effettivo sulla GPU, oltre alla sola indicizzazione.

Crediti: [progetto originale di Razius](https://www.emutalk.net/threads/super-paper-mario.55330/), [mirror del pacchetto 4×](https://emulationking.com/nintendo/wii/games/superpapermario/texturepacks/razius/). Il pacchetto viene scaricato separatamente; non è incluso nel repository.

## Compilazione

Servono un Mac Apple Silicon, strumenti Apple/Swift, Python 3, CMake, Ninja, .NET 8 e nodtool macOS ARM64 v2.0.0-alpha.10. Usare il checkout di spm-decomp fissato sopra.

```sh
python3 tools/build-macos.py --profile eu1 \
  --game "/percorso/Super Paper Mario (Europe) (En,Fr,De,Es,It) (Rev 1).rvz" \
  --dotnet /percorso/dotnet \
  --nodtool /percorso/nodtool \
  --symbols-root /percorso/spm-decomp
```

Il risultato è `dist/macos/New Super Paper Bros PAL.app`. Il launcher non richiede .NET. Per installare le texture:

```sh
python3 tools/macos/install-hd-textures.py --app "dist/macos/New Super Paper Bros PAL.app"
```

I dati del disco, il codice tradotto, le dipendenze scaricate e i runtime generati sono esclusi da Git. Il repository contiene il codice del port e i simboli pubblici, non gli eseguibili del disco.

## Verifiche e limiti

Sul Mac M1 con macOS 26.6.2 sono stati verificati 28/28 riferimenti SDK PAL, traduzione senza istruzioni non supportate o SSA invalida, compilazione nativa ARM64, allineamento REL/BSS, menu originali italiani e caricamento effettivo di texture 4×. I test della proiezione controllano rapporto geometrico, integrità dei bordi HUD, continuità del 16:9/panoramico e assenza di modifiche ai viewport delle texture. Il parser delle impostazioni controlla il nuovo valore 4 e rifiuta valori non supportati.

Un test con dati temporanei ha caricato `he1_01`, mostrato HUD e messaggi italiani, eseguito movimento, salto e passaggio al 3D in modalità 16:10 con texture HD. Il test usa il comando di sviluppo per raggiungere il livello: non dimostra la progressione completa della storia. Nell'app finale sono stati verificati Play, menu F10 con “16:10 (Mac)”, avvio con tastiera e ritorno al launcher dopo l'uscita. I salvataggi di prova non sono installati nel profilo del giocatore.

Il successivo confronto dell'HUD a 1080 linee mostra PV, punti e monete spostati insieme verso l'alto di circa 28 pixel, con il riquadro del dialogo nella stessa posizione. Il test della proiezione verifica anche la conservazione del margine superiore e l'allineamento prospettico a profondità diverse. Il log facoltativo `SPM_HUD_LOG=1` conferma l'offset applicato alle matrici dell'HUD.

È una preview sperimentale: un avvio e test mirati non certificano ogni capitolo, filmato, effetto o controller. Il target di compilazione è macOS 12, ma versioni precedenti a quella provata e Mac Intel non sono stati verificati. L'app locale è firmata ad hoc, senza notarizzazione Developer ID.
