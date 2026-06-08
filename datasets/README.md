# Datasets

Drop these three CSV files in this folder. They are **gitignored** — never commit them.

## Required downloads

### 1. `smart_grid_stability_augmented.csv` — PRIMARY
Used for stability monitoring, telemetry analysis, transformer/grid behavior.

**Source (Kaggle):** https://www.kaggle.com/datasets/pcbreviglieri/smart-grid-stability

Steps:
1. Open the Kaggle link → click **Download** (you may need to sign in to Kaggle).
2. Unzip the archive.
3. Copy `smart_grid_stability_augmented.csv` into `datasets/`.

Expected shape: ~60,000 rows, columns include `tau1..tau4`, `p1..p4`, `g1..g4`, `stab`, `stabf`.

---

### 2. `household_power_consumption.csv` — ALTERNATIVE / household telemetry
Used for smart-meter anomaly detection and household-level consumption patterns.

**Source (UCI ML Repository):** https://archive.ics.uci.edu/dataset/235/individual+household+electric+power+consumption

Steps:
1. Open the UCI link → click **Download** → grab the `.zip`.
2. Unzip → the file inside is named `household_power_consumption.txt` (semicolon-separated).
3. Either:
   - Rename to `household_power_consumption.csv` and keep the `;` delimiter (our loader handles both), **or**
   - Re-save as CSV with comma delimiter.
4. Place in `datasets/`.

Expected shape: ~2 million rows over ~4 years; columns include `Date`, `Time`,
`Global_active_power`, `Global_reactive_power`, `Voltage`, `Global_intensity`,
`Sub_metering_1..3`.

---

### 3. `electric_power_consumption.csv` — ALTERNATIVE
Aggregated electric power consumption dataset (Kaggle mirror of UCI data).

**Source (Kaggle):** https://www.kaggle.com/datasets/uciml/electric-power-consumption-data-set

Steps: same as #1 — download → unzip → drop the CSV in `datasets/`.

---

## After downloading

Your `datasets/` folder should look like:

```
datasets/
├── README.md                              # this file
├── .gitkeep
├── smart_grid_stability_augmented.csv     # ← REQUIRED
├── household_power_consumption.csv        # ← REQUIRED
└── electric_power_consumption.csv         # ← REQUIRED
```

## Why all three?

| Capstone requirement | Dataset that supports it |
|---|---|
| Grid Stability Monitoring | `smart_grid_stability_augmented.csv` |
| Smart Meter Intelligence | `household_power_consumption.csv` |
| Power Consumption / Demand patterns | `electric_power_consumption.csv` |
| Telemetry anomaly correlation | all three (cross-correlated in STEP 8) |

## Common schema (after normalization in STEP 3)

The data loader unifies all three into a common schema with these key fields
(per the capstone requirement spec):

`voltage`, `current`, `power_consumption`, `transformer_status`, `outage_event`,
`region`, `demand_load`, `timestamp`, `grid_frequency`, `equipment_type`.

Missing fields are filled with sensible defaults (e.g. simulated `region` and
`transformer_status`) so all three CSVs flow through the same pipeline.

## Quick sanity check after downloading

```powershell
cd datasets
dir *.csv
# You should see all 3 files listed with sizes > 0
```
