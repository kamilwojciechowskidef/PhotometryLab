# Indeks cech dla dużego katalogu

Migracja `005` tworzy `photolab.feature_sets`. Każda oprawa gotowa do porównania
otrzymuje przy imporcie niezmienną wersję cechy:

```text
shape-v1-c36-g19-maxnorm-weighted-canonical-lsh96
```

Cecha ma 684 wartości `float32`: siatka C 0–350° co 10° i gamma 0–90° co 5°.
Powstaje z tej samej interpolacji, normalizacji i wag kąta bryłowego co bieżący
cosinus oraz RMSE. Przed zapisem wybierana jest kanoniczna rotacja C. To pozwala
rozpoznać identyczny rozsył zapisany z obrotem układu współrzędnych.

Do szybkiego wskazania kandydatów zapisywanych jest osiem 12-bitowych koszyków
LSH, zdefiniowanych przez stały seed i wersję algorytmu. PostgreSQL używa ośmiu
indeksów B-tree. Wyszukiwanie pobiera rekordy pasujące do co najmniej jednego
koszyka, a następnie dokładnie oblicza istniejące RMSE i cosinus dla tej puli.
Koszyki są przybliżonym filtrem: nie stanowią dowodu, że najbliższa oprawa z
całej bazy zawsze zostanie odnaleziona. Recall i czas trzeba zmierzyć na
rzeczywistym zbiorze przed wykorzystaniem wyniku w pracy.

## Operacja dla 1,5–3 mln plików

Po migracji nowe importy tworzą cechę automatycznie. Dla opraw istniejących
przed migracją uruchamiaj worker poza Streamlit:

```powershell
.venv\Scripts\python.exe -m photolab.indexing --batch-size 200 --max-records 10000
```

Polecenie wykonuje małe transakcje i wypisuje postęp. Powtarzaj je przez
harmonogram zadań Windows, aż komunikat zakończenia będzie miał `examined=0`.
Nie uruchamiaj pełnej przebudowy wielomilionowej bazy z interfejsu Streamlit.

Niepoprawnie odtwarzalne rekordy trafiają do `feature_generation_errors` i nie
są automatycznie ponawiane. Najpierw napraw dane źródłowe, potem usuń konkretny
rekord błędu wyłącznie w kontrolowanej procedurze administracyjnej.

Minimalny rozmiar samych wektorów dla 3 mln rekordów to około 7,6 GiB
(`3_000_000 × 684 × 4`), przed narzutem PostgreSQL, indeksami i danymi
źródłowymi. Zaplanuj pojemność i wykonaj benchmark na kopii bazy przed importem
całego zbioru. Ta wersja nie dodaje `pgvector`; jego użycie wymaga osobnego
benchmarku, kalibracji recall i migracji.

W aplikacji wybierz oprawę referencyjną i użyj `Search indexed catalogue`.
Tabela podaje liczbę kandydatów ocenionych dokładnie. Wynik porównuje kształt
rozsyłu, nie stanowi automatycznego doboru zamiennika.
