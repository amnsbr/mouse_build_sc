# Building mouse connectomes using Allen Mouse Brain Connectivity Atlas

This repository creates a Docker image for building regionalized mouse structural connectivity matrices from the [Allen Mouse Brain Connectivity Atlas](https://connectivity.brain-map.org/), using [mouse_connectivity_models](https://github.com/AllenInstitute/mouse_connectivity_models). The container is just a thin wrapper for the `mcmodels` Python package, and includes its (old) dependencies.

Published image: [`amnsbr/mouse_build_sc`](https://hub.docker.com/r/amnsbr/mouse_build_sc) (linux/amd64).

## Quick start

```bash
docker pull amnsbr/mouse_build_sc

mkdir -p output
# aba_ids.txt: one ABA structure ID per line
docker run --rm \
  -v "$(pwd)/output:/output" \
  -v "$(pwd)/example_aba_ids.txt:/aba_ids.txt" \
  amnsbr/mouse_build_sc \
  --output-dir /output \
  --outfile-suffix N78 \
  --excluded-experiments nathan \
  --aba-ids /aba_ids.txt
```

The image includes a pre-downloaded Allen cache at `/aba_cache`. To use your own cache instead:

```bash
-v "$(pwd)/aba_cache:/aba_cache"
```

On Apple Silicon, add `--platform linux/amd64` to `docker pull` and `docker run` if needed.

Singularity can also be used:

```bash
singularity pull docker://amnsbr/mouse_build_sc
```

Then run the container with:

```bash
singularity run mouse_build_sc.sif ...
```

## CLI options

| Flag | Required | Description |
|------|----------|-------------|
| `--aba-cache-dir` | no | Allen cache root (default: `/aba_cache`) |
| `--output-dir` | yes | Where CSV/JSON outputs are written |
| `--outfile-suffix` | yes | Suffix for output filenames |
| `--aba-ids` | no | File of ABA IDs; default = 292-region order used in Knox et al. 2018 |
| `--excluded-experiments` | no | `nathan`, `knox`, `none`, or path to ID list (default: `nathan`)* |
| `--model-option` | no | `standard` or `log` (default: `standard`) |
| `--save-weights-nodes` | no | Also write weights/nodes `.npz` files |

\* For more details on the excluded experiments, see the respective papers:

- `knox`: [Knox et al. 2018](https://doi.org/10.1162/netn_a_00066)
- `nathan`: [Nathan et al. 2026](https://doi.org/10.64898/2026.02.20.707091). Note that the `nathan` exclusion set also excludes the `knox` experiments.

> **⚠️ Warning**
>
> Using the `knox` exclusion set will not exactly reproduce the connectivity matrices published in Knox et al. 2018 (which are available [here](https://download.alleninstitute.org/publications/A_high_resolution_data-driven_model_of_the_mouse_connectome/)), because new experiments have been added to the dataset since then, and some experiments are no longer available (see [Nathan et al. 2026](https://doi.org/10.64898/2026.02.20.707091) for more details).

## Outputs

Written to `--output-dir`:

- `connection_density_<suffix>.csv`
- `connection_strength_<suffix>.csv`
- `normalized_connection_density_<suffix>.csv`
- `normalized_connection_strength_<suffix>.csv`
- `source_mask_params.json`
- `target_mask_params.json`

## Building the container

```bash
git clone --recurse-submodules https://github.com/amnsbr/mouse_build_sc.git
cd mouse_build_sc
bash build_container.sh
```

`build_container.sh` initializes the `mouse_connectivity_models` submodule and ensures `aba_cache/` exists before build; any contents are copied into the image at `/aba_cache`.