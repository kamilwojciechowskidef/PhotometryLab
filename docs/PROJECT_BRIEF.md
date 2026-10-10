# PhotometryLab — opis projektu i wymagania z tematu pracy

## Źródło zakresu

Uzgodniony z promotorem opis znajduje się w dostarczonym dokumencie `Temat_Pracy.docx` (nie jest automatycznie częścią tego repozytorium). Poniższe punkty są uporządkowanym streszczeniem wymagań; nie stanowią nowych zobowiązań ani zmiany tematu.

**Temat:** „Analiza porównawcza plików fotometrycznych różnych producentów z wykorzystaniem sztucznej inteligencji i implementacją autorskiego narzędzia informatycznego”.

**Cel:** opracowanie metod automatycznej analizy i porównywania charakterystyk fotometrycznych opraw z użyciem statystyki i sztucznej inteligencji; rezultatem ma być aplikacja ułatwiająca przetwarzanie dużych zbiorów i znajdowanie opraw o podobnych właściwościach.

**Ramowy zakres z opisu pracy:**

1. Analiza formatów plików fotometrycznych.
2. Zebranie dużego zbioru plików i pipeline przygotowania, ujednolicania, kontroli jakości oraz ekstrakcji cech.
3. Implementacja klasycznych metod matematycznych/statystycznych dla podobieństwa rozsyłów i korelacji.
4. Zbadanie metod AI/ML: wykrywanie nietypowych charakterystyk, grupowanie, wyszukiwanie podobnych rozsyłów i potencjalnych zamienników.
5. Stworzenie aplikacji z użytecznym interfejsem i wizualizacją danych.
6. Przeprowadzenie badań eksperymentalnych na zbiorze plików przy użyciu narzędzia.
7. Ocena praktycznej użyteczności, granic zastosowania i dalszego rozwoju.
8. Wnioski i podsumowanie.

## Co jest dziś implementowane

Wersja 0.1 zawiera podstawy pkt 1, 3, 4, 5, ale na uproszczonej siatce, ograniczonym podzbiorze plików i syntetycznych przykładach. Nie zrealizowano jeszcze pełnowartościowego zbioru do eksperymentów ani walidacji skuteczności na danych producentów (pkt 2, 6, 7).

## Zasady pracy badawczej

- Definiuj pytania badawcze, hipotezy, baselines oraz mierzalne metryki *przed* uruchomieniem eksperymentów.
- Porównuj co najmniej klasyczną metodę kształtu rozsyłu i uzasadnioną metodę ML, na tym samym zbiorze i uczciwym protokole.
- Raportuj parametry i rozrzut wyników, analizę błędów, opóźnienia/zużycie zasobów przy rosnącym rozmiarze bazy.
- Przy rankingach podobieństwa rozważ Precision@k, Recall@k (gdy istnieją oznaczone pary lub klasy referencyjne); bez danych prawdy odniesienia tych miar nie da się wiarygodnie oszacować.
- Nie przypisuj modelowi ML lepszej skuteczności bez pomiaru. Oddziel eksploracyjne grupowanie od nadzorowanej oceny trafności rekomendacji.
- Oceniaj oprawy w granicach porównywanych danych: normalizacja usuwa różnice skali, więc podobny rozsył nie oznacza równych natężeń oświetlenia.

## Decyzje wymagające danych od autora pracy

1. Próbka rzeczywistych plików IES/LDT różnych producentów i informacja o warunkach wykorzystania.
2. Oczekiwane zastosowanie: szukanie podobnego rozsyłu czy warunkowe szukanie pełnych zamienników (bardziej złożone).
3. Priorytet środowiska: aplikacja lokalna Windows (obecny kierunek) czy serwerowa aplikacja dla wielu użytkowników.

Dopóki brak decyzji, utrzymuj aplikację lokalną, badawczą, offline i opartą na porównaniu kształtów.
