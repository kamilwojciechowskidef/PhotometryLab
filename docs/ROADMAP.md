# Plan rozwoju PhotometryLab

Ten dokument definiuje proponowaną kolejność działań, a nie zadania wykonane. Aktualny stan wyjściowy: MVP 0.1, 13 testów automatycznych przechodziło 2026-10-10 w środowisku przekazania.

Aktualizacja dokumentacji (2026-10-10): w [README](../README.md) doprecyzowano normalizację, metryki, obrót, ranking, jednostki i ograniczenia walidacji zakresu C. Jest to opis obecnej implementacji, nie ukończenie audytu P0 ani potwierdzenie zgodności formatowej.

## P0 — jakość danych i poprawność obliczeń [NASTĘPNE]

Pierwszy przyrost: parser LDT odrzuca niepełne zakresy C dla `Isym=2/3/4`.
Dodano cztery przypadki regresyjne odrzucania brakujących granic oraz trzy
przypadki poprawnych nierównomiernych siatek, obejmujące odbicia i C=0/360°.
Próbki są syntetyczne; pozostały audyt i walidacja na plikach producentów
pozostają do wykonania.

- [ ] Audyt parserów IES/LDT i funkcji `sample()` w kontekście obsługiwanych symetrii, jednostek, kątów oraz błędów.
- [ ] Zestaw testów numerycznych: brak ekstrapolacji, przejścia kątowe C=0/360, rotacja, normalizacja, typowe i nietypowe siatki, referencyjny rozsył izotropowy i strumień analityczny.
- [x] Regresja LDT: kolejność danych `Isym=3` (C=270°→90°) oraz odmowa importu przy braku płaszczyzny brzegowej dla `Isym=2–4`.
- [x] Diagnostyka plików: klasyfikacja `poprawny`/`z ograniczeniami`/`niekompletny`/`nieobsługiwany`/`uszkodzony`, jawne ostrzeżenia oraz eksport raportu jakości do CSV.
- [ ] Posiadanie kilku **rzeczywistych** plików różnych producentów jako odrębnej bazy testowej z potwierdzonym prawem użycia; bez dodawania ich do publicznego repozytorium automatycznie.

**Warunek ukończenia:** poprawność kluczowych obliczeń potwierdzona testami i co najmniej kilkoma ręcznie zweryfikowanymi plikami referencyjnymi; wszelkie braki dokumentowane.

## P1 — katalog i przetwarzanie większej skali

- [x] Kod importu wielu plików/ZIP, wspólna partia, limity i historia raportów
  (migracja `004`); wymaga weryfikacji ręcznej w środowisku użytkownika.

- [x] Magazyn oryginałów według SHA-256, integracja importu, pobieranie,
  kontrola integralności i podgląd ponownego parsowania.

- [x] Przeglądarka PostgreSQL: filtry producenta/modelu, strony po 50 rekordów,
  wybór zapisanej fotometrii do porównania oraz rozróżnienie nazw w interfejsie.

- [x] Kod zapisu i odczytu natywnej fotometrii w PostgreSQL (migracja `003`),
  powiązanie z SHA-256 oraz integracja z ręcznym zapisem w Streamlit.
- [ ] Weryfikacja zapisu i odczytu fotometrii na rzeczywistej bazie testowej.

- [ ] Import wsadowy katalogów/ZIP (bezpiecznie, limity rozmiaru), raport błędów i deduplikacja po SHA-256.
- [ ] Rozdzielenie identyfikatora oprawy od nazwy pliku i producenta.
- [ ] Prosty trwały magazyn metadanych (np. SQLite), tylko gdy konieczny po pomiarze skali.
- [ ] Eksport cech i danych do CSV/Parquet z identyfikatorem źródła, wersją algorytmu i parametrami siatki.
- [ ] Benchmark wydajności od 100 do 1000+ plików; bez obietnicy wydajności bez testu.

**Warunek ukończenia:** powtarzalny import zbioru, statystyki jakości, brak cichych pominięć i zapisane pochodzenie danych.

## P2 — porównania fotometryczne

- [ ] Jawne alternatywy metryk (np. cosinus, RMSE, korelacja/Pearson z opisem ograniczeń); porównywalne warunki testu.
- [ ] Zbadać wrażliwość rankingu na siatkę, symetrię, orientację oprawy, szum danych i dopuszczalne obroty.
- [ ] Rozdzielić `shape similarity` od filtrów potencjalnych zamienników (metadane i wymagania użytkownika).
- [ ] Wizualizacja 3D lub pełnej bryły tylko przy poprawnie zdefiniowanych danych i kątach.

**Warunek ukończenia:** porównania weryfikowalne numerycznie i interpretowalne dla projektanta.

## P3 — uczenie maszynowe i eksperyment naukowy

- [ ] Hipotezy i protokół ewaluacji z punktami odniesienia (baseline).
- [ ] Zbiór danych producentów, opis klas/etykiet lub ekspercki zestaw istotnych podobieństw.
- [ ] Przegląd cech: surowa znormalizowana siatka, deskryptory rozsyłu, wybrane cechy fizyczne.
- [ ] Ocena KMeans/IsolationForest/PCA jako metod eksploracyjnych, alternatywnie inne metody, jeżeli uzasadnione.
- [ ] Precision@k, Recall@k lub inne adekwatne miary wyłącznie przy dostępnej prawdzie odniesienia; ocena stabilności modeli i czasu pracy.
- [ ] Reprodukowalny eksperyment z seed, konfiguracją, wersją kodu i zapisanymi wynikami.

**Warunek ukończenia:** wyniki porównujące metody na prawdziwych danych, analiza błędów i ograniczeń.

## P4 — finalizacja produktu i pracy

- [ ] Dopracowane komunikaty, instrukcja instalacji i eksport raportu porównawczego.
- [ ] Scenariusze testów użyteczności dla projektantów oświetlenia.
- [ ] Wykresy/tabele do rozdziałów pracy, metodyka, architektura, omówienie ograniczeń.
- [ ] Kontrola poprawności terminologii, źródeł, praw do danych i rzetelności wniosków.

**Warunek ukończenia:** odtwarzalna procedura od wejściowych plików po tabele/wykresy i wnioski w pracy magisterskiej.

## Notatka dla agenta

Nie zaczynaj fazy P3 od trenowania „zaawansowanej AI” na ośmiu próbkach `DEMO_*`. Największy zysk na tym etapie przyniesie rzetelna walidacja P0 i porządek w zbiorze P1.
