# Diagnostyka fotometryczna pojedynczej oprawy

## Schemat wiązki w kolejnych odległościach

W sekcji **Beam projection and axial illuminance** schemat pokazuje pięć
odległości wyznaczonych przez suwak, szerokość wybranego przekroju oraz
natężenie oświetlenia na osi. Domyślnie są to 2, 4, 6, 8 i 10 m. Granice
są projekcją promieni odpowiadających połowie maksymalnej światłości danego
przekroju, a luks obliczany jest jako I osiowe / d². Dla rozsyłu asymetrycznego
przekrój zachowuje przesunięcie względem osi. Okrągłe symbole i oznaczenie
średnicy stosowane są tylko dla symetrii obrotowej; same symbole są poglądowe.
Skale osi są niezależne. Nie jest to mapa natężenia ani kontur połowy
natężenia oświetlenia. Gdy brakuje granic, schemat może pokazać same luksy;
gdy brakuje przeliczenia na cd, wartości luksów są niedostępne. Strumień
z nagłówka nie musi być strumieniem oprawy, dlatego schemat go nie wyświetla.
Obliczenie zakłada źródło punktowe w polu dalekim; wiarygodność tego
przybliżenia wymaga osobnej oceny.

Stan: 10 listopada 2026 r. Wersja obliczeń:
`diagnostics-v1-native-linear-half-maximum`.

Nowa, czwarta zakładka **Photometric diagnostics** jest dostępna dla jednego
odczytanego pliku IES/LDT lub rekordu dołączonego przez **Browse saved catalogue**.
Wybór **Diagnostic luminaire** jest niezależny od wzorca w rankingu.
Obliczenia nie zmieniają katalogu PostgreSQL, parserów ani indeksu LSH.
Nie wymagają migracji bazy.

## 1. Wykres biegunowy i jednostki

Wykres przedstawia przekroje C0–C180 i C90–C270. γ=0° znajduje się na dole,
γ=180° u góry, γ=90° po obu stronach. Prawa połowa odpowiada C0/C90,
lewa C180/C270. Przeciwne płaszczyzny wykorzystują własne wartości;
asymetria nie jest zastępowana odbiciem jednej krzywej.

Kąty gamma pochodzą z natywnej siatki pliku. Brakujący zakres nie jest
uzupełniany ani domykany zerami. Dla pliku z gamma 20–90° widoczne pozostają
oddzielne łuki. Dla pliku 0–180° można obejrzeć dolną i górną półprzestrzeń.
Wartości w płaszczyznach C są interpolowane zgodnie z symetrią modelu.
Siatka okresowa C zaczynająca się poza 0° jest przesuwana lokalnie na potrzeby
próbkowania. Nie zmienia to zapisanych danych ani algorytmu rankingu.

Pole **Diagnostic intensity scale** udostępnia:

- **Absolute intensity [cd]** — wartości przemnożone przez dostępny `to_cd`;
- **Source units** — wartości i jednostkę modelu, np. cd/klm;
- **Normalized to native maximum** — wartości podzielone przez jedno maksimum
  całej natywnej macierzy. Oba przekroje zachowują wspólną skalę.

Nie wyznaczamy cd/klm przez dzielenie cd przez dowolną wartość strumienia
z nagłówka. Konwersja do cd wykorzystuje istniejącą interpretację parsera,
wraz z jej ograniczeniami. Przy braku `to_cd` opcja bezwzględna nie jest dostępna.

**Native sampled maximum** to największa zapisana próbka, a nie gwarancja
znalezienia maksimum rzeczywistej bryły. **One native maximum direction**
podaje jedną pozycję tego maksimum na natywnej siatce; przy symetrii lub
remisach maksimum może występować w wielu kierunkach. Zakres dotyczy całego
pliku, także górnej półprzestrzeni. Wykres nie obraca oprawy zgodnie z
ustawieniem rankingu **Align C rotation**.

## 2. Definicja szerokości FWHM

Podstawą jest połowa maksimum światłości w rozpatrywanym przekroju. Definicję
kąta wiązki przez 50% maksimum opisuje [IES — beam angle](https://ies.org/definitions/beam-angle/).
W aplikacji realizujemy ściśle określoną diagnostykę: szerokość dwóch stałych
przekrojów dolnej półprzestrzeni. Nie poszukujemy automatycznie optycznej osi
wiązki ani płaszczyzn największej i najmniejszej szerokości bryły.

Dla każdego przekroju:

1. Wymagamy pokrycia gamma od 0 do 90°.
2. Tworzymy podpisany kąt β: wartości z C180/C270 leżą po stronie ujemnej,
   wartości z C0/C90 po dodatniej. Zakres to −90° do +90°.
3. Zachowujemy wszystkie natywne węzły gamma wewnątrz zakresu, dodając granicę
   90° przez interpolację, jeżeli leży między próbkami. Nie przechodzimy na
   siatkę co 5° wykorzystywaną w rankingu.
4. Wyznaczamy połowę maksimum **danego przekroju dolnej półprzestrzeni**.
5. Sprawdzamy, czy wartości co najmniej połowy maksimum tworzą jeden spójny
   przedział. Kilka rozłącznych obszarów oznacza brak pojedynczego FWHM.
6. Przecięcia progu wyznaczamy liniowo między sąsiednimi próbkami.
7. FWHM = β_prawa − β_lewa. Obie granice i szerokość pokazujemy w tabeli.

Nie przypisujemy liczby, gdy rozsył jest zerowy, brakuje zakresu lub próg leży
poza dostępnymi kątami. Dla izotropowego przekroju nie da się wskazać przecięć
połowy maksimum. Dwa maksima połączone obszarem powyżej połowy maksimum
stanowią jedną obwiednię; wynik nie oznacza udowodnionej pojedynczej wiązki.

Wspólny kierunek γ=0° powinien mieć zgodne wartości we wszystkich C.
W pierwszej wersji tolerancja zgodności wynosi `rtol=1e-3`, `atol=1e-8`
w jednostkach źródłowych (porównanie do pierwszej płaszczyzny). Przy większej
rozbieżności pokazujemy osobne krzywe, lecz nie łączymy ich do FWHM i nie
obliczamy luksów na osi. Tolerancja jest decyzją implementacyjną, nie deklaracją
wymagania normowego. Przy zgodności przyjmujemy próbkę pierwszej płaszczyzny.

Gęste próbkowanie wyświetlania nie zwiększa dokładności pomiaru. Interfejs
podaje największy natywny krok gamma; szerokość wąskiej wiązki z rzadkiej siatki
może być niedokładna. Wyniki wymagają porównania z wiarygodnymi referencjami.

## 3. Projekcja wiązki na odległość

Suwak **Maximum axial distance [m]** wybiera maksymalną odległość 1–50 m.
Tabela i diagram używają pięciu równomiernych odległości od d_max/5 do d_max.
Domyślnie jest to 2, 4, 6, 8, 10 m.

Płaszczyzna odbiorcza jest prostopadła do γ=0° i odległa wzdłuż tej osi o d.
Dla każdej granicy FWHM wyznaczamy:

```text
x_lewa  = d · tan(β_lewa)
x_prawa = d · tan(β_prawa)
szerokość = x_prawa − x_lewa
```

Dla symetrycznej wiązki o kącie α daje to `2d · tan(α/2)`. Przy asymetrii
granice mają różne odsunięcia od osi; nie symetryzujemy ich. Jeśli wiązka jest
pochylona, obie granice mogą znajdować się po tej samej stronie osi.

Diagram pokazuje dwa przekroje granic w funkcji odległości. Nie przedstawia
okręgu lub elipsy plamy: dwie płaszczyzny nie wystarczają do określenia pełnej
obwiedni. Granica na ±90° nie ma skończonego rzutu — nie pokazujemy wtedy
szerokości w metrach. Są to rzuty kierunków o połowie **światłości**, nie
kontur połowy **natężenia oświetlenia** na płaszczyźnie.

### Czytelność wykresów i tabel

Wykresy mają własne jasne tło i ciemne opisy, niezależne od motywu Streamlit.
Diagram odległości zaczyna oś X od zera. Skale X i Y są niezależne, aby
wykorzystać szerokość ekranu: nachylenie linii na ekranie nie przedstawia
rzeczywistego kąta wiązki. Wartości geometryczne należy odczytywać z osi i tabel.

Etykieta **Sampled maximum** ma jednostkę w podpisie poniżej; **Peak direction**
podaje kolejno C / γ. **On-axis [cd]** pozostaje w kandelach niezależnie od
wybranej skali wykresu.

Tabele ekranowe zaokrąglają wartości do dwóch miejsc po przecinku i zachowują
braki jako puste komórki. Główna tabela odległości pokazuje luks na osi i dwie
szerokości; **Boundary positions — detailed table** rozwija podpisane pozycje
granic. Powody niedostępnego FWHM znajdują się pod tabelą szerokości.
Eksport CSV zachowuje niezaokrąglone wartości oraz statusy. Formatowanie nie
zmienia obliczeń ani nie oznacza dokładności pomiarowej do 0,01° czy 0,01 m.

## 4. Luks na osi

Jeśli istnieją zgodne próbki γ=0° i wiarygodne `to_cd`, wyznaczamy:

```text
I_axis [cd] = natywna światłość przy γ=0° · to_cd
E_axis [lx] = I_axis / d²
```

Podstawą jest [prawo odwrotności kwadratu odległości — IES](https://ies.org/definitions/inverse-square-law/).
Wynik dotyczy punktu na osi i powierzchni prostopadłej do niej, w modelu
punktowego źródła w dalekim polu. Nie jest średnią z całej plamy ani maksimum
na płaszczyźnie dla oprawy z pochyloną wiązką. Poza osią dochodzą zmiana
odległości, kierunku światłości i cosinus kąta padania.

Aplikacja nie weryfikuje, czy podana odległość spełnia założenie dalekiego
pola — zależy to od gabarytów i optyki oprawy. Nie uwzględnia odbić, przeszkód,
utrzymania ani oświetlenia od innych źródeł. Brak konwersji do cd pozostawia
puste wartości luksów, ale nie blokuje dostępnych wykresów kształtu i szerokości.
Zmiana skali wykresu na znormalizowaną nie zmienia luksów.

## 5. Eksport i odtwarzalność

Dostępne są trzy CSV (UTF-8 z BOM, separator średnik):

- `diagnostic_curves.csv`: cztery płaszczyzny C, gamma, światłość, jednostka;
- `diagnostic_fwhm.csv`: granice, szerokości i powody braku wyniku;
- `diagnostic_distances.csv`: odległości, luks na osi, granice i szerokości w m.

Każdy plik zawiera nazwę źródła i wersję algorytmu. Do eksperymentu należy
zachować też oryginalne źródło, jego SHA-256, wersję kodu i informacje o
pochodzeniu. Sam plik CSV z nazwą źródła nie stanowi pełnego manifestu badania.

## 6. Testy i dalsza walidacja

### Korekta syntetycznej próbki asymetrycznej (10 listopada 2026)

`DEMO_06_Asymmetry_IES.ies` w aplikacji (plik `examples/DEMO_06_Asymetria_IES.ies`
w repozytorium) opisuje obecnie wiązkę Gaussa odchyloną o 30° w kierunku C0.
Jej światłość jest funkcją odległości kątowej δ od osi wiązki:

```text
cos(δ) = cos(γ) cos(30°) + sin(γ) sin(30°) cos(C)
I = 780 · exp(−0,5 · (δ / 25°)²) cd
```

W obliczeniach trygonometrycznych kąty są przeliczane na radiany. Ten wzór
wynika z iloczynu skalarnego wektorów kierunkowych; na biegunach γ=0° i 180°
wynik nie zależy od C. Poprzednia próbka przesuwała gamma o wartość zależną
od C i naruszała tę własność. Był to błąd danych demonstracyjnych.

Maksimum pozostaje 780 cd przy C0/γ30°, a światłość na osi γ=0° wynosi
około 379,67 cd. Teoretyczne FWHM przekroju przez oś wiązki wynosi
`2√(2 ln 2) · 25° ≈ 58,87°`; wynik z pliku zależy dodatkowo od interpolacji
siatki co 10°. Sigma w nazwach innych próbek również nie jest kątem FWHM.

Poprawiono generator aplikacji oraz przykład w `examples`. Wcześniej zapisane
pliki i rekordy PostgreSQL nie są automatycznie zmieniane. Zmieniają się bajty
i hash nowo wygenerowanej próbki oraz wyniki benchmarków wykorzystujących ją.
Nie należy porównywać wyników eksperymentów z różnymi wersjami generatora
bez odnotowania wersji kodu. Zabezpieczenie niespójności osi pozostaje aktywne.

Testy syntetyczne sprawdzają m.in. znane kąty przecięć, niesymetryczne szerokości,
wiązki węższe niż krok rankingu, znane luksometryczne wartości I/d², konwersję
cd/klm, brak ekstrapolacji, horyzont, kilka lobów, niezgodną oś i symetrię C.
Test Streamlit przechodzi przez jedną oprawę i zmianę skali wykresu.

Pozostaje walidacja na plikach referencyjnych producentów oraz porównanie
rysunków w przeglądarce z ich dokumentacją. Nie wyciągamy z syntetycznych
testów wniosków o pełnej zgodności formatów ani dokładności fizycznego pomiaru.
