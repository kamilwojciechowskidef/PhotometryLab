# AGENTS.md — PhotometryLab

## Cel i architektura

PhotometryLab to lokalne narzędzie badawcze do analizy i porównywania rozsyłów
fotometrycznych z plików IES/LDT, rozwijane na potrzeby pracy magisterskiej.
Podobieństwo kształtu nie potwierdza równoważności opraw; aplikacja nie jest
certyfikowanym programem do projektowania oświetlenia ani automatycznym
systemem doboru zamienników.

- `app.py` — interfejs Streamlit: katalog, wybór plików, jakość, porównanie i ML.
- `photolab/models.py`, `parsers.py`, `quality.py` — model danych, ograniczona
  obsługa IES LM-63 Type C z `TILT=NONE` i EULUMDAT/LDT oraz raport jakości.
- `photolab/analysis.py`, `diagnostics.py`, `diagnostics_ui.py` — obliczenia,
  porównanie rozsyłów, diagnostyka i wykresy pojedynczej oprawy.
- `photolab/database.py`, `storage.py`, `artifacts.py` i `database/migrations/`
  — PostgreSQL, zapis fotometrii i lokalne archiwum oryginałów.
- `photolab/bulk.py`, `zip_products.py`, `zip_import.py`, `import_worker.py` —
  ograniczony import wsadowy i ZIP; worker ma lokalny checkpoint wznowienia.
- `photolab/features.py`, `indexing.py` — wersjonowane cechy i wyszukiwanie
  kandydatów; `tests/` zawiera testy, a `docs/` dokumentację projektu.

Stos: Python 3.10+, Streamlit, NumPy, pandas, Plotly, scikit-learn, psycopg,
PostgreSQL i pytest; pełna lista zależności znajduje się w `requirements.txt`.

## Zasady zmian

- Przed pracą sprawdź `git status`, `README.md` oraz odpowiednie moduły i testy.
  Zachowuj istniejące zmiany użytkownika i sprawdzaj, czy nie działa importer.
- Wprowadzaj małe, modularne zmiany w obecnej architekturze. Nie dodawaj
  zbędnych zależności, infrastruktury ani zmian niezwiązanych z zadaniem.
- Zachowuj publiczne kontrakty; przy koniecznej zmianie zaktualizuj ich użycia,
  testy i właściwą dokumentację. Nie zakładaj obsługi wariantów formatów bez
  sprawdzenia implementacji i źródeł technicznych.
- Poprawność fizyczna ma pierwszeństwo. Zmiany parserów, jednostek, symetrii,
  interpolacji, normalizacji, integracji i rankingu wymagają testów numerycznych
  ze znanym wynikiem; dla błędów dodawaj testy regresyjne.
- Nie ekstrapoluj brakujących pomiarów ani nie maskuj błędnych lub
  nieobsługiwanych danych. Jawnie rozróżniaj `cd`, `cd/klm`, strumień źródła,
  oprawy i szacowany strumień dolny. Nie przedstawiaj szacunków jako danych
  producenta ani podobieństwa jako potwierdzenia zamienności.
- Dokumentuj metryki, parametry, pochodzenie zbioru i ograniczenia wyników.
  Dane syntetyczne służą testom i nie dowodzą zgodności z danymi producentów.
- Traktuj pliki użytkownika jako niezaufane; zachowuj limity importu. Nie
  wysyłaj danych na zewnątrz bez zgody ani nie umieszczaj w Git sekretów,
  `.env`, środowiska `.venv`, `zip/`, prywatnego magazynu i dużych danych.
  Nie czyść bazy, checkpointów ani archiwum podczas zwykłych testów.
- Komunikuj się po polsku; język interfejsu i treści dostosuj do wyraźnych
  ustaleń użytkownika. Nazwy API i plików mogą być angielskie.
- Aktualizuj `README.md`, `docs/ROADMAP.md` i dokumentację specjalistyczną,
  gdy zmiana wpływa na opisane zachowanie lub decyzje badawcze.

## Uruchamianie i testy

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m streamlit run app.py
```

Na macOS/Linux użyj `python3 -m venv .venv` i `.venv/bin/python`. Przed
zmianami uruchom testy wyjściowe, a po zmianach co najmniej testy właściwe dla
zakresu oraz `python -m pytest -q`; zgłoś brak zależności lub nieuruchomione
testy. Nie wykonuj migracji ani importu produkcyjnych danych jako testu bez
wyraźnego zakresu zadania. Sposób importu i ograniczenia opisuje
`docs/BULK_IMPORT.md`; konfiguracja PostgreSQL korzysta z `DATABASE_URL`.

W odpowiedzi podaj, co zmieniono, dlaczego, jak sprawdzono oraz istotne
ograniczenia i następny krok, jeżeli pozostaje potrzebny.
