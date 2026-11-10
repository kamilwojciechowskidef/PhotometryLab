# PhotometryLab — szczegółowa instrukcja interfejsu Streamlit

Stan opisu: 22 października 2026 r. Dokument opisuje aktualne `app.py` i
`photolab/bulk_ui.py`, w tym pierwszy etap obsługi wielu ZIP-ów. Etykiety
angielskie pozostawiono dosłownie, aby można było znaleźć je na ekranie.
Opis opiera się na kodzie; nie jest protokołem testu interfejsu w przeglądarce.

## 1. Do czego służy strona

Aplikacja wczytuje fotometrię IES/LDT, ocenia jej przydatność do obliczeń,
porównuje kształty rozsyłów, zapisuje pliki w katalogu PostgreSQL i udostępnia
eksperymentalną analizę ML. Obliczenia są lokalne. Pliki nie są przesyłane do
zewnętrznego API AI.

Podobny rozsył nie oznacza równoważnej oprawy. Dobór zamiennika wymaga również
strumienia, mocy, barwy, wymiarów, montażu, stopnia ochrony i obliczeń
oświetleniowych. Program jest narzędziem badawczym, nie certyfikowanym programem
projektowym.

## 2. Mapa strony i trzy różne zbiory danych

Po lewej jest panel `1. Luminaire set`. W części głównej znajdują się tytuł,
trzy liczniki, ostrzeżenie interpretacyjne i trzy zakładki. Na samym dole,
poniżej stopki, znajduje się `Open batch import`.

| Zbiór | Co zawiera | Gdzie go widać |
|---|---|---|
| Bieżący zestaw porównawczy | Wgrane pojedyncze IES/LDT, opcjonalne próbki demo i wybrane rekordy z bazy | Liczniki, ranking lokalny, wykresy, tabela jakości, ML |
| Trwały katalog PostgreSQL | Zapisane pliki, fotometria, jakość, aliasy i cechy indeksu | `Browse saved catalogue`, wyszukiwanie indeksowe, historia importów |
| Archiwum źródeł | Oryginalne bajty plików w lokalnym magazynie | `Browse source archive` |

Samo wybranie pliku w uploaderze bocznym nie zapisuje go do PostgreSQL.
Import wsadowy zapisuje katalog, ale nie dodaje automatycznie całej partii do
wykresów i ML. To rozróżnienie jest szczególnie ważne przy tysiącach plików.

## 3. Panel boczny — budowanie zestawu

### Upload .ies and .ldt files

Można wybrać wiele plików. Obsługiwany zakres obejmuje IES LM-63 Type C
z `TILT=NONE` i wybrane warianty EULUMDAT. Limit pojedynczego pliku to 5 MB.
Parser może odrzucić plik mimo prawidłowego rozszerzenia.

Pliki o jednakowych nazwach otrzymują w sesji rozróżniający dopisek, np.
`lampa (2).ies`. Nie oznacza to zmiany oryginalnej nazwy na dysku.

### Include synthetic demonstration files

Dołącza syntetyczne przykłady rozsyłów. Domyślnie opcja jest proponowana jako
włączona, kiedy nie przesłano własnych plików. Stan checkboxa można zmienić.
Przykłady nie są danymi producentów ani podstawą oceny skuteczności naukowej.
Automatycznie dołączone demo są wyłączone z przycisku zapisu uploadów do bazy.

### Align C rotation (10° steps)

Włącza poszukiwanie obrotu kandydata wokół osi C co 10°. Wybierany jest obrót
o najmniejszym ważonym RMSE, a przy remisie preferowany jest wyższy cosinus.
Opcja dotyczy lokalnego porównania i dokładnego rankingu kandydatów z bazy.
Po wyłączeniu porównywane są zapisane orientacje bez dopasowania obrotu.

### Browse saved catalogue

Rozwija przeglądarkę zapisanej fotometrii. `Manufacturer contains` i
`Model contains` wyszukują fragment tekstu bez rozróżniania wielkości liter.
`Catalogue page` wybiera stronę, po maksymalnie 50 rekordów.

Tabela pokazuje ID, nazwę pliku, producenta, model i format. Pole
`Add saved luminaires to comparison` dołącza wybrane rekordy do bieżącego
zestawu. Wybór dotyczy bieżącej strony i filtrów. Nazwy otrzymują prefiks
`[DB id]`, aby odróżnić identyczne nazwy różnych rekordów.

Identyczny SHA-256 już obecny w zestawie powoduje pominięcie powtórnego
dołączenia i komunikat informacyjny. Widok obejmuje rekordy z fotometrią;
plik odrzucony, zapisany wyłącznie jako źródło i raport, może się tu nie pojawić.

## 4. Liczniki nad zakładkami

| Licznik | Dokładne znaczenie |
|---|---|
| Files read | Liczba poprawnie odtworzonych modeli fotometrii w aktualnym zestawie |
| Luminaires ready to compare | Liczba modeli dopuszczonych przez raport jakości do porównania |
| Limited or rejected | Liczba wszystkich raportów minus liczba modeli gotowych do porównania |

Nie są to liczniki całej bazy. Nazwa trzeciego licznika jest uproszczeniem:
plik z ograniczeniem, ale nadal gotowy do porównania, nie zwiększa tego licznika.
`Files read but excluded from comparison` rozwija powody wyłączenia modeli,
które udało się odczytać. Odrzucone przez parser pliki opisuje tabela jakości.

## 5. Comparison and ranking — porównania

### Reference luminaire

Wybiera wzorzec spośród pozycji gotowych do porównania. Do wyszukiwania w bazie
wystarczy jeden wzorzec. Lokalny ranking i wykresy wymagają co najmniej dwóch
gotowych pozycji w bieżącym zestawie.

### Search indexed catalogue

Przycisk szuka kandydatów w PostgreSQL przez wersjonowany indeks LSH, po czym
oblicza dokładne metryki dla pobranej puli. Domyślne API ogranicza pulę do
10 000 kandydatów i wynik do 50 pozycji. Nie jest to pełny ranking całej bazy.
Brak kandydatów może oznaczać brak cech aktualnej wersji lub brak dopasowania
koszyków. Wymagany bywa backfill indeksu.

Tabela `Indexed catalogue candidates` zawiera `Catalogue ID`, `Candidate`,
`Cosine (1 = identical)`, `RMSE (0 = identical)` i `Rotation [°]`.
Podpis podaje liczbę kandydatów ocenionych dokładnie. Pobranie tabeli umożliwia
`Download indexed catalogue CSV` (`catalogue_ranking.csv`). Wynik może zawierać
zapisany odpowiednik samego wzorca. Nie dołącza automatycznie wyników do
lokalnych wykresów: należy wybrać rekordy przez przeglądarkę katalogu.

### Most similar distributions

Lokalny ranking porównuje wzorzec z pozostałymi gotowymi pozycjami aktualnego
zestawu. `Rank` oznacza miejsce. Sortowanie preferuje najmniejsze RMSE, następnie
największy cosinus, a potem nazwę. Wartości tabeli są zaokrąglone do pięciu
miejsc; podobny wygląd dwóch wierszy nie musi oznaczać identycznego wyniku.
`Download ranking CSV` zapisuje `photometry_ranking.csv`.

### Znaczenie metryk

Rozsyły są interpolowane do siatki C = 0–350° co 10° i γ = 0–90° co 5°.
Każdy jest niezależnie dzielony przez własne maksimum na tej siatce. Usuwa to
informację o absolutnej skali światłości. Wagi są proporcjonalne do sin(γ).

Cosinus opisuje podobieństwo kierunku ważonych wektorów; wyżej oznacza bardziej
podobny kształt. RMSE opisuje różnicę znormalizowanych wartości; niżej oznacza
lepsze dopasowanie. Obie miary są bezwymiarowe. Cosinus 0,98 nie oznacza
„98% zgodności opraw”. Rotacja jest przesunięciem zastosowanym do kandydata,
a nie zaleceniem montażowym.

### Compare with candidate i wykres przekrojów

Wybór kandydata ustawia parę pokazaną niżej. Trzy pola podają cosinus, ważony
RMSE i wybrany obrót. Wykres `Cross-section comparison after rotation alignment`
pokazuje cztery krzywe: C0 i C90 wzorca oraz C0 i C90 obróconego kandydata.
Kandydat ma linię przerywaną; wzorzec linię z punktami.

Oś X to γ w stopniach; oś Y to `Intensity / maximum`, czyli udział maksimum,
nie kandele ani lumeny. Dwie podobne krzywe nie dowodzą identyczności całego
rozsyłu: metryki wykorzystują wszystkie 36 płaszczyzn C.

### Distribution map

Mapa cieplna przedstawia wyłącznie wzorzec. Oś X to γ, oś Y to C. Kolor
`I / Imax` pokazuje znormalizowaną światłość; jaśniejsze obszary skali Viridis
oznaczają wyższe wartości. Nie jest to mapa natężenia oświetlenia na podłożu
ani widok 3D. W aktualnym układzie pojawia się razem z porównaniem pary.

## 6. Catalogue and data quality — dane i kontrola jakości

Główna tabela opisuje bieżący zestaw, a nie cały katalog PostgreSQL.

| Kolumna | Co przedstawia |
|---|---|
| File | Nazwę używaną w bieżącej sesji |
| Quality status | Klasyfikację raportu jakości, np. valid, limited, incomplete, unsupported, damaged |
| Ready to compare | Czy model może wejść do rankingu kształtu |
| Format | Odczytany format lub informację o odrzuceniu |
| Manufacturer / Model | Metadane z pliku; nie są zewnętrznie weryfikowane |
| C planes / Gamma angles | Liczby kątów w natywnym modelu, nie rozmiar wspólnej siatki rankingu |
| Symmetry | Kod symetrii modelu: radial, none, plane0, plane90 lub quadrants |
| Source unit | Jednostkę danych źródłowych, np. cd lub cd/klm |
| Power [W] | Moc odczytaną z metadanych, jeśli dostępna |
| Header flux [lm] | Strumień źródeł z nagłówka; niekoniecznie strumień oprawy |
| Calculated downward flux [lm] | Numeryczne przybliżenie strumienia dolnej półprzestrzeni |
| Covers γ 0–90° | Czy zakres pomiarowy obejmuje dolną półprzestrzeń |
| Reasons / warnings | Przyczyny ograniczeń, odrzucenia i uwagi parsera |

`unavailable` oznacza brak dostępnej wartości, nie zero. `none` w uwagach
oznacza brak zgłoszonych uwag; w kolumnie symetrii oznacza brak redukcji
symetrycznej. Symetria `radial` jest obrotowa, `plane0` i `plane90` dotyczą
odpowiednich płaszczyzn odbicia, `quadrants` — ćwiartek.

Pokrycie kątów nie wystarcza do porównania: rozsył może mieć w dolnej
półprzestrzeni same zera. Taki plik nie powinien być normalizowany do maksimum.
Status `incomplete` nie dowodzi uszkodzenia źródła — może wskazywać ograniczenie
względem zakresu obsługiwanego przez aplikację.

Strumień dolny jest całką numeryczną wymagającą konwersji do cd. Nie jest
deklaracją producenta, całkowitym strumieniem oprawy ani skutecznością lm/W.
Porównanie kształtu może być możliwe przy braku wiarygodnego strumienia.

`Download quality report CSV` pobiera `import_quality_report.csv`.
`File warnings and limitations` rozwija uwagi dla każdego pliku.

### Local PostgreSQL catalogue

`Save uploaded files to PostgreSQL` zapisuje wyłącznie pliki przesłane
uploaderem bocznym. Nie zapisuje ponownie wybranych rekordów DB ani automatycznie
dołączonych demonstracji. Zapis zachowuje oryginalne bajty w archiwum, hash,
alias, raport jakości i dostępną fotometrię w bazie. Gotowa fotometria otrzymuje
cechy aktualnego indeksu.

Komunikat `Added ... new file(s)` liczy nowe hashe. `Detected ... duplicate(s)`
oznacza rozpoznaną zawartość i dodanie aliasu importowego. Identyczna nazwa
nie przesądza o duplikacie; identyczna zawartość pod inną nazwą może nim być.
Błędy zapisu są wypisywane osobno. Ponowne kliknięcie jest nową operacją importu.

### Browse source archive

`Source archive page` wybiera stronę po 50 źródeł. `Source file` wybiera
oryginał; dostępne mogą być również źródła odrzucone przez parser.
Przed pobraniem program sprawdza rozmiar i SHA-256. Komunikat
`Source integrity verified` potwierdza zgodność bajtów, nie poprawność fotometrii.

`Download original source` pobiera oryginał. `Reparse source and preview quality`
uruchamia obecny parser i pokazuje status, gotowość porównania, gotowość
strumienia dolnego oraz uwagi. To podgląd: nie aktualizuje zapisanej fotometrii
ani cech. Starszy rekord bez archiwum wymaga ponownego zapisania oryginału.

## 7. ML exploration (experimental)

Analiza obejmuje tylko gotowe modele z bieżącego zestawu. Wymaga minimum trzech.
Suwak `Number of KMeans groups` wybiera od dwóch do maksymalnie sześciu grup,
jednocześnie nie więcej niż liczba pozycji minus jeden.

Każdy punkt wykresu PCA oznacza plik. PC1 i PC2 to dwie składowe projekcji
ważonych cech rozsyłu, nie fizyczne kąty ani jednostki fotometryczne. Kolor
oznacza grupę KMeans, symbol — oznaczenie anomalii. Nazwa pliku jest dostępna
po wskazaniu punktu. Bliskość w projekcji 2D może pomijać różnice w pozostałych
wymiarach. Grupy powstają na pełnych cechach, nie tylko na dwóch osiach wykresu.

`Explained variance` informuje, jaki udział zmienności zachowują PC1 i PC2.
To nie dokładność modelu. Isolation Forest jest uruchamiany od ośmiu pozycji;
wcześniej `Anomalous` ma wartość `not assessed`. Anomalia oznacza nietypowość
względem wybranego zbioru, nie wadliwą oprawę.

Tabela zawiera File, PC1, PC2, Cluster i Anomalous. Przycisk
`Download ML results CSV` pobiera `ml_results.csv`. Zmiana zestawu zmienia
projekcję, klastry i potencjalne anomalie; numer grupy nie jest trwałą kategorią.

## 8. Open batch import — dolna część strony

Checkbox znajduje się pod stopką, poza trzema zakładkami. Otwiera formularz
trwałego importu. `Batch IES/LDT files` przyjmuje wiele pojedynczych plików,
`Or multiple ZIP archives` wiele ZIP-ów. Należy użyć jednej z tych dróg.
`Batch source / provenance` jest wymaganym opisem pochodzenia. Warto podać
źródło, datę pozyskania i podstawę wykorzystania danych.

`Import batch` rozpoczyna zapis. Dla pojedynczych IES/LDT widoczny jest pasek
postępu po plikach, po zakończeniu tabela i `Download batch report`.
Dla wielu ZIP-ów bieżący komunikat ma postać `Archive x/y: nazwa`. Aktualny
wariant ZIP nie pokazuje paska postępu wewnątrz archiwum.

### Limity i sposób przetwarzania

- Maksymalnie 500 plików w partii lub 500 wpisów pojedynczego ZIP-a.
- Maksymalnie 5 000 000 bajtów na plik fotometryczny.
- Maksymalnie 100 000 000 bajtów w partii i po rozpakowaniu jednego ZIP-a.
- Łącznie maksymalnie 100 000 000 bajtów przesłanych ZIP-ów w formularzu.

Archiwa są przetwarzane kolejno, ale uploady Streamlit pozostają w pamięci.
ZIP-y nie są wypakowywane do wskazanych przez wpisy ścieżek dyskowych.
Niebezpieczne nazwy, szyfrowanie, dowiązania, powtarzające się nazwy i nadmierna
kompresja powodują odmowę. Każdy ZIP ma własną partię i opis zawierający nazwę
archiwum. Błąd jednego archiwum jest raportowany, a pętla UI przechodzi dalej.

### Raporty

| Pole / wynik | Znaczenie |
|---|---|
| new | Nowa zawartość z odczytaną fotometrią |
| duplicate | Istniejący hash, dodany alias importowy |
| rejected | Parser odrzucił fotometrię; źródło i raport mogą być zapisane |
| skipped | Wpis pominięty, np. nieobsługiwane rozszerzenie lub za duży plik |
| error | Błąd operacji zapisu/importu |
| quality | Osobny status jakości fotometrii |
| duplicate | Flaga duplikatu niezależna od outcome, istotna również przy rejected |
| file_id | ID zapisanego pliku, jeśli zapis nastąpił |
| message | Powód, ostrzeżenia lub błąd |

Podsumowanie wielu ZIP-ów zawiera archive, batch_id, files i errors albo error
przy awarii archiwum. Licznik errors sumuje wyniki error, skipped i rejected;
nie liczy wszystkich ograniczeń jakości. `Download archive summary` pobiera
`archive_summary.csv`. Szczegóły plików są w historii odpowiednich partii.

Komunikat `Batch #... finished` oznacza zakończenie pętli, a nie gwarancję
powodzenia każdego pliku. Zawsze należy sprawdzić outcome i quality.

### Show batch history

`History page` przegląda strony po 20 partii. Pierwsza tabela pokazuje ID,
czas importu, opis źródła, status i oczekiwaną liczbę plików. `Batch report`
wybiera szczegółowy raport, a `Download historical report` pobiera jego CSV.

`completed` oznacza koniec bez wyników error/skipped/rejected;
`completed_with_errors` — koniec z przynajmniej jednym takim wynikiem;
`running` może oznaczać także przerwaną operację. Raport jest utrwalany po
każdym pliku, lecz awaria między zapisem pliku a raportu może pozostawić różnicę.
Po zakończeniu ścieżki wielu ZIP-ów formularz kończy bieżące wykonanie przed
historią; historia pojawia się przy kolejnym przebiegu strony.

## 9. Restart, odświeżanie i duże importy

Streamlit ponownie wykonuje skrypt po zmianach kontrolek. Nie wszystkie wyniki
akcji przycisków są przechowywane w stanie sesji; tabela wyszukiwania lub
podsumowanie importu mogą zniknąć po kolejnej interakcji. Historia PostgreSQL
pozostaje trwała. Zakładki nie zapewniają niezależnych procesów w tle.

W obecnym kodzie import blokuje wykonanie obsługującej go sesji. Nie ma trwałej
kolejki z automatycznym wznowieniem. Ponowny import rozpoznaje hashe, ale tworzy
nowe partie i aliasy. W trakcie operacji należy zaczekać na wynik i nie wywoływać
powtórnego importu tej samej partii.

Dla wielu lokalnych ZIP-ów dostępny jest poza Streamlit moduł
`python -m photolab.zip_import KATALOG --source "Opis źródła"`.
Przetwarza jedno archiwum naraz, z dotychczasowymi limitami. Nie należy mylić go
z kompletną kolejką wznawialną. Szczegóły: [BULK_IMPORT.md](BULK_IMPORT.md).

## 10. Typowe scenariusze

### Porównanie dwóch opraw

Wgraj dwa pliki w panelu bocznym, sprawdź gotowość i uwagi w tabeli jakości,
wybierz wzorzec oraz kandydata w pierwszej zakładce. Oceń RMSE, cosinus,
przekroje i zakres danych. Pobierz ranking i raport jakości.

### Zbudowanie trwałego katalogu

Otwórz import na dole, wybierz pliki lub ZIP-y, opisz źródło i uruchom import.
Sprawdź raport każdej partii. Następnie w panelu bocznym otwórz katalog,
przefiltruj rekordy i dołącz tylko potrzebne pozycje do porównania.

### Szukanie podobnego rozsyłu w bazie

Wgraj jeden wzorzec, wybierz go i uruchom `Search indexed catalogue`. Sprawdź
liczbę ocenionych kandydatów oraz ID wyników. Do wykresów dołącz wybrany rekord
przez katalog. Ocena podobieństwa obejmuje pulę LSH, nie wszystkie rekordy.

### Brak wyników lub niezgodne liczniki

Sprawdź, czy pliki zostały zapisane, czy mają fotometrię i czy są gotowe do
porównania. Liczba uploadów, unikalnych hashy, modeli i cech może być różna.
`examined=0` w indeksatorze może oznaczać, że wszystko jest już zindeksowane,
że baza jest pusta albo że pozostałe rekordy mają zapisane błędy generowania.
Nie jest samodzielnym dowodem pustego katalogu.

## 11. Eksporty i dokumentacja uzupełniająca

Rankingi, jakość i ML używają CSV z separatorem średnikowym i UTF-8 z BOM.
Raporty partii i podsumowanie archiwów używają przecinka oraz UTF-8 z BOM.
W razie nieprawidłowego podziału kolumn w arkuszu wybierz właściwy separator.

- [Indeks cech](FEATURE_INDEX.md): wersja, ograniczenia wyszukiwania, backfill.
- [Import wsadowy](BULK_IMPORT.md): limity i trwałość zapisów.
- [Magazyn źródeł](SOURCE_STORAGE.md): archiwum i integralność.
- [Benchmark](BENCHMARK.md): pomiary wykonywane poza interfejsem.

Instrukcja nie potwierdza zgodności wszystkich wariantów IES/LDT ani
skuteczności doboru zamienników. Widoki prezentują wyniki bieżących algorytmów
i dane źródłowe w zakresie opisanym powyżej.
