# Import wsadowy

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
