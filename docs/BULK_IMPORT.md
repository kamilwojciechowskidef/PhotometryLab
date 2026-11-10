# Import wsadowy

Aktualizacja interfejsu: w panelu bocznym zaznacz **Import and save ZIP files**.
Po wybraniu archiwów i opisaniu źródła przycisk **Import and save to catalogue**
rozpoczyna zapis. Sam wybór plików nie zapisuje ich do bazy. Podsumowanie z
błędami wymaga sprawdzenia; nie jest ogłaszane jako całkowity sukces.

## Zestawy produktów z ZIP i trwały katalog

Aktualizacja: przed importem ZIP uruchom migracje, w tym `006`:

```powershell
.venv\Scripts\python.exe -m photolab.database
```

Nowy importer archiwów zapisuje zestawy `IES/LDT + JSON + JPG/PNG`. Grupowanie
obejmuje **jedno archiwum i jedną ścieżkę bez rozszerzenia**: `a/item.ies`
i `a/item.json` należą do jednej grupy, a `b/item.ies` do innej. IES i LDT
są opcjonalne niezależnie w każdej grupie, choć całe archiwum musi zawierać
przynajmniej jedną fotometrię. Wspólna nazwa nie dowodzi równoważności
fotometrycznej ani globalnej tożsamości produktów między archiwami.

Obsługiwane są `.ies`, `.ldt`, `.json`, `.jpg`, `.jpeg`, `.png`. JSON musi być
obiektem UTF-8; jeśli zawiera `hash`, jego wartość musi odpowiadać nazwie pliku.
Rozszerzenia obrazów są sprawdzane po sygnaturze, a podgląd jest dodatkowo
dekodowany w ograniczonym rozmiarze. Przy błędnym JSON-ie, sygnaturze lub
niejednoznacznym typie w grupie archiwum jest odrzucane przed zapisem. Inne
wpisy są pomijane z powodem w raporcie partii. Poprzednie zabezpieczenia ZIP
i limity 500 wpisów, 5 MB/pliku i 100 MB archiwum pozostają aktywne.

Fotometrie są zapisywane dotychczasowym mechanizmem, a oryginalne bajty
wszystkich obsługiwanych plików w magazynie SHA-256. Nowe tabele
`zip_product_bundles` i `zip_bundle_assets` zachowują powiązania, nazwy, hashe
oraz JSON. JSON nie nadpisuje automatycznie marki i numeru odczytanych z IES/LDT;
konflikty i priorytety metadanych wymagają osobnej implementacji.

Zakładka **Saved catalogue** jest dostępna po uruchomieniu aplikacji i pokazuje
fotometrie zapisane w PostgreSQL, bez zaznaczania opcji w panelu bocznym.
Wybierz rekord i zaznacz **Show associated ZIP assets**, aby obejrzeć powiązane
pliki, JSON i jedno zdjęcie. Istniejące rekordy sprzed tej migracji nie dostają
automatycznie powiązań do sidecarów. Dla analiz wybór pliku z katalogu nadal
odbywa się przez **Browse saved catalogue**; centralny widok nie dodaje całej
bazy do bieżącej sesji.

**Ważne ograniczenie:** zapis fotometrii odbywa się w osobnych transakcjach,
przed transakcją powiązań ZIP. Awaria na tym etapie może zostawić fotometrię
bez powiązanych sidecarów; importer podaje numer partii do kontroli. Nie ma
jeszcze gwarancji dokładnie jednokrotnego importu. Przeglądarkowe ponowienie
tworzy nową partię i aliasy. Worker katalogowy ma checkpointy dla ukończonych
archiwów, lecz niepewne przerwania wymagają kontroli. Przed pełnym zbiorem
28 tys. ZIP-ów wykonaj pilotaż oraz pomiary czasu i pojemności.

Po deploymencie dane będą widoczne tylko wtedy, gdy aplikacja docelowa ma dostęp
do właściwej bazy PostgreSQL i trwałego katalogu `PHOTOLAB_ARTIFACT_DIR`.
`127.0.0.1` wskazuje komputer, na którym działa serwer aplikacji. Restart
kontenera lub serwera nie odtworzy plików z laptopa automatycznie. Kopie
zapasowe muszą obejmować zarówno bazę, jak i magazyn oryginałów.

Na czas zapisu powiązań importer ponownie oznacza partię jako `running`;
zakończenie powiązań i status końcowy są zatwierdzane w jednej transakcji.
Wąska przerwa między wcześniejszym zakończeniem importu fotometrii a ustawieniem
`running` nadal istnieje, więc status nie jest jeszcze gwarancją pełnego importu.

Istniejący interfejs importu wielu ZIP-ów i CLI `photolab.zip_import` korzystają
teraz z nowego importera. Migracja 006 jest sprawdzana przed rozpoczęciem
transakcji fotometrii. Limity i zachowanie przy przerwaniu opisane poniżej
nadal dotyczą pojedynczej partii.

## Wiele ZIP-ów

Uploader ZIP pozwala wybrać wiele archiwów. Łączny rozmiar uploadu jest
ograniczony do 500 MB; Streamlit przechowuje przesłane archiwa w pamięci.
Każdy ZIP tworzy osobną partię i zachowuje dotychczasowe limity 500 wpisów
oraz 100 MB po rozpakowaniu. Podsumowanie archiwów można pobrać jako CSV.

Dla dużego zbioru umieść ZIP-y w jednym lokalnym katalogu i uruchom:

```powershell
.venv\Scripts\python.exe -m photolab.zip_import "C:\dane\archiwa" --source "Opis pochodzenia danych" --recursive
```

Polecenie czyta jedno archiwum naraz i nie ma łącznego limitu rozmiaru zbioru.
`--recursive` obejmuje podkatalogi; bez niego przetwarzany jest tylko wskazany
katalog. Nadal obowiązuje limit pojedynczego ZIP-a: 100 MB skompresowane i
100 MB po rozpakowaniu, 500 wpisów oraz 5 MB na plik.

Worker zapisuje lokalne checkpointy SQLite obok magazynu oryginałów (domyślnie
`data/private/zip-import-checkpoints.sqlite3`). Klucz obejmuje rzeczywisty cel
PostgreSQL, bezwzględną ścieżkę i SHA-256 archiwum. Po ponownym uruchomieniu
pomija zakończone ZIP-y, kontynuując dalsze. W terminalu pokazuje postęp,
liczbę nowych, zduplikowanych i odrzuconych plików, ID partii oraz przyczynę
błędu. Brak archiwów jest błędem, nie pozornym sukcesem.

Status `running` lub `needs_review` oznacza niepewną operację: część danych
mogła już trafić do bazy. Worker nie ponawia jej automatycznie. Najpierw
zatrzymaj wszystkie workery i sprawdź historię importów, opis ścieżki i numer
partii/komunikat w terminalu. Dopiero po świadomej decyzji można użyć
`--retry-uncertain`; wznowienie może utworzyć kolejne aliasy i grupy ZIP.
`completed_with_errors` także wymaga przeglądu raportu, ale nie jest ponawiane.
Proces zwraca niezerowy kod, gdy zostały błędy lub archiwa wymagające kontroli.

Checkpointy nie obejmują importów wykonanych przed ich wprowadzeniem ani z
innego pliku checkpointu. Pierwszy przebieg tego workera może więc ponownie
przetworzyć wcześniejsze archiwa: SHA-256 rozpozna te same pliki, ale powstaną
nowe partie, aliasy i powiązania. Samo zmienienie opisu źródła nie powoduje
ponownego importu ukończonego archiwum. Przechowuj checkpoint na trwałym dysku;
po zmianie bazy lub zawartości ZIP-a będzie on traktowany jako nowe zadanie.
Nie uruchamiaj równolegle `--retry-uncertain` z innym aktywnym workerem.

Przed użyciem uruchom `python -m photolab.database` (migracja `004`).
Po restarcie Streamlit zaznacz `Import and save ZIP files` w panelu bocznym.
Wybierz wiele IES/LDT albo wiele ZIP-ów, opisz pochodzenie zbioru i kliknij
`Import and save to catalogue`. Automatyczne próbki demonstracyjne nie są importowane.

Limity: 500 wpisów ZIP lub plików, 5 000 000 bajtów na plik, 100 000 000
bajtów całej partii i rozpakowanego archiwum. ZIP jest czytany w pamięci,
bez wypakowywania ścieżek. Odrzucane są niebezpieczne ścieżki, dowiązania,
szyfrowanie, powtarzające się nazwy i nadmierny współczynnik kompresji.
Nieobsługiwane rozszerzenia oraz za duże pliki otrzymują wpis `skipped`.
Puste katalogi ZIP nie są plikami i nie trafiają do raportu.

Każda partia ma wspólne ID i opis źródła. Każdy plik zapisuje się osobno:
oryginał w prywatnym magazynie, alias, raport jakości i poprawna fotometria
w PostgreSQL. Błędna fotometria ma wynik `rejected`, ale źródło zostaje
zarchiwizowane. Pole `duplicate` niezależnie informuje o istniejącym hashu.
Nazwy wpisów ZIP zachowują katalogi, dzięki czemu jednakowe nazwy bazowe
w różnych folderach nie kolidują.

Raport rozróżnia `new`, `duplicate`, `rejected`, `skipped`, `error`.
Historia dostępna przez `Show batch history` przetrwa restart aplikacji,
zawiera strony po 20 partii i pozwala pobrać raport CSV.

## Przerwanie importu

Raport jest zapisywany po każdym pliku. Awaria między zatwierdzeniem pliku
a zapisem raportu może pozostawić raport opóźniony względem katalogu.
Status `running` może oznaczać przerwaną partię — nie oznacza sukcesu.
Utrata możliwości zapisania raportu zatrzymuje przetwarzanie.
Ponowne kliknięcie importu w przeglądarce tworzy nową partię, a istniejące
źródła są rozpoznawane po SHA-256. Interfejs pozostaje zajęty podczas importu;
checkpointy opisane wyżej dotyczą wyłącznie workera katalogowego w terminalu.

Nie deklarujemy wydajności dla 28 tys. archiwów bez benchmarku. Bezpieczeństwo magazynu i kopie
zapasowe opisuje [SOURCE_STORAGE.md](SOURCE_STORAGE.md).
