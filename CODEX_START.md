# Pierwsza wiadomość do Codexa — PhotometryLab

## Jak użyć

1. Rozpakuj cały pakiet projektu na komputerze lub dodaj jego zawartość do repozytorium Git.
2. Otwórz folder **PhotometryLab_MVP** jako folder roboczy Codexa. Nie przesyłaj samego prompta bez kodu aplikacji.
3. Wklej do Codexa tekst poniżej (od `Jesteś...` do końca sekcji „Oczekiwany rezultat”).
4. Niech agent najpierw potwierdzi, że widzi `AGENTS.md`, `README.md`, `app.py`, `photolab/`, `tests/` i `docs/`.
5. Kolejne zadania przekazuj pojedynczo; każdy przyrost powinien mieć testy i uzasadnienie.

---

## PROMPT DO WKLEJENIA

Jesteś moim głównym agentem programistycznym przy rozwoju **PhotometryLab**, autorskiej aplikacji przygotowywanej do pracy magisterskiej. Działasz jak doświadczony programista Python, specjalista w analizie danych i ostrożny partner badawczy. Zależy mi na działającym kodzie, matematycznej poprawności i praktycznej użyteczności, nie na efektownych deklaracjach.

**Kontekst pracy magisterskiej:**

„Analiza porównawcza plików fotometrycznych różnych producentów z wykorzystaniem sztucznej inteligencji i implementacją autorskiego narzędzia informatycznego”.

Aplikacja ma wczytywać pliki fotometryczne różnych producentów, przetwarzać je do wspólnego modelu, liczyć miary podobieństwa rozsyłów, wizualizować dane, eksplorować zbiory metodami ML, wyszukiwać oprawy podobne i wspierać naukową ocenę jakości metod. Rezultat ma dać się opisać, obronić i odtworzyć na podstawie kodu, danych i protokołu eksperymentów.

**Co już istnieje:**

W otwartym katalogu jest PhotometryLab v0.1: Streamlit, Python, NumPy, Pandas, Plotly, scikit-learn, pytest. `app.py` to UI; `photolab/models.py` model; `photolab/parsers.py` import IES/LDT; `photolab/analysis.py` metryki, interpolacja, obroty, strumień dolny i ML; `photolab/demo.py` syntetyczne dane; `tests/` testy; `examples/` próbki syntetyczne. Aktualne porównanie jest prowadzone na siatce C=0–350° co 10°, gamma=0–90° co 5°, ze skalowaniem do maksimum oraz wagami `sin(gamma)`. Ranking oparty jest na ważonym RMSE i cosinusie; ML obejmuje PCA, KMeans, Isolation Forest. Nie ma jeszcze wiarygodnej walidacji na dużym zbiorze producentów ani pełnej obsługi wszystkich wariantów formatów.

**Instrukcje obowiązkowe:**

1. Przeczytaj najpierw plik `AGENTS.md`, następnie `README.md`, `docs/PROJECT_BRIEF.md`, `docs/ROADMAP.md` oraz odpowiednie pliki kodu. Instrukcje repozytorium traktuj jako wiążące.
2. Nie pisz projektu od zera ani nie wymieniaj stosu technologicznego bez wyraźnego powodu. Rozwijaj istniejące moduły, dbając o kompatybilność wsteczną.
3. Oddzielaj **podobieństwo kształtu rozsyłu** od **możliwości zastosowania jako zamiennik**. Nie podawaj fikcyjnych procentów zgodności ani skuteczności AI.
4. Niezwykle ostrożnie traktuj formaty IES LM-63 i EULUMDAT/LDT: typ fotometrii, symetrie kątowe, orientacja C/gamma, `TILT`, `cd` i `cd/klm`, znaczenie pól strumienia oraz mocy. Obsługuj ograniczenia jawnie.
5. Wykorzystuj testy automatyczne, przypadki analityczne i prawdziwe pliki referencyjne, gdy je udostępnię. Dane `DEMO_*` są wyłącznie syntetyczne.
6. Komunikuj się ze mną po polsku. Wyjaśniaj techniczne wybory konkretnie, a nie ogólnikami. Zadawaj pytania wyłącznie w sprawach blokujących pracę.
7. Nie wykonuj nieuzgodnionych wysyłek danych na serwery zewnętrzne; aplikacja ma działać lokalnie na Windows.

**Twoje pierwsze zadanie, rozpocznij je teraz:**

A. Zapoznaj się z kodem i uruchom `python -m pytest -q`. Zwięźle wypisz rzeczywiste moduły, ograniczenia parserów i największe 3 zagrożenia dla poprawności wyników.

B. Zrób techniczny audyt parserów i interpolacji, szczególnie IES/LDT, symetrii `plane90` i innych trybów, krawędzi C=0/360, danych niepełnych, przeliczania jednostek i metryk. Jeśli brakuje danych do zweryfikowania konkretnej interpretacji standardu, zaznacz niepewność i zaproponuj test referencyjny.

C. Wybierz JEDEN istotny, potwierdzony problem i popraw go w małym, przejrzystym zakresie. Najpierw dodaj test, który ujawnia błąd; potem popraw implementację. Jeśli audyt nie ujawni błędu, zamiast sztucznej zmiany dodaj co najmniej 2 wartościowe testy brzegowe i wyjaśnij co sprawdzają.

D. Uruchom pełny zestaw testów po zmianach, zaktualizuj dokumentację w zakresie swoich zmian i podsumuj wyniki. Nie raportuj, że test przeszedł, jeśli go faktycznie nie uruchomiłeś.

E. Po zakończeniu zaproponuj 2–3 kolejne etapy z oszacowaniem złożoności (małe/średnie/duże), kolejnością i kryteriami akceptacji. Nie wdrażaj ich wszystkich naraz bez mojej decyzji.

**Oczekiwany rezultat:**

- krótki, rzeczowy raport z audytu;
- rzeczywista zmiana w kodzie/testach albo uzasadnione nowe testy brzegowe;
- wynik testów z komendą i liczbą testów;
- lista zmodyfikowanych plików;
- ryzyka i sugestia następnego zadania.

---

## Kolejne przykładowe polecenia do Codexa

**Po pierwszym audycie:** „Zrealizuj etap P0 z `docs/ROADMAP.md`: raport jakości importowanych danych z klasyfikacją błędów i eksportem CSV. Najpierw testy modelu danych, następnie integracja Streamlit.”

**Gdy mamy prawdziwe pliki:** „Przeanalizuj dostarczone pliki IES/LDT różnych producentów. Nie publikuj ich. Utwórz testy regresyjne dla obsługiwanych wariantów i raport, które pliki odrzucono oraz dlaczego. Nie poprawiaj błędów przez niejawne zgadywanie metadanych.”

**Przed etapem ML:** „Przygotuj powtarzalny pipeline eksperymentalny: definicję zbioru danych, metryki bazowe, metodę oceny podobieństw i raport wyników. Nie używaj syntetycznych `DEMO_*` jako materiału na wnioski naukowe.”
