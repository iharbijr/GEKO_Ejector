# Automated CFD Pipeline for GEKO Turbulence Tuning

This repository contains a fully automated, cross-platform pipeline designed to orchestrate Ansys CFX simulations for ejector performance tuning. The workflow utilizes the Generalized $k-\omega$ (GEKO) turbulence model to fine-tune mixing and jet shear layer coefficients ($C_{mix}$ and $C_{jet}$) against experimental entrainment ratios.

## Architecture: Hybrid Windows-to-Linux Mapped Drive
The pipeline is specifically engineered for environments where local development occurs on a Windows machine, but heavy computation is executed on a Linux-based HPC cluster. 

By mapping the HPC network drive to Windows (e.g., `Z:\`), Python executes locally to dynamically generate all required Linux bash scripts, Ansys Command Language (CCL) files, and CFD-Post session files (`.cse`) directly onto the cluster's file system.

## Pipeline Workflow

The script provides an interactive terminal menu with three distinct phases:

### Phase 1: Pre-Processing & Script Generation
Executes entirely on Windows to prepare the simulation matrix.
- Generates a nested directory structure based on the matrix of $C_{mix}$ and $C_{jet}$ values.
- Injects parametric thermodynamic boundary conditions and GEKO coefficients into `.ccl` templates.
- Writes SLURM `run.sh` files configured for parallel MPI execution.
- Generates a master `01_submit_all_solvers.sh` script to bulk-submit all cases to the cluster.

### Phase 2: HPC Execution & Monitor Extraction
Executed sequentially on the Linux Login Node (via SSH/MobaXterm).
- Once the solvers finish, Python scans the mapped drive to verify completed `.res` files.
- Generates `02_extract_monitors.sh`, which uses `cfx5mondata` to rapidly dump transient monitor data (mass flow rates) into `.csv` files.
- Generates `03_run_all_post_local.sh`, which sequentially launches CFD-Post in batch mode on the login node to render contour images based on the `.cse` templates.

### Phase 3: Statistical Post-Processing (Pandas)
Executes entirely on Windows, leveraging the local Python environment.
- **Data Ingestion:** Reads all extracted `monitors.csv` files.
- **Trailing Statistics:** Analyzes the final 1,000 iterations to compute Mean, Standard Deviation, and Coefficient of Variation (CV%).
- **Stability Flagging:** Automatically flags variables and runs as "Oscillatory" or "Converged" based on a strict 1.0% CV threshold.
- **Entrainment Ratio:** Automatically computes the ratio of Suction Nozzle to Motive Nozzle mass flow.
- **Visualizations:** Uses `matplotlib` to generate and save `convergence_plot.png` in every run folder, plotting mass flows against accumulated timesteps with a trailing average marker.
- **Data Aggregation:** Compiles all statistical data into a master `Master_Stats.csv` file for rapid engineering evaluation.

## Prerequisites
* **Windows (Local):** Python 3.8+, `pandas`, `numpy`, `matplotlib`.
* **Linux (HPC):** Ansys CFX 24.1 (`cfx5solve`, `cfx5mondata`), Ansys CFD-Post, SLURM workload manager.

## Usage
1. Configure `WINDOWS_DRIVE_PATH` and `LINUX_CLUSTER_PATH` at the top of the script.
2. Run `python axSymm_Ejector_Pipeline.py`.
3. Follow the 3-step prompt, toggling between Windows execution and MobaXterm bash executions as directed by the terminal output.

---
*Note: Negative GEKO coefficients are fully supported and are automatically parsed via regex, converting dashes to underscores in directory names to prevent Linux pathing errors.*
