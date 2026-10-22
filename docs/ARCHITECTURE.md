# Architektura docelowa i stan integracji PostgreSQL

## Cel

PhotometryLab ma pozostać lokalną aplikacją badawczą, ale obsługiwać duży,
trwały katalog plików IES i LDT. Streamlit będzie warstwą interfejsu, a logika
importu, analizy i dostępu do danych pozostanie w modułach `photolab/`.

Podobieństwo rozsyłu jest wynikiem analizy kształtu. Nie jest automatycznym
doborem równoważnego zamiennika oprawy.

## Stan na 2026-10-22

### Co jest zaimplementowane

- Streamlit: import wielu plików, ranking, wykresy, katalog i eksploracja ML.
- Parser IES LM-63 Type C z `TILT=NONE` oraz ograniczony parser EULUMDAT LDT.
- Wspólna siatka porównawcza, normalizacja, ważony cosinus, RMSE, opcjonalny
  obrót C, przybliżony strumień dolny oraz PCA/KMeans/Isolation Forest.
- Wstępny raport jakości dla poprawnie sparsowanych plików: gotowość do
  porównania i niezależnie do obliczenia strumienia dolnego.
- Zależność `psycopg[binary]` i lokalny `DATABASE_URL` w `.env`.
- Migracje `001`–`005`, trwała fotometria, import wsadowy, magazyn źródeł oraz
  wersjonowany indeks cech LSH z dokładnym rankingiem końcowym.
- Benchmark syntetyczny indeksu i osobna diagnostyka PostgreSQL w trybie tylko
  do odczytu; oba raportują wyniki lokalnie i nie są walidacją na danych producentów.

### Co zostało zweryfikowane lokalnie

- Serwer PostgreSQL jest dostępny przez `DATABASE_URL`.
- Połączenie wskazuje bazę `postgres` i użytkownika `postgres`.
- Migracje katalogu i indeksu są dostępne w repozytorium; stan konkretnej bazy
  należy zawsze potwierdzać przez `python -m photolab.database` oraz benchmark
  read-only, zamiast wnioskować go z kodu.

### Czego jeszcze nie ma

- reprezentatywnego, legalnie pozyskanego zbioru danych producentów do pomiarów;
- benchmarku importu i indeksów na kopii bazy z docelowymi 1,5–3 mln plików;
- trwałej historii analiz lub wyników porównań;
- potwierdzenia recall i wydajności dla rzeczywistych kategorii opraw.

## Decyzja architektoniczna

Na obecnym etapie używamy bezpośrednio `psycopg`, nie `st.connection()`.
Streamlit wywołuje funkcje repozytorium, a nie buduje SQL ani nie zarządza
transakcjami. Takie podejście zachowuje jedną warstwę dostępu do danych dla
interfejsu, importu wsadowego i przyszłych eksperymentów.

`st.connection(..., type="sql")` jest poprawną alternatywą dla prostych
zapytaniach tabelarycznych, ale wymaga SQLAlchemy. Nie jest potrzebne do
pierwszej wersji katalogu, ponieważ `psycopg` już jest zależnością projektu i
pozwala jawnie kontrolować transakcje oraz zapis danych numerycznych.

Nie używamy w aplikacji roli superuser `postgres`. Przed pierwszym zapisem
należy utworzyć ograniczoną rolę aplikacyjną, np. `photolab_app`, z dostępem
wyłącznie do schematu aplikacji.

## Przepływ danych

```text
plik IES/LDT
  -> SHA-256 oryginalnych bajtów
  -> kontrola duplikatu w katalogu
  -> parser i raport jakości
  -> zapis metadanych oraz danych natywnych
  -> obliczenie wersjonowanej macierzy cech
  -> filtr kandydatów w PostgreSQL
  -> dokładne RMSE i cosinus w NumPy
  -> prezentacja wyniku w Streamlit
```

Brakujące lub nieobsługiwane dane są raportowane. Nie są ekstrapolowane ani
uzupełniane przed zapisem.

## Przechowywanie danych

Magazyn źródeł archiwizuje oryginalne bajty i uzupełnia `private_artifact_path`,
również przy ponownym imporcie. Konfigurację, zachowanie przy awariach i kopie
zapasowe opisuje [SOURCE_STORAGE.md](SOURCE_STORAGE.md). Nie wymaga nowej migracji.

Przeglądarka katalogu pobiera metadane stronami po 50 rekordów i filtruje je
na serwerze. Macierze są pobierane tylko dla wybranych pozycji. Wybór obejmuje
bieżącą stronę i filtry. Zapisane oprawy są dołączane do lokalnego porównania,
z deduplikacją względem SHA-256 plików w bieżącym zestawie. Nie są ponownie
zapisywane przy użyciu przycisku zapisu przesłanych plików.

Migracja `003` wprowadza tabelę `photometries` z jednym rekordem na `file_id`.
Wersjonowany dokument JSONB (wersja 1) zachowuje wszystkie pola modelu,
w tym natywną siatkę, macierz i jednostki. Nie zapisujemy znormalizowanej
siatki zamiast danych natywnych: pozwala to ponownie obliczać cechy.
Zapis następuje w transakcji importu. Duplikat uzupełnia brakujący rekord,
ale nie nadpisuje istniejącej fotometrii. Odczyt waliduje odtworzony model.
Starsze rekordy katalogowe wymagają ponownego przesłania pliku. Widok katalogu
oraz archiwum oryginalnych bajtów są już zaimplementowane w kolejnych przyrostach.

Oryginalne pliki producentów należy przechowywać w prywatnym lokalnym magazynie
poza Gitem, np. pod nazwą ich SHA-256. PostgreSQL powinien przechowywać hash,
rozmiar, pochodzenie, licencję, status jakości, metadane i dane potrzebne do
analizy. Takie rozdzielenie ogranicza rozmiar kopii zapasowych bazy oraz pomaga
respektować prawa do plików producentów.

Proponowane tabele pierwszej wersji:

| Tabela | Rola |
| --- | --- |
| `import_batches` | Kontekst i czas jednego importu. |
| `photometry_files` | SHA-256, rozmiar, format, ścieżka prywatnego artefaktu, pochodzenie i status jakości. |
| `file_aliases` | Oryginalne nazwy plików i relacja z konkretnym importem. |
| `photometries` | Metadane oprawy, jednostki, symetria i dane natywne. |
| `feature_sets` | Znormalizowana macierz cech oraz wersja algorytmu i siatki. |
| `comparison_runs` | Opcjonalna, odtwarzalna historia analiz i parametrów. |

`photometry_files.sha256` musi mieć ograniczenie `UNIQUE`. Ten sam hash nie
powinien tworzyć drugiej fotometrii, ale może mieć wiele aliasów i importów.

## Wydajność i skala

Docelowy katalog 1,5–3 mln plików wymaga indeksu cech, nie wczytywania całej
bazy do Streamlit. Migracja `005` zapisuje wersjonowane, ważone wektory kształtu
i osiem indeksowanych koszyków LSH. Indeks służy wyłącznie do ograniczenia
puli kandydatów; końcowy ranking nadal liczy istniejący algorytm RMSE/cosinus.
Szczegóły wymiaru, backfillu, ograniczeń recall i pojemności opisuje
[FEATURE_INDEX.md](FEATURE_INDEX.md).

Na początku wyszukiwanie przebiega przez filtr metadanych w SQL, a dokładny
ranking jest liczony istniejącymi funkcjami NumPy. To zapewnia zgodność z
zdefiniowanymi metrykami RMSE i cosinusową.

Nie dodajemy `pgvector` przed wykonaniem benchmarku. Przy większej skali może
on służyć wyłącznie do szybkiego wskazania kandydatów; końcowy ranking nadal
musi zostać obliczony dokładną, wersjonowaną metryką PhotometryLab.

## Kolejność implementacji

1. `feature/postgresql-foundation`
   - `photolab/database.py`, jawny health check, obsługa błędów bez ujawniania
     adresu lub hasła bazy;
   - pierwsza migracja SQL tworząca pusty schemat;
   - testy jednostkowe konfiguracji i kolejności migracji.

   Kod modułu i migracja są przygotowane w repozytorium. Ich wykonanie jest
   celowe i ręczne: `python -m photolab.database`. To polecenie może utworzyć
   wyłącznie schemat `photolab` oraz jego tabele w bazie wskazanej przez
   `DATABASE_URL`.

2. `feature/file-identifiers`
   - SHA-256 z oryginalnych bajtów — zaimplementowany przez `identify_file()`;
   - wykrywanie duplikatów oraz aliasów w jednym imporcie;
   - bez automatycznego usuwania plików.

3. `feature/catalogue-ingestion`
   - transakcyjny zapis pojedynczego pliku, jego SHA-256, aliasu i raportu jakości;
   - rejestr plików odrzuconych bez fałszowania ich danych.

   Zapis jest dostępny ręcznie w interfejsie Streamlit wyłącznie dla plików
   przesłanych przez użytkownika. Pliki demonstracyjne nie są zapisywane.

4. `feature/catalogue-search`
   - katalog PostgreSQL, filtry metadanych i porównanie referencji z
     kandydatami istniejącym algorytmem.

5. `feature/bulk-import`
   - bezpieczny import katalogów/ZIP, limity, postęp i kompletny raport błędów.

## Kryterium ukończenia pierwszego etapu

Migracja może być wielokrotnie uruchomiona bez uszkodzenia schematu. Aplikacja
potrafi sprawdzić połączenie z bazą bez zapisu. Nie zapisuje żadnej fotometrii,
dopóki użytkownik nie uruchomi jawnej funkcji importu katalogowego.

## Źródła techniczne

- Streamlit: [łączenie z PostgreSQL](https://docs.streamlit.io/develop/tutorials/databases/postgresql)
  oraz [`st.connection`](https://docs.streamlit.io/develop/api-reference/connections/st.connection).
- Psycopg: [pule połączeń](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).
- PostgreSQL: [indeksy GIN](https://www.postgresql.org/docs/current/gin.html).
