import os
import sys
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
MASTER_DEF_FILE = "GEKO_Ejector_LP4000.def"
MASTER_RES_FILE = "GEKO_Ejector_LP4000.res"  # Common restart file
BASE_DIR = Path.cwd()
DOMAIN_NAME = "Ejector"

# TOGGLES
SUBMIT_JOBS = True          # Submit job immediately
USE_INITIAL_FILE = True     # Use common .res file as initial state

# ==========================================
# PARTITION SELECTION SYSTEM
# ==========================================
AVAILABLE_PARTITIONS = {
    "express": "12:00:00",
    "normal": "5-00:00:00",
    "batch": "14-00:00:00",
    "validation": "2:00:00"
}

def get_partition_choice():
    print("\n=== HPC Queue Selection ===")
    print("Available Partitions:")
    for i, (part, time_limit) in enumerate(AVAILABLE_PARTITIONS.items(), 1):
        print(f"  {i}. {part:<12} (Max Time: {time_limit})")
    while True:
        try:
            choice = input("\nEnter the number of the partition you want to use (or 'q' to quit): ")
            if choice.lower() == 'q':
                sys.exit(0)
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_PARTITIONS):
                sel = list(AVAILABLE_PARTITIONS.keys())[idx]
                print(f"-> Selected '{sel}' queue.\n")
                return sel
            else:
                print("Invalid number. Try again.")
        except ValueError:
            print("Please enter a valid number.")

# ==========================================
# TEMPLATES
# ==========================================

CCL_TEMPLATE = """
LIBRARY:
  CEL:
    EXPRESSIONS:
      IPPInMN = {motive_p} [Pa]
      IPHInMN = {motive_h} [J kg^-1]
      IPTInMN = {motive_t} [K]
      IPPInSN = {suction_p} [Pa]
      IPHInSN = {suction_h} [J kg^-1]
      IPTInSN = {suction_t} [K]
      IPPOut = {outlet_p} [Pa]
    END
  END
END

FLOW: Flow Analysis 1
  DOMAIN: {domain_name}
    FLUID MODELS:
      TURBULENCE MODEL:
        Option = GEKO
        Jet Coefficient = {c_jet}
        Mixing Coefficient = {c_mix}
      END
    END
  END
END
"""

BASH_TEMPLATE_BASE = """#!/bin/bash
#SBATCH --job-name="{job_name}"
#SBATCH --ntasks=64
#SBATCH --output="{job_name}-%j.log"
#SBATCH --partition={partition_name}
##########################

date
echo "SLURM_JOB_ID : "$SLURM_JOB_ID
echo "SLURM_JOB_NODELIST : "$SLURM_JOB_NODELIST
echo "SLURM_JOB_NUM_NODES : "$SLURM_JOB_NUM_NODES
echo "SLURM_NTASKS : "$SLURM_NTASKS
echo "working directory : "$SLURM_SUBMIT_DIR

MACHINES=$(srun hostname | sort | uniq -c | awk '{{ if ($2 ~ /-workload/) print $2 "*" $1; else print $2 "-workload*" $1 }}' | paste -s -d "," -)
echo $MACHINES

/mapr/danfoss4.com/apps/Ansys/v241/v241/CFX/bin/cfx5solve \\
-double \\
-size 1.0 \\
-par \\
-par-dist $MACHINES \\
-start-method 'Open MPI Distributed Parallel' \\
-def {master_def_path} \\
{initial_file_clause}-ccl {ccl_filename} \\
-name {job_name}
"""

def main():
    selected_partition = get_partition_choice()

    # Single GEKO combination
    c_mix_values = [1.0, 1.2]
    c_jet_values = [1.0]

    # Trial point data
    exp_point_name = "Point_1"
    exp_data = {
        "motive_p": 115.99814E5,
        "motive_h": 249695.4,
        "motive_t": 296.88335,
        "suction_p": 34.9823E5,
        "suction_h": 430810.4,
        "suction_t": 273.29169,
        "outlet_p": 40.426818E5
    }

    exp_dir = BASE_DIR / exp_point_name
    exp_dir.mkdir(exist_ok=True)

    master_def_path = (BASE_DIR / MASTER_DEF_FILE).absolute()
    master_res_path = (BASE_DIR / MASTER_RES_FILE).absolute()

    jobs_prepared = 0
    jobs_submitted = 0

    # Decide the -initial-file clause
    if USE_INITIAL_FILE:
        initial_clause = f"-initial-file {master_res_path} \\\n"
    else:
        initial_clause = ""

    for c_mix in c_mix_values:
        for c_jet in c_jet_values:
            folder_name = f"GEKO_CMIX_{str(c_mix).replace('.', '_')}_CJET_{str(c_jet).replace('.', '_')}"
            run_dir = exp_dir / folder_name
            run_dir.mkdir(exist_ok=True)
            ccl_filename = f"{folder_name}.ccl"

            ccl_content = CCL_TEMPLATE.format(
                motive_p=exp_data["motive_p"],
                motive_h=exp_data["motive_h"],
                motive_t=exp_data["motive_t"],
                suction_p=exp_data["suction_p"],
                suction_h=exp_data["suction_h"],
                suction_t=exp_data["suction_t"],
                outlet_p=exp_data["outlet_p"],
                c_mix=c_mix,
                c_jet=c_jet,
                domain_name=DOMAIN_NAME
            )
            with open(run_dir / ccl_filename, "w") as f:
                f.write(ccl_content)

            job_name = f"{exp_point_name}_{folder_name}"
            bash_content = BASH_TEMPLATE_BASE.format(
                job_name=job_name,
                partition_name=selected_partition,
                master_def_path=master_def_path,
                ccl_filename=ccl_filename,
                initial_file_clause=initial_clause
            )
            with open(run_dir / "run.sh", "w") as f:
                f.write(bash_content)

            print(f"Prepared directory: {run_dir.relative_to(BASE_DIR)}")
            jobs_prepared += 1

            if SUBMIT_JOBS:
                os.system(f"cd {run_dir.absolute()} && sbatch run.sh")
                jobs_submitted += 1

    print("\n--- Workflow Summary ---")
    print(f"Target Partition: {selected_partition}")
    print(f"Total runs prepared: {jobs_prepared}")
    if SUBMIT_JOBS:
        print(f"Total jobs submitted to '{selected_partition}' queue: {jobs_submitted}")

if __name__ == "__main__":
    main()