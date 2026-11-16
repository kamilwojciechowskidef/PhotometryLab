# Marka i numer katalogowy

Pierwszy etap zapisuje numer katalogowy jako osobne, opcjonalne pole modelu
`catalogue_number`. W IES pochodzi wyłącznie z `[LUMCAT]`; w LDT z pola numeru
oprawy. `manufacturer` pozostaje marką lub producentem z pliku. Oryginalna
nazwa pliku i identyfikatory katalogu nie są zmieniane.

Listy wyboru w porównaniu i diagnostyce wyświetlają markę, numer katalogowy
lub dostępny opis oraz nazwę pliku dla rozróżnienia pozycji. Tabela jakości,
lokalny ranking oraz ranking kandydatów z bazy pokazują osobno markę i numer.
Filtr modelu w katalogu uwzględnia także nowe pole numeru katalogowego.

Fotometria jest zapisywana w istniejącym JSONB; nowe pole jest opcjonalne, więc
odczyt rekordów sprzed zmiany działa bez migracji SQL. W starszych rekordach
`luminaire` bywa numerem lub opisem, zależnie od zawartości źródła. Nie da się
rozstrzygnąć tego po samym polu: osobny numer jest wtedy niedostępny, a opis
pozostaje widoczny. Ponowny zapis duplikatu obecnie **nie aktualizuje** danych
fotometrii; potrzebny będzie osobny, kontrolowany backfill z oryginału.

Ten etap nie wczytuje JSON/JPG z ZIP-ów, nie łączy IES/LDT w jeden produkt i
nie zmienia dużych zbiorów w bazie. Osobny importer będzie musiał uwzględnić
źródło danych, niejednoznaczności oraz konflikty między JSON a fotometrią.
Przy dużej liczbie rekordów filtr `contains` nie ma gwarancji wydajności;
nie należy interpretować tego etapu jako gotowego wyszukiwania dla 3 mln plików.
