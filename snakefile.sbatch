#!/bin/bash
#SBATCH -p hsph # partition (queue)
#SBATCH -c 6 # number of cores
#SBATCH --mem 40GB # memory per job
#SBATCH -t 1-01:00 # time (D-HH:MM)
#SBATCH -o logs/output/%j.out
#SBATCH -e logs/err/%j.err

# ===================

export PYTHONPATH="."
snakemake --unlock
snakemake --cores 4