#!/bin/bash
#
#SBATCH -p shared # partition (queue)
#SBATCH -c 6 # number of cores
#SBATCH --mem 12GB # memory per job
#SBATCH -t 1-01:00 # time (D-HH:MM)

# ===================
#module load python
#conda activate gridmet_raster2polygon

module load python/3.10.9-fasrc01
source activate gridmet_raster2polygon

export PYTHONPATH="."
snakemake --unlock
snakemake --cores 4