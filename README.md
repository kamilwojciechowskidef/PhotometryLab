# PhotometryLab — wersja MVP 0.1

Prototyp aplikacji do pracy magisterskiej: **„Analiza porównawcza plików fotometrycznych różnych producentów z wykorzystaniem sztucznej inteligencji i implementacją autorskiego narzędzia informatycznego”**.

Aplikacja ma polski interfejs i uruchamia się **lokalnie**. Nie wymaga konta ani zewnętrznego API. Wczytuje pliki IES (.ies) i EULUMDAT (.ldt), ujednolica rozsyły, pokazuje ranking podobieństw i wizualizacje. Ma również eksperymentalny moduł PCA, KMeans i Isolation Forest.

## Szybki start w Windows (PowerShell)

Najprościej: rozpakuj ZIP i dwukrotnie kliknij `START_WINDOWS.bat` (wymagany zainstalowany Python 3.10+). Możesz też uruchomić ręcznie w folderze projektu:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Otwórz adres podany w terminalu, zwykle `http://localhost:8501`.

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

Do działania potrzebny jest **Python 3.10 lub nowszy**, połączenie z internetem jedynie podczas pierwszej instalacji bibliotek.

## Co już działa?

1. Import wielu plików, z zachowaniem informacji o błędach zamiast bezgłośnego pomijania plików.
2. Odczyt IES LM-63 typu C (z `TILT=NONE`), LDT EULUMDAT (symetrie `Isym` od 0 do 4).
3. Rozszerzanie symetrii rozsyłu, interpolacja do wspólnej siatki: C od 0° do 350° co 10°, γ od 0° do 90° co 5°.
4. Porównanie **kształtu rozsyłu** z normalizacją do maksimum danej oprawy: ważone przez `sin(γ)` podobieństwo cosinusowe i ważony RMSE. Opcjonalny obrót C co 10°.
5. Ranking opraw, wykresy krzywych C0/C90, mapa rozsyłu, eksport rankingu do CSV.
6. Analiza eksploracyjna PCA (2D), klasteryzacja KMeans i opcjonalne oznaczanie obserwacji nietypowych algorytmem Isolation Forest (od 8 plików).
7. Prosty obliczany numerycznie strumień dolny, jeśli da się wiarygodnie przeliczyć intensywności na cd; osobny od metadanych strumienia.
8. Syntetyczne próbki w tym przykład LDT, do weryfikacji działania i nauki interfejsu.

## Kluczowe ograniczenia wersji 0.1

- **Nie jest to automatyczny dobór pełnoprawnych zamienników.** Kształt rozsyłu może być podobny mimo innego strumienia, mocy, geometrii, barwy czy sposobu montażu. Ostateczne zastępowanie opraw wymaga projektu oświetleniowego i weryfikacji w warunkach konkretnej instalacji.
- Analiza porównawcza świadomie ogranicza się do dolnej półprzestrzeni γ=0–90°. Brakujące pomiary nie są sztucznie ekstrapolowane. Uplighty, pliki bez pokrycia tego zakresu i badania pełnej przestrzeni wymagają rozszerzenia algorytmu.
- IES: tylko typ C (`photometric type = 1`) i `TILT=NONE`. `TILT=INCLUDE` i zewnętrzne pliki TLT nie są obecnie obsługiwane. Nie ma obsługi fotometrii typu A i B.
- LDT: zakładana zgodność z klasyczną strukturą EULUMDAT. Różne rozszerzenia producentów i nietypowe zestawy lamp mogą wymagać osobnych testów. Przeliczenie cd/klm na cd opiera się na polach lamp/strumienia z pliku, których jakość wymaga sprawdzenia.
- Parametry uzyskane z nagłówka nie oznaczają automatycznie strumienia oprawy. Moc oprawy i strumień powinny być porównane z kartą katalogową.
- PCA, KMeans i Isolation Forest są metodami **uczenia nienadzorowanego**, a nie systemem niezawodnej klasyfikacji czy dowodem jakości podobieństwa. Potrzebna jest walidacja na rzeczywistych, zróżnicowanych danych.
- Przykłady `DEMO_*` są **syntetyczne** i nie pochodzą od producentów. Nie należy ich używać jako dowodu w wynikach eksperymentów magisterskich.
- Wczytywane pliki mają limit 5 MB; kod prototypu nie zawiera bazy danych, kont użytkowników, integracji CAD/DIALux ani deduplikacji po zawartości.

## Proponowane eksperymenty do magisterki

Wymagana baza badawcza: prawdziwe pliki kilku producentów, z uwzględnieniem licencji/warunków używania plików. Dla każdej oprawy odnotuj grupę funkcjonalną, symetrię, strumień, moc, producenta, typ i przeznaczenie. Ręcznie oceń próby zamiany jako punkt odniesienia.

Porównaj skuteczność: cosinus, RMSE, odległość euklidesowa oraz metody ML na różnych zestawach cech. Mierz Precision@k/Recall@k, czas obliczeń, wpływ rozdzielczości siatki, trybu obrotu, symetrii i anomalii danych. Dokumentuj także błędne zamienniki.

## Architektura

```text
app.py                 Streamlit UI
photolab/models.py     Model danych fotometrycznych i walidacja
photolab/parsers.py    Odczyt IES/LDT
photolab/analysis.py   Interpolacja, podobieństwo, strumień i ML
photolab/demo.py       Generowanie syntetycznych danych demonstracyjnych
tests/                 Automatyczne testy parserów i metryk
examples/              Eksportowane przykłady IES/LDT
```

## Testy

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Materiały techniczne, na których oparto implementację

- IES LM-63, dokumentacja formatu i reguł symetrii: https://web.mit.edu/4.455/software/lightscape/Docs/Lightscape%20User%20Guide.pdf
- EULUMDAT, charakterystyka pól i układu danych: https://docs.agi32.com/PhotometricToolbox/Content/Open_Tool/eulumdat_file_format.htm
- EULUMDAT, opis redukcji symetrii, kodowania i przykładów: https://github.com/123VincentB/eulumdat-py/blob/main/docs/eulumdat_format.md

Dokumentacja techniczna pomaga w implementacji formatu, ale nie zastępuje zakupu/uzyskania dostępu do pełnych norm, jeżeli wymaga tego ostateczna weryfikacja zgodności ze standardem.
