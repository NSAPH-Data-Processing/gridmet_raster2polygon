#!/bin/bash
#
#SBATCH -p shared # partition (queue)
#SBATCH -c 12 # number of cores
#SBATCH --mem 64GB # memory per job
#SBATCH -t 0-02:00 # time (D-HH:MM)

# ===================
#module load python
#conda activate gridmet_raster2polygon

export PYTHONPATH="."
snakemake --cores 10