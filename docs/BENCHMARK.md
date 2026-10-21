# Benchmark indeksu cech

Moduł `photolab.benchmark` mierzy algorytm indeksu cech na danych
**syntetycznych**. Nie zapisuje rekordów do PostgreSQL i nie jest walidacją na
oprawach producentów. Jego zadaniem jest uzyskanie powtarzalnej informacji o
koszcie obliczeń cech oraz o zachowaniu puli kandydatów LSH względem pełnego
rankingu cosinusowego w kontrolowanym eksperymencie.

## Uruchomienie

```powershell
.venv\Scripts\python.exe -m photolab.benchmark --corpus-size 100000 --queries 20 --top-k 20 --output benchmark\run-100k
```

Generator tworzy dane partiami, więc nie przechowuje całego korpusu wektorów w
pamięci. Parametr `--seed` ma domyślnie stałą wartość. Wyniki są zapisywane jako
JSON (konfiguracja, rozmiary i podsumowanie) oraz CSV (wynik każdego zapytania).

`recall_at_k` to odsetek pierwszych `k` wyników pełnego rankingu, które trafiły
do puli kandydatów LSH. Nie jest to Recall@k zamienników ani miara jakości
fotometrii. Czas filtra kandydatów dotyczy obliczeń w pamięci, nie PostgreSQL.

## Co mierzyć przed importem 1,5–3 mln plików

Wykonaj też osobny eksperyment na kopii bazy z legalnie pozyskanymi plikami:
czas importu i generowania cech, rozmiar tabel `photometries` i `feature_sets`,
rozmiar ośmiu indeksów B-tree, czas zapytania kandydatów, obciążenie
dysku/CPU/RAM oraz recall wobec pełnego rankingu na oznaczonej próbce prawdziwych
danych. Nie uruchamiaj tego testu na produkcyjnym katalogu bez kopii zapasowej.
