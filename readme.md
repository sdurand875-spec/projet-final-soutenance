# Video timing of the Illinois agility test

Master 1 IEAP – Université de Montpellier
Course: Python-R-Git (Denis Mottet) – Project 2026
Author: Sarah Durand

## Aim

Measure the time of an agility test (start and finish on the same line)
from a slow-motion smartphone video (240 fps), by manually selecting the
START and END frames, then study the relationship between the Illinois
test time and age in young ice hockey players (n = 20).

## Structure

```
├── main.ipynb            entry point (Python): video timing
├── main.qmd              entry point (R): statistical analysis
├── main.Rproj            RStudio project
├── sources/
│   └── video_timing.py   Python functions (video, window, CSV, anonymisation)
├── notebooks/
│   └── development.ipynb step-by-step development of the Python code
└── results/
    └── measures_anonymous.csv   anonymous results (P01 to P20)
```

## How to run

**Python** (`main.ipynb`): `pip install opencv-python numpy pandas`
- `MEASURE = False` (default): shows the anonymous results, no video needed.
- `MEASURE = True`: opens the measurement window (videos needed).

**R** (`main.qmd`): `install.packages(c("ggplot2", "rmarkdown"))`, then open
`main.Rproj` and click **Render**.

## Data and privacy

Videos and files containing names or birth dates are **not shared**
(personal data of minors). Only the anonymous file
`results/measures_anonymous.csv` (id, times, age, sex) is published.

## Use of AI

Part of the code was written with the help of Claude (Anthropic),
then read, tested and adapted by the author.

## Licence

MIT – see `LICENSE`.
