```markdown
# GEKO Turbulence Model Sweeper for CFX Ejector Simulations

This repository contains a lightweight, native-Python automation pipeline designed to streamline computational fluid dynamics (CFD) ejector simulations in **Ansys CFX**. The tool automates the generation of a parametric sweep matrix for Generalized Eddy-Viscosity (GEKO) turbulence model coefficients ($C_{MIX}$ and $C_{JET}$), and seamlessly submits these runs to an HPC cluster.

## 🚀 Key Features

- **No Dependency Hell:** Built entirely using Python's standard library (`os`, `sys`, `pathlib`). No need to install Pandas, openpyxl, or worry about virtual environments on restricted HPC clusters.
- **Smart File Management:** Uses absolute path referencing for heavy `.def` and `.res` master files. It completely eliminates file duplication and cluster storage quota bloat.
- **Dynamic CCL Injection:** Automatically generates CFX Command Language (`.ccl`) files to overwrite thermodynamic boundary conditions (Pressure, Enthalpy, Temperature) and turbulence settings at runtime.
- **Interactive SLURM Integration:** Intercepts the user before generation to prompt for the desired HPC queue (e.g., *express, normal, batch*), injecting the correct partition directly into the batch scripts.
- **Hot-Start Capability:** Includes a toggle to initialize all sweep variations from a common, pre-converged master `.res` file to drastically cut down on solver iterations.

## 📂 Expected Directory Structure

Since the `.gitignore` is heavily restricted to prevent tracking large CFX binaries, you must set up your HPC workspace like this before running the script:

```text
/Your_Workspace_Folder
├── automate_workflow.py         # Main script (from this repo)
├── GEKO_Ejector_LP4000.def      # Master mesh and physics definition
└── GEKO_Ejector_LP4000.res      # Master restart file (for initialization)
```

## 🛠️ Usage Guide

### 1. Configure the Script
Open `automate_workflow.py` in your preferred text editor (`nano`, `vim`, etc.) and adjust the configuration block at the top of the file:

```python
# --- TOGGLES ---
SUBMIT_JOBS = True          # Set to False to dry-run (generate folders without submitting)
USE_INITIAL_FILE = True     # Set to False to start from scratch without .res interpolation

# --- SWEEP MATRIX ---
c_mix_values = [0.0, 1.0, 1.5]
c_jet_values = [0.5, 0.9, 1.5]

# --- THERMODYNAMICS ---
exp_data = {
    "motive_p": 115.99814E5,
    "motive_h": 249695.4, 
    "motive_t": 296.88335,
    "suction_p": 34.9823E5,
    "suction_h": 430810.4,
    "suction_t": 273.29169,
    "outlet_p": 40.426818E5
}
```

### 2. Execute
Load your cluster's Python module (if required) and execute the script:
```bash
module load python
python3 automate_workflow.py
```

### 3. Select Queue
The terminal will display an interactive menu. Select the number corresponding to your desired HPC partition:
```text
=== HPC Queue Selection ===
Available Partitions:
  1. express      (Max Time: 12:00:00)
  2. normal       (Max Time: 5-00:00:00)
  3. batch        (Max Time: 14-00:00:00)
  4. validation   (Max Time: 2:00:00)

Enter the number of the partition you want to use: 
```

The script will automatically generate the directory tree, write the custom `.ccl` and `.sh` scripts, and submit the jobs to SLURM. 

## 🔜 Next Steps / Roadmap
- **Phase 2 (Post-Processing):** Implementing the `post_process_results()` function to automate the parsing of CFX `.out` files, extracting the final `OPMFRInSN` scalar (suction mass flow), and exporting to a master CSV.
- **Phase 3 (Batch Data Loading):** Scaling the single-point dictionary to iterate through a full experimental matrix via built-in CSV reading.

## 🤝 Contributing
If you are contributing to this repository, note that the `.gitignore` is heavily restricted to prevent tracking of CFX artifacts. If you add a new Python module, you will need to add an allowlist exception (`!new_script.py`) to the `.gitignore`.
```
