# Magazyn plików źródłowych

Przycisk zapisu w aplikacji archiwizuje oryginalne bajty (także plików odrzuconych),
a następnie zapisuje transakcję PostgreSQL. Domyślna lokalizacja to
`data/private/sources`, ignorowana przez Git. Opcjonalne ustawienie w `.env`:

```dotenv
PHOTOLAB_ARTIFACT_DIR=D:/PhotometryLab-private/sources
```

Zmienna środowiskowa ma pierwszeństwo. Ścieżki względne odnoszą się do katalogu
<<<<<<< HEAD
projektu. Katalog nie jest szyfrowany: dostęp regulują uprawnienia systemu.
=======
projektu. Katalog nie jest szyfrowany: ogranicz dostęp uprawnieniami systemu.
>>>>>>> origin/main
Zmiana lokalizacji wymaga przeniesienia całej zawartości magazynu.

Plik trafia pod `<pierwsze 2 znaki SHA-256>/<SHA-256>`. Nazwa użytkownika nie
wpływa na ścieżkę. Zapis publikuje gotowy plik przez dowiązanie twarde; system
plików musi je obsługiwać (np. lokalny NTFS). Duplikaty używają jednej kopii.
Uszkodzona kopia jest zgłaszana i nie jest nadpisywana. Limit wynosi 5 MiB.

W zakładce katalogu zaznacz `Browse source archive`. Wybierz plik, pobierz
oryginał albo wykonaj `Reparse source and preview quality`. Przed udostępnieniem
zawsze sprawdzane są SHA-256 i rozmiar. Ponowne parsowanie jest podglądem;
nie nadpisuje zapisanej fotometrii ani historycznego raportu.
Stare rekordy uzupełnia się przez ponowny import oryginalnego pliku.

## Awarie i kopie zapasowe

Baza i system plików nie mają wspólnej transakcji. Zapis pliku poprzedza zapis
bazy. Błąd bazy może pozostawić poprawny, niepowiązany artefakt: zachowujemy go,
a ponowienie importu wykorzysta tę samą kopię. Nie ma automatycznego czyszczenia.
Przerwanie procesu może pozostawić plik tymczasowy; nie jest on rekordem katalogu.

Przed kopią zapasową wstrzymaj importy. Wykonaj kopię PostgreSQL (np. pg_dump)
oraz całego katalogu źródeł. Odtwarzaj obie części, ustaw lokalizację magazynu
i sprawdź pobieranie kilku plików. Sama kopia bazy nie zawiera oryginałów.
Brakujący lub uszkodzony plik przywróć z zaufanej kopii; aplikacja zweryfikuje hash.
Nie zapisuj źródeł producentów w publicznym repozytorium.
