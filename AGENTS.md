# AGENTS.md — PhotometryLab

> Instrukcje dla agentów programistycznych (w szczególności OpenAI Codex) pracujących w tym repozytorium.
> Język komunikacji i interfejsu: polski. Nazwy API i plików w kodzie mogą pozostać angielskie.

## 1. Misja i kontekst naukowy

PhotometryLab to autorskie narzędzie badawcze w ramach pracy magisterskiej pt.:
**„Analiza porównawcza plików fotometrycznych różnych producentów z wykorzystaniem sztucznej inteligencji i implementacją autorskiego narzędzia informatycznego”**.

Cel: analizować i porównywać fotometrię opraw z plików IES/LDT, wyszukiwać podobne rozsyły, badać metody statystyczne i ML oraz umożliwić rzetelną ocenę skuteczności narzędzia. Wymagania i etapy pracy opisano w `docs/PROJECT_BRIEF.md` i `docs/ROADMAP.md`.

**To NIE jest certyfikowane oprogramowanie do projektowania oświetlenia i NIE jest automatyczny system doboru zamienników.** Podobieństwo kształtu rozsyłu nie dowodzi równoważności opraw. Wymagane są odrębne kryteria: strumień, moc, efektywność, barwa, gabaryty, montaż, warunki użytkowania i obliczenia oświetleniowe.

## 2. Stan kodu (v0.1, 2026-10-10)

- `app.py` — interfejs Streamlit: import, ranking, wykresy, katalog, eksploracja ML, eksport CSV.
- `photolab/models.py` — dataclass `Photometry` i walidacja.
- `photolab/parsers.py` — `load_photometry(...)`, obsługiwany podzbiór IES LM-63 type C (`TILT=NONE`) i EULUMDAT/LDT (`Isym` 0–4).
- `photolab/analysis.py` — wyrównanie rozsyłów do siatki C: 0–350° co 10°, gamma: 0–90° co 5°; interpolacja; normalizacja przez maksimum; ważone podobieństwo cosinusowe i RMSE; opcjonalne dopasowanie obrotu; przybliżony strumień dolny; PCA, KMeans i Isolation Forest.
- `photolab/demo.py`, `examples/DEMO_*` — **syntetyczne** dane do demonstracji i testów; nie są danymi producentów ani dowodami empirycznymi.
- `tests/` — testy jednostkowe oraz symulowany test interfejsu (w stanie wyjściowym 13 przechodzących testów).
- `requirements.txt`, `START_WINDOWS.bat`, `README.md` — zależności, uruchamianie i ograniczenia.

Przed zmianami przeczytaj README, istotne moduły i testy. Nie zakładaj obsługi formatów ani funkcji niewymienionych wyżej; najpierw zweryfikuj implementację.

## 3. Techniczne zasady niepodlegające negocjacjom

1. **Poprawność fizyczna przed UI i ML.** Każda istotna zmiana parsera, konwersji jednostek, symetrii, interpolacji, normalizacji, integracji po kącie bryłowym i rankingu wymaga testów numerycznych z wynikiem oczekiwanym.
2. **Nie maskuj nieobsługiwanych danych.** Nie ekstrapoluj brakującej fotometrii, nie dopisuj zer bez uzasadnienia, nie podmieniaj błędnego pliku domyślnym rozsyłem. Odmawiaj analizy z czytelnym błędem lub raportuj ograniczenie.
3. **Jawne jednostki i źródło danych.** Rozróżniaj `cd`, `cd/klm`, strumień lamp/źródeł, strumień oprawy i strumień dolnej półprzestrzeni. Nie przedstawiaj obliczonego przybliżenia jako deklaracji producenta.
4. **Dwa rodzaje podobieństwa.** Oddzielaj porównanie *kształtu rozsyłu* od wielokryterialnej oceny *potencjalnego zamiennika*; nie łącz ich w arbitralny „procent zgodności” bez definicji i kalibracji.
5. **Reprodukowalność badań.** Dokumentuj definicje metryk, zakres kątów, rozdzielczość siatki, sposób obrotu, parametry modeli, `random_state`, skład i pochodzenie zbioru danych, wersję kodu, ograniczenia oraz protokół eksperymentu.
6. **Dane prawdziwe vs syntetyczne.** Syntetycznych próbek używaj do testów, ale nie prezentuj jako walidacji na oprawach producentów. Prawdziwe dane muszą mieć udokumentowane pochodzenie i prawo do ich wykorzystania.
7. **Bezpieczeństwo danych.** Pliki od użytkownika traktuj jako niezaufane, ogranicz rozmiary i złożoność, nie uruchamiaj kodu z plików, nie wysyłaj danych do zewnętrznych usług bez zgody użytkownika.
8. **Zmiany minimalne, modularne.** Rozwijaj aktualny kod zamiast przepisywać wszystko. Nie dodawaj ciężkiej infrastruktury (mikroserwisy, płatne API, chmura, logowanie) bez wykazanej potrzeby i zatwierdzenia.
9. **Polska komunikacja, czytelny UX.** Komunikaty użytkownika i instrukcje mają być po polsku; algorytmy opisuj w sposób możliwy do późniejszego zacytowania i uzasadnienia w pracy.
10. **Nie wymyślaj wyników.** Nie twórz fikcyjnych benchmarków, ocen użytkowników, dokładności ML, certyfikacji normowej ani nazw producentów.

## 4. Styl pracy agenta

- Pracuj małymi, testowalnymi przyrostami. Nie poprawiaj od razu całego projektu.
- Zanim zaczniesz, sprawdź `git status` (jeśli projekt jest repozytorium) i uruchom testy wyjściowe.
- Przy większym zadaniu przedstaw krótki plan, następnie wykonaj pierwszy sensowny etap. Pytaj tylko, gdy odpowiedź wpływa na decyzję techniczną, zakres danych lub koszt.
- Każdą nową funkcję wesprzyj testem i krótkim uzasadnieniem merytorycznym. W szczególności dodawaj testy regresyjne do poprawianych błędów.
- Nie zmieniaj publicznych kontraktów funkcji bez konieczności; jeżeli to zrobisz, zaktualizuj wszystkich użytkowników funkcji i testy.
- Po zmianach uruchom `python -m pytest -q`; jeśli środowisko nie ma zależności, opisz, czego brakuje, zamiast twierdzić, że testy zaliczone.
- Na koniec każdej iteracji przedstaw: **co zmieniono**, **dlaczego**, **jak sprawdzono**, **ograniczenia/ryzyka**, **kolejny proponowany krok**.
- Utrzymuj aktualne: `README.md`, `docs/ROADMAP.md`; dla decyzji badawczych dopisuj uzasadnienie w dokumentacji.

## 5. Pierwsze zadanie po przejęciu projektu

**Audyt i wzmocnienie warstwy fotometrycznej, zanim rozbudujesz UI lub ML.**

1. Uruchom testy i sprawdź krytyczne reguły IES/LDT w kodzie i źródłach technicznych; nie zakładaj, że obecne 13 testów dowodzi zgodności z każdym wariantem formatów.
2. Sprawdź przede wszystkim: symetrię C, brzeg C=0/360, orientację i kompletność kątów, interpretację `cd/klm` i `cd`, metadane strumienia/mocy, zachowanie przy danych uszkodzonych, integralność wyników porównania przy różnych nazwach plików.
3. Dodaj najpierw kilka precyzyjnych testów regresyjnych i napraw **jedną** wysoko priorytetową słabość potwierdzoną testem. Nie deklaruj zgodności formatowej bez zestawu rzeczywistych plików referencyjnych.
4. Zaproponuj następny przyrost: raport jakości danych, import zbiorczy i trwałe identyfikatory/hash plików; dopiero później eksperymenty ML.

## 6. Uruchamianie

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m streamlit run app.py
```

macOS/Linux: użyj `python3 -m venv .venv` oraz `.venv/bin/python`.

Pamiętaj o `.gitignore`: nie commituj `.venv`, `__pycache__`, `.pytest_cache`, tajnych danych, danych producentów bez odpowiednich uprawnień ani dużych zbiorów roboczych.
