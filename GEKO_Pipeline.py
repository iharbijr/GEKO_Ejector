import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import re

# ==========================================
# DIRECTORY CONFIGURATION
# ==========================================
WINDOWS_DRIVE_PATH = Path(r"Z:\axSymm_Ejector")
LINUX_CLUSTER_PATH = "/mapr/danfoss4.com/home/ahmed_harbi/axSymm_Ejector"

# ==========================================
# GLOBAL CONFIGURATION
# ==========================================
MASTER_DEF_FILE = "GEKO_Ejector_axiSymm.def"
MASTER_RES_FILE = "GEKO_Ejector_axiSymm.res"
MASTER_CST_FILE = "GEKO_Ejector_axiSymm.cst"
DOMAIN_NAME = "Ejector"

USE_INITIAL_FILE = True

AVG_ITERATIONS = 1000
CV_THRESHOLD = 1.0
CFX_MONDATA_CMD = "/mapr/danfoss4.com/apps/Ansys/v241/v241/CFX/bin/cfx5mondata"
CFD_POST_CMD = "/mapr/danfoss4.com/apps/Ansys/v241/v241/CFD-Post/bin/cfdpost"
VAR_LIST = "'USER POINT,ME mass flow rate Inlet MN; USER POINT,ME mass flow rate Inlet SN; USER POINT,ME mass flow rate Outlet'"

AVAILABLE_PARTITIONS = {
    "express": "12:00:00",
    "normal": "5-00:00:00",
    "batch": "14-00:00:00",
    "validation": "2:00:00"
}

def get_partition_choice():
    print("\n=== HPC Queue Selection ===")
    for i, (part, time_limit) in enumerate(AVAILABLE_PARTITIONS.items(), 1):
        print(f" {i}. {part:<12} (Max Time: {time_limit})")
    while True:
        try:
            choice = input("\nEnter partition number: ")
            idx = int(choice) - 1
            if 0 <= idx < len(AVAILABLE_PARTITIONS):
                return list(AVAILABLE_PARTITIONS.keys())[idx]
        except ValueError:
            pass

# ==========================================
# HELPER FUNCTIONS FOR NEGATIVE VALUES
# ==========================================
def encode_val(val):
    """Converts float to string, replacing '.' and '-' with '_'
    Example: 1.2 -> '1_2', -1.2 -> '_1_2'"""
    return str(val).replace('.', '_').replace('-', '_')

def decode_val(s):
    """Converts the formatted string back to a float.
    Example: '1_2' -> 1.2, '_1_2' -> -1.2"""
    if s.startswith('_'):
        return -float(s[1:].replace('_', '.'))
    return float(s.replace('_', '.'))

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

BASH_SOLVER_TEMPLATE = """#!/bin/bash
#SBATCH --job-name="{job_name}"
#SBATCH --ntasks=64
#SBATCH --output="{job_name}-%j.log"
#SBATCH --partition={partition_name}

date
MACHINES=$(srun hostname | sort | uniq -c | awk '{{ if ($2 ~ /-workload/) print $2 "*"$1; else print $2 "-workload*"$1 }}' | paste -s -d "," -)

/mapr/danfoss4.com/apps/Ansys/v241/v241/CFX/bin/cfx5solve \
-double -size 1.0 -par -par-dist $MACHINES \
-start-method 'Open MPI Distributed Parallel' \
-def "{master_def_path}" \
{initial_file_clause}-ccl "{ccl_filename}" \
-name "{job_name}"
"""

CSE_TEMPLATE = """COMMAND FILE:
  CFX Post Version = 24.1
END
!$export_dir = "Figures";
!mkdir $export_dir unless -d $export_dir;

>hide /CONTOUR:P, view=/VIEW:View 1
>hide /CONTOUR:Mach, view=/VIEW:View 1
>hide /CONTOUR:v, view=/VIEW:View 1
>hide /CONTOUR:EV, view=/VIEW:View 1
>hide /CONTOUR:Entropy, view=/VIEW:View 1
>hide /CONTOUR:MFliquid, view=/VIEW:View 1
>hide /CONTOUR:MFvapor, view=/VIEW:View 1
>hide /CONTOUR:VFliquid, view=/VIEW:View 1
>hide /CONTOUR:RhoGrad, view=/VIEW:View 1

>show /CONTOUR:P, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_P.png
  White Background = On
END
>print
>hide /CONTOUR:P, view=/VIEW:View 1

>show /CONTOUR:Mach, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_Mach.png
  White Background = On
END
>print
>hide /CONTOUR:Mach, view=/VIEW:View 1

>show /CONTOUR:v, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_v.png
  White Background = On
END
>print
>hide /CONTOUR:v, view=/VIEW:View 1

>show /CONTOUR:EV, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_EV.png
  White Background = On
END
>print
>hide /CONTOUR:EV, view=/VIEW:View 1

>show /CONTOUR:Entropy, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_Entropy.png
  White Background = On
END
>print
>hide /CONTOUR:Entropy, view=/VIEW:View 1

>show /CONTOUR:MFliquid, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_MFliquid.png
  White Background = On
END
>print
>hide /CONTOUR:MFliquid, view=/VIEW:View 1

>show /CONTOUR:MFvapor, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_MFvapor.png
  White Background = On
END
>print
>hide /CONTOUR:MFvapor, view=/VIEW:View 1

>show /CONTOUR:VFliquid, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_VFliquid.png
  White Background = On
END
>print
>hide /CONTOUR:VFliquid, view=/VIEW:View 1

>show /CONTOUR:RhoGrad, view=/VIEW:View 1
HARDCOPY:
  Hardcopy Filename = $export_dir/{folder_name}_RhoGrad.png
  White Background = On
END
>print
>hide /CONTOUR:RhoGrad, view=/VIEW:View 1
"""

# NOTE: Removed SLURM headers to run purely on the login node sequentially.
BASH_POST_TEMPLATE = """#!/bin/bash
# Local post-processing execution on login node

echo "Starting CFD-Post rendering for {job_name}..."
{cfd_post_cmd} -batch render.cse -state "{master_cst_path}" -res "{res_file_name}"
echo "Rendering complete for {job_name}."
"""

# ==========================================
# PHASE 1: GENERATION & MASTER SUBMISSION SCRIPT
# ==========================================
def run_phase_1(exp_point_name, exp_data, c_mix_values, c_jet_values):
    selected_partition = get_partition_choice()

    exp_dir_win = WINDOWS_DRIVE_PATH / exp_point_name
    exp_dir_win.mkdir(parents=True, exist_ok=True)

    exp_dir_linux = f"{LINUX_CLUSTER_PATH}/{exp_point_name}"
    master_def_linux = f"{LINUX_CLUSTER_PATH}/{MASTER_DEF_FILE}"
    master_res_linux = f"{LINUX_CLUSTER_PATH}/{MASTER_RES_FILE}"
    master_cst_linux = f"{LINUX_CLUSTER_PATH}/{MASTER_CST_FILE}"

    initial_clause = f"-initial-file \"{master_res_linux}\" \
" if USE_INITIAL_FILE else ""

    master_submit_commands = ["#!/bin/bash", f"echo 'Submitting all solver jobs for {exp_point_name}...'"]

    for c_mix in c_mix_values:
        for c_jet in c_jet_values:
            folder_name = f"GEKO_CMIX_{encode_val(c_mix)}_CJET_{encode_val(c_jet)}"

            run_dir_win = exp_dir_win / folder_name
            run_dir_win.mkdir(exist_ok=True)
            run_dir_linux = f"{exp_dir_linux}/{folder_name}"

            ccl_content = CCL_TEMPLATE.format(
                motive_p=exp_data["motive_p"], motive_h=exp_data["motive_h"], motive_t=exp_data["motive_t"],
                suction_p=exp_data["suction_p"], suction_h=exp_data["suction_h"], suction_t=exp_data["suction_t"],
                outlet_p=exp_data["outlet_p"], c_mix=c_mix, c_jet=c_jet, domain_name=DOMAIN_NAME
            )
            with open(run_dir_win / f"{folder_name}.ccl", "w") as f: f.write(ccl_content)

            job_name = f"{exp_point_name}_{folder_name}"
            bash_content = BASH_SOLVER_TEMPLATE.format(
                job_name=job_name, partition_name=selected_partition,
                master_def_path=master_def_linux, ccl_filename=f"{run_dir_linux}/{folder_name}.ccl",
                initial_file_clause=initial_clause
            )
            with open(run_dir_win / "run.sh", "w", newline='\n') as f: f.write(bash_content)

            with open(run_dir_win / "render.cse", "w", newline='\n') as f: f.write(CSE_TEMPLATE.format(folder_name=folder_name))

            post_sh_content = BASH_POST_TEMPLATE.format(
                job_name=job_name,
                cfd_post_cmd=CFD_POST_CMD, master_cst_path=master_cst_linux, res_file_name=f"{job_name}_001.res"
            )
            with open(run_dir_win / "post.sh", "w", newline='\n') as f: f.write(post_sh_content)

            master_submit_commands.append(f"cd \"{run_dir_linux}\" && sbatch run.sh")

    master_submit_commands.append("echo 'All solver jobs submitted!'")

    master_script_path = exp_dir_win / "01_submit_all_solvers.sh"
    with open(master_script_path, "w", newline='\n') as f:
        f.write("\n".join(master_submit_commands) + "\n")

    print(f"\n✅ Phase 1 complete. Cases prepared at: {exp_dir_win}")

# ==========================================
# PHASE 2: GENERATE EXTRACT & POST-PROC SUBMIT SCRIPT
# ==========================================
def run_phase_2(exp_point_name):
    print(f"\n=== Scanning {exp_point_name} for finished .res files ===")
    exp_dir_win = WINDOWS_DRIVE_PATH / exp_point_name
    exp_dir_linux = f"{LINUX_CLUSTER_PATH}/{exp_point_name}"

    extract_script_path = exp_dir_win / "02_extract_monitors.sh"
    post_script_path = exp_dir_win / "03_run_all_post_local.sh"

    extract_commands = ["#!/bin/bash", "echo 'Starting batch monitor extraction...'"]
    post_commands = ["#!/bin/bash", "echo 'Running all CFD-Post jobs sequentially on login node...'"]
    count = 0

    for run_dir_win in exp_dir_win.glob("GEKO_CMIX_*_CJET_*"):
        if not run_dir_win.is_dir(): continue
        res_file_win = run_dir_win / f"{exp_point_name}_{run_dir_win.name}_001.res"

        if res_file_win.exists():
            run_dir_linux = f"{exp_dir_linux}/{run_dir_win.name}"
            res_remote = f"{run_dir_linux}/{exp_point_name}_{run_dir_win.name}_001.res"
            csv_remote = f"{run_dir_linux}/monitors.csv"

            cmd = f"{CFX_MONDATA_CMD} -res \"{res_remote}\" -varlist {VAR_LIST} -out \"{csv_remote}\""
            extract_commands.append(f"echo 'Extracting {run_dir_win.name}...'")
            extract_commands.append(cmd)

            # Changed from sbatch post.sh to bash post.sh
            post_commands.append(f"cd \"{run_dir_linux}\" && bash post.sh")
            count += 1

    extract_commands.append("echo 'All extractions complete!'")
    post_commands.append("echo 'All local post-processing jobs complete!'")

    if count > 0:
        with open(extract_script_path, "w", newline='\n') as f:
            f.write("\n".join(extract_commands) + "\n")
        with open(post_script_path, "w", newline='\n') as f:
            f.write("\n".join(post_commands) + "\n")

        print(f"✅ Generated Phase 2 scripts for {count} finished runs.")
        print(f"-> MobaXterm Action Required:")
        print(f"   Log in, cd to {exp_dir_linux}, and run:")
        print(f"   bash 02_extract_monitors.sh")
        print(f"   bash 03_run_all_post_local.sh")
    else:
        print("❌ No completed .res files found.")

# ==========================================
# PHASE 3: COMPILE PANDAS STATS
# ==========================================
def check_cv_flag(cv):
    if pd.isna(cv): return "ERROR"
    return "Stable" if cv <= CV_THRESHOLD else "Oscillatory"

def run_phase_3(exp_point_name):
    print("\n=== Phase 3: Compiling Master Stats ===")
    exp_dir_win = WINDOWS_DRIVE_PATH / exp_point_name
    results_data = []

    for run_dir_win in exp_dir_win.glob("GEKO_CMIX_*_CJET_*"):
        if not run_dir_win.is_dir(): continue

        match = re.search(r"GEKO_CMIX_(.*)_CJET_(.*)", run_dir_win.name)
        if not match: continue

        cmix_str, cjet_str = match.groups()
        c_mix = decode_val(cmix_str)
        c_jet = decode_val(cjet_str)

        csv_win = run_dir_win / "monitors.csv"

        if csv_win.exists():
            try:
                df = pd.read_csv(csv_win)
                total_iters = len(df)
                slice_size = min(total_iters, AVG_ITERATIONS)
                df_last = df.tail(slice_size)

                timestep_col = df.columns[0]
                monitor_cols = df.columns[1:]

                row_data = {"Run_Name": run_dir_win.name, "C_MIX": c_mix, "C_JET": c_jet}
                all_stable = True
                mn_mean, sn_mean = None, None

                plt.figure(figsize=(10, 6))

                for col in monitor_cols:
                    clean_name = col.replace("USER POINT,", "").strip()
                    mean_val = df_last[col].mean()
                    std_val = df_last[col].std()

                    cv_val = (std_val / abs(mean_val) * 100) if mean_val != 0 else np.nan
                    status = check_cv_flag(cv_val)
                    if status != "Stable": all_stable = False

                    row_data[f"{clean_name}_Mean"] = mean_val
                    row_data[f"{clean_name}_CV(%)"] = cv_val
                    row_data[f"{clean_name}_Status"] = status

                    if "MN" in clean_name: mn_mean = mean_val
                    if "SN" in clean_name: sn_mean = mean_val

                    plt.plot(df[timestep_col], df[col], label=clean_name, linewidth=1.5)

                if mn_mean is not None and sn_mean is not None and mn_mean != 0:
                    row_data["Entrainment_Ratio"] = abs(sn_mean) / abs(mn_mean)
                else:
                    row_data["Entrainment_Ratio"] = np.nan

                row_data["Run_Status"] = "Converged" if all_stable else "Review"

                plt.axvline(x=(total_iters - slice_size), color='r', linestyle='--', label='Start of Averaging')
                plt.title(f"Monitor Convergence: {run_dir_win.name}")
                plt.xlabel("Accumulated Timestep")
                plt.ylabel("Value")
                plt.legend()
                plt.grid(True, linestyle=':', alpha=0.7)
                plt.savefig(run_dir_win / "convergence_plot.png", dpi=300, bbox_inches='tight')
                plt.close()

                results_data.append(row_data)
                os.remove(csv_win)
                print(f"Processed: {run_dir_win.name} (CMIX: {c_mix}, CJET: {c_jet})")

            except Exception as e:
                print(f"Error parsing {run_dir_win.name}: {e}")

    if results_data:
        master_df = pd.DataFrame(results_data)
        master_df = master_df.sort_values(by=["C_MIX", "C_JET"])
        out_csv = WINDOWS_DRIVE_PATH / f"{exp_point_name}_Master_Stats.csv"
        master_df.to_csv(out_csv, index=False)
        print(f"\n✅ Stats compiled and saved to: {out_csv}")
    else:
        print("\n❌ No 'monitors.csv' files found.")

# ==========================================
# MAIN MENU
# ==========================================
def main():
    print("\n=== Master Batch Pipeline (Windows -> MobaXterm) ===")
    print(" 1. Generate Folders, Scripts & '01_submit_all_solvers.sh'")
    print(" 2. Generate '02_extract_monitors.sh' & '03_run_all_post_local.sh'")
    print(" 3. Compile Master Stats CSV & Plots on Windows")

    choice = input("\nSelect mode (1, 2, or 3): ")
    exp_point_name = "Point_1"

    if choice == '1':
        exp_data = {
            "motive_p": 115.99814E5, "motive_h": 249695.4, "motive_t": 296.88335,
            "suction_p": 34.9823E5, "suction_h": 430810.4, "suction_t": 273.29169,
            "outlet_p": 40.426818E5
        }
        c_mix_values, c_jet_values = [0.0], [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        run_phase_1(exp_point_name, exp_data, c_mix_values, c_jet_values)
    elif choice == '2':
        run_phase_2(exp_point_name)
    elif choice == '3':
        run_phase_3(exp_point_name)

if __name__ == "__main__":
    main()
