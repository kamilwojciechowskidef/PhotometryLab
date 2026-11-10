# Import wsadowy

## Przygotowany worker katalogów producentów

`photolab.import_worker` przeszukuje podkatalogi, importuje jeden ZIP naraz
i zapisuje punkt wznowienia w lokalnym SQLite. Po ukończeniu ZIP-a ponowne
uruchomienie pomija go, jeżeli rozmiar i czas modyfikacji nie uległy zmianie.
Błędne ZIP-y są ponawiane; częściowo zapisane partie mogą pozostać w bazie.
Przerwanie po zapisaniu partii, lecz przed punktem wznowienia, również może
utworzyć ponowną partię i aliasy; fotometria jest deduplikowana po SHA-256.

Worker zapisuje JPG/JPEG/PNG i JSON w prywatnym magazynie, a ich nazwy, hashe
i identyfikator partii w tabeli `photolab.archive_assets` (migracja `006`).
Wspólna nazwa w ZIP-ie pozwala powiązać pliki, jednak obecny interfejs nie
wyświetla jeszcze zdjęć ani danych z JSON. Raport starego importu może oznaczać
te pliki jako `skipped`, ponieważ zapisuje je osobny etap workera. Pliki
odrzucone przez parser pozostają w raporcie; ukończony ZIP nie oznacza, że
każdy IES/LDT nadaje się do porównania.

Po wykonaniu kopii zapasowej i zastosowaniu migracji można sprawdzić niewielką
próbę, korzystając z osobnego checkpointu:

```powershell
.venv\Scripts\python.exe -m photolab.database
.venv\Scripts\python.exe -m photolab.import_worker "C:\Users\kamil\Downloads\ies_mass_data\zip" --source "Lokalne archiwa producentów" --checkpoint data\private\test-import.sqlite3 --limit 2
```

To polecenie faktycznie zapisuje dane w skonfigurowanej bazie. Docelowy import
uruchamia się bez `--limit`, z osobnym checkpointem. Po wyczyszczeniu bazy lub
magazynu trzeba użyć nowego checkpointu, gdyż poprzedni oznacza ZIP-y jako
ukończone. Zmiana rozmiaru lub czasu modyfikacji ZIP-a powoduje jego ponowny
import. Checkpoint nie wykrywa podmiany treści z zachowaniem obu tych wartości.
Nie uruchamiaj dwóch workerów z tym samym checkpointem. Nie usuwaj archiwów
źródłowych. Walidacja większego importu, obsługa awarii PostgreSQL, wydajność
przy 28 tys. ZIP-ów i podgląd zdjęć wymagają dalszego sprawdzenia.

## Wiele ZIP-ów

Uploader ZIP pozwala wybrać wiele archiwów. Łączny rozmiar uploadu jest
ograniczony do 100 MB; Streamlit przechowuje przesłane archiwa w pamięci.
Każdy ZIP tworzy osobną partię i zachowuje dotychczasowe limity 500 wpisów
oraz 100 MB po rozpakowaniu. Podsumowanie archiwów można pobrać jako CSV.

Dla dużego zbioru umieść ZIP-y w jednym lokalnym katalogu i uruchom:

```powershell
.venv\Scripts\python.exe -m photolab.zip_import C:\dane\archiwa --source "Opis pochodzenia danych"
```

Polecenie czyta jedno archiwum naraz i nie wymaga uploadu całego zbioru.
Przetwarza ZIP-y w podanym katalogu i podkatalogach producentów, zachowując
ścieżkę względną w opisie pochodzenia. Błąd archiwum zatrzymuje CLI;
ukończone partie pozostają zapisane. Automatyczne wznawianie kolejki nie jest
jeszcze dostępne. Ponowienie deduplikuje pliki, ale tworzy nowe aliasy i partie.

Przed użyciem uruchom `python -m photolab.database` (migracja `004`).
Po restarcie Streamlit zaznacz `Open batch import` na dole strony.
Wybierz wiele IES/LDT albo pojedynczy ZIP, opisz pochodzenie zbioru i kliknij
`Import batch`. Automatyczne próbki demonstracyjne nie są importowane.

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
Ponowne kliknięcie importu tworzy nową partię, a istniejące źródła są
rozpoznawane po SHA-256. Nie ma jeszcze automatycznego wznawiania ani
przetwarzania w tle. Interfejs pozostaje zajęty podczas importu.

To pierwszy zakres skali ograniczony do 100 MB; nie deklarujemy wydajności
dla większych zbiorów bez benchmarku. Bezpieczeństwo magazynu i kopie
zapasowe opisuje [SOURCE_STORAGE.md](SOURCE_STORAGE.md).
