# PhotometryLab — MVP version 0.1

A prototype application developed for a master's thesis: **“Comparative analysis of photometric files from different manufacturers using artificial intelligence and the implementation of an original software tool.”**

The application has a Polish interface and runs **locally**. It requires no account or external API. It imports IES (.ies) and EULUMDAT (.ldt) files, aligns luminous intensity distributions, displays similarity rankings and visualizations, and includes an experimental PCA, KMeans, and Isolation Forest module.

**Similarity in distribution shape does not establish luminaire equivalence.** PhotometryLab is a research prototype. It is not certified lighting design software or an automated replacement selection system.

## Project documentation

- [Magazyn źródeł i kopie zapasowe](docs/SOURCE_STORAGE.md) — konfiguracja,
  pobieranie oryginałów, integralność i ponowne parsowanie.

- [Project brief and requirements](docs/PROJECT_BRIEF.md) — thesis scope and research principles.
- [Development roadmap](docs/ROADMAP.md) — stages P0–P4 and completion criteria; auditing the photometric layer is the priority.
- [Target architecture and PostgreSQL plan](docs/ARCHITECTURE.md) — current state, storage model, and implementation order.
- [Agent instructions](AGENTS.md) — rules for working on code and documentation.
- [Initial task template](CODEX_START.md) — guidance for handing the project over to an agent.

## Quick start on Windows (PowerShell)

The easiest option is to extract the ZIP archive and double-click `START_WINDOWS.bat` (Python 3.10+ must be installed). Alternatively, run these commands from the project directory:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app.py
```

Open the address shown in the terminal, usually `http://localhost:8501`.

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

The application requires **Python 3.10 or later** and the libraries listed in `requirements.txt`. Installing or updating dependencies may require internet access. File analysis runs locally and requires no external API. `START_WINDOWS.bat` invokes the dependency installer on every launch; with an existing environment, you can run the Streamlit command above directly.

If `py -3` fails to launch the interpreter, check your Python installation and the `py` launcher. If `python` works, you can use `python -m venv .venv`. The remaining commands use the interpreter in `.venv` directly, so activating the environment is unnecessary.

## Current features

1. Import multiple files and report errors rather than silently skipping files.
2. Read IES LM-63 Type C files (`TILT=NONE`) and EULUMDAT LDT files (`Isym` symmetry codes 0–4).
3. Expand distribution symmetry and interpolate onto a common grid: C from 0° to 350° in 10° steps, γ from 0° to 90° in 5° steps.
4. Compare **distribution shape**, normalized to the maximum on the comparison grid, using cosine similarity and RMSE weighted by `sin(γ)`. Optional C rotation in 10° steps.
5. Luminaire rankings, C0/C90 curve plots, distribution heatmaps, and ranking export to CSV.
6. Exploratory PCA (2D), KMeans clustering, and optional anomaly flags using Isolation Forest (with at least 8 files).
7. Numerical estimates of downward luminous flux when intensities can be reliably converted to cd, kept separate from flux metadata.
8. Synthetic samples, including an LDT example, for checking application behavior and learning the interface.
9. A quality report that classifies every imported file as correct, limited, incomplete, unsupported, or damaged; it explicitly separates readiness for shape comparison from readiness for an absolute downward-flux estimate and can be exported to CSV.

## How the ranking works

Comparison covers only the lower hemisphere: C = 0–350° in 10° steps (36 planes), γ = 0–90° in 5° steps (19 angles). Luminous intensities are interpolated linearly using the symmetry stored in the data model. Each matrix is then divided by its own maximum **after interpolation onto this grid**. Normalization removes intensity scale differences; it does not compare luminaire flux or power.

For normalized values `x_i`, `y_i` and weights `w_i = sin(γ_i) / Σ sin(γ_i)`, summed over all grid points:

- Cosine similarity: `Σ(w_i x_i y_i) / sqrt(Σ(w_i x_i²) Σ(w_i y_i²))`; higher values indicate greater similarity, and 1 indicates matching vector directions.
- RMSE: `sqrt(Σ(w_i (x_i − y_i)²))`; lower values indicate smaller differences, and 0 indicates identical matrices.

These metrics are dimensionless and do not represent a percentage of luminaire equivalence. Weights at γ = 0° are zero. Discrete `sin(γ)` weights approximate solid-angle contributions; they do not exactly integrate individual grid cells.

With rotation alignment enabled, the candidate matrix is shifted along the C axis by 0–350° in 10° steps. The rotation with the lowest RMSE is selected, followed by the higher cosine similarity (using a numerical tolerance of `1e-12`). Ties retain the first rotation found. The reported angle describes the shift applied to the candidate data. Candidates are ranked by ascending RMSE, descending cosine similarity, and then filename.

## Units and luminous flux

- **IES:** the matrix is in `cd` after applying the `candela multiplier`. Header flux, when available, is stored as source luminous flux rather than verified luminaire luminous flux.
- **LDT:** the matrix is in `cd/klm`; conversion to `cd` uses the lamp count, lamp flux, and conversion factor fields. For multiple lamp sets, the code sums their reference fluxes and issues a warning. This interpretation requires verification against reference files. Shape comparison remains possible when the conversion scale is unavailable.
- **Estimated downward luminous flux:** a numerical approximation of the integral `I(C, γ) sin(γ) dγ dC` for γ = 0–90°, with angles in radians. The code uses trapezoidal integration on a grid with C steps of 5° and γ steps of 2.5°. The result in lumens is available when the gamma range is covered and conversion to `cd` is known. It is neither a manufacturer declaration nor the total luminaire luminous flux.

## Key limitations of version 0.1

- **The application does not automatically select equivalent replacements.** Similar distributions may have different flux, power, geometry, color characteristics, or mounting requirements. Replacing luminaires requires lighting design calculations and verification for the specific installation.
- Comparison is limited to the lower hemisphere, γ = 0–90°. The code rejects sampling outside the measured gamma range and distributions with no emission on the comparison grid. For LDT `Isym=2`, `Isym=3`, and `Isym=4`, it also requires the symmetry-defining boundary C planes (respectively 0–180°, 90–270°, and 0–90°); it does not infer missing boundary values by interpolation. This is not complete validation of every possible C grid or manufacturer extension.
- IES: only Type C (`photometric type = 1`) and `TILT=NONE`. `TILT=INCLUDE`, external TLT files, and Type A or B photometry are unsupported.
- LDT: the parser assumes the classical EULUMDAT structure. Manufacturer extensions and unusual lamp sets may require separate tests. Conversion from cd/klm to cd relies on lamp and flux fields whose quality must be verified.
- Header parameters do not automatically establish luminaire luminous flux. Power and flux should be checked against the product datasheet.
- PCA, KMeans, and Isolation Forest are **unsupervised learning** methods. They do not provide reliable classification guarantees or demonstrate the quality of similarity results. Validation on diverse real data is required.
- `DEMO_*` examples are **synthetic** and do not come from manufacturers. They must not serve as empirical evidence for thesis experiments.
- Imported files have a 5 MB limit. The local PostgreSQL catalogue stores photometry and quality reports, with filtering and comparison selection. Original bytes are archived locally by SHA-256. User accounts, CAD/DIALux integration and automatic deletion are not implemented.
- Results in the current interface are identified by filenames. The interface assigns distinct names when collisions occur, and the analysis layer still excludes candidates whose filename matches the reference filename. A future catalogue import will use the SHA-256 identifier instead.
- Support for symmetry codes in the parser does not prove full format compliance. Independent tests and real reference files are required.

## Proposed thesis experiments

The research dataset should contain real files from several manufacturers, with documented licenses or terms of use. Record each luminaire's functional category, symmetry, flux, power, manufacturer, type, and intended use. Manually assess proposed replacements as a reference.

Compare cosine similarity, RMSE, and justified ML methods on the same dataset using a protocol defined in advance. Euclidean distance is a proposed additional experimental metric, not a separate option in the current interface. Calculate Precision@k/Recall@k only when labels or expert judgments of relevant similarity are available. Measure computation time and the effects of grid resolution, rotation, symmetry, and data anomalies; document incorrect similarity results. Evaluating potential replacements requires separate criteria and labels.

Record data provenance and usage rights, code and library versions, and grid, normalization, and rotation settings. The current ML module uses `random_state=42`: PCA has 2 components, KMeans uses `n_init=10`, and Isolation Forest uses `n_estimators=100` and `contamination=0.15`. These settings describe the implementation, not validated research performance.

## Architecture

```text
app.py                 Streamlit UI
photolab/models.py     Photometric data model and validation
photolab/parsers.py    IES/LDT parsing
photolab/analysis.py   Interpolation, similarity, luminous flux, and ML
photolab/demo.py       Synthetic demonstration data generation
tests/                 Automated parser and metric tests
examples/              Exported IES/LDT examples
```

## Tests

Przeglądarka katalogu: zaznacz `Browse saved catalogue` w panelu bocznym.
Filtry producenta i modelu wyszukują fragment tekstu bez rozróżniania wielkości
liter. Strony zawierają do 50 pozycji z zapisaną fotometrią. Wybór pozycji
dołącza je do istniejących wykresów i rankingu; wybór dotyczy bieżącej strony
i filtrów. Plik obecny w zestawie jest rozpoznawany po SHA-256.
Wczytane pozycje otrzymują oznaczenie `[DB id]`, aby rozróżnić jednakowe nazwy.
Przeglądanie wymaga migracji do `003`; nie ma nowej migracji dla przeglądarki.

Trwała fotometria: migracja `003` dodaje tabelę `photolab.photometries`.
Uruchom `python -m photolab.database` przed zapisem z interfejsu.
Przycisk zapisu zachowuje teraz również natywne kąty, macierz, jednostki
i metadane oprawy. API `load_stored_photometry(url, file_id)` odtwarza model.
Starsze rekordy wymagają ponownego wgrania i zapisania pliku, aby uzupełnić
fotometrię. Zapis w interfejsie archiwizuje też oryginalne bajty w prywatnym magazynie.

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Linux/macOS:

```bash
.venv/bin/python -m pytest -q
```

Tests cover synthetic parser and calculation cases and a mocked Streamlit interface test. The interface test does not replace checking the application in a browser. Passing the test suite does not establish support for every IES/LDT variant or effectiveness on manufacturer data.

## Technical references used for the implementation

- [IES LM-63 format documentation and symmetry rules](https://web.mit.edu/4.455/software/lightscape/Docs/Lightscape%20User%20Guide.pdf).
- [EULUMDAT fields and data layout](https://docs.agi32.com/PhotometricToolbox/Content/Open_Tool/eulumdat_file_format.htm).
- [EULUMDAT symmetry reduction, encoding, and examples](https://github.com/123VincentB/eulumdat-py/blob/main/docs/eulumdat_format.md).

Technical documentation supports format implementation but does not replace obtaining access to the full standards when required for final compliance verification.
