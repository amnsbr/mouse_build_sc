# Based on https://github.com/vik16nathan/allen_connectome_qc/blob/main/after_manual_qc/build_model_new_excluded.py
# at commit 1595d9d
from __future__ import division
import argparse
import logging
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/mouse_connectivity_models/paper/figures/model_comparison/")

import allensdk.core.json_utilities as ju

from mcmodels.core import VoxelModelCache, Mask
from mcmodels.models.voxel import RegionalizedModel
from mcmodels.regressors.nonparametric.kernels import Polynomial
from mcmodels.utils import padded_diagonal_fill

from helpers.model_data import ModelData
from helpers.error import VoxelModelError
from helpers.utils import get_structure_id, get_ordered_summary_structures

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXP_INPUT_DIR = os.path.join("/mouse_connectivity_models", "paper")
INPUT_JSON = os.path.join(EXP_INPUT_DIR, "input.json")
HYPERPARAM_DIR = os.path.join(
    EXP_INPUT_DIR, "figures", "model_comparison", "output"
)
KNOX_EXCLUDED = os.path.join(SCRIPT_DIR, "knox_excluded.txt")
NATHAN_EXCLUDED = os.path.join(SCRIPT_DIR, "nathan_excluded.txt")


def load_excluded_experiments(excluded_arg):
    if excluded_arg == "none":
        return []
    if excluded_arg == "knox":
        path = KNOX_EXCLUDED
    elif excluded_arg == "nathan":
        path = NATHAN_EXCLUDED
    else:
        path = excluded_arg

    if not os.path.isfile(path):
        raise IOError("Exclusion list not found: %s" % path)

    with open(path, "r") as f:
        return [int(line.strip()) for line in f if line.strip()]


def fit_structure(cache, structure_id, experiments_exclude, kernel_params,
                  model_option="standard"):
    data = ModelData(cache, structure_id).get_voxel_data(
        experiments_exclude=experiments_exclude)

    nw_kwargs = dict()
    if "shape" in kernel_params:
        nw_kwargs["kernel"] = Polynomial(**kernel_params)
    else:
        nw_kwargs["kernel"] = "rbf"
        nw_kwargs["gamma"] = kernel_params.pop("gamma")

    error = VoxelModelError(cache, data)
    return data, error.fit(**nw_kwargs, option=model_option)


def main(args):
    input_data = ju.read(INPUT_JSON)
    structures = input_data.get("structures")
    log_level = input_data.get("log_level", logging.DEBUG)
    logging.getLogger().setLevel(log_level)

    experiments_exclude = load_excluded_experiments(args.excluded_experiments)
    
    manifest_file = os.path.join(args.aba_cache_dir, input_data.get('manifest_file'))

    hyperparameter_json = os.path.join(
        HYPERPARAM_DIR, "hyperparameters-%s.json" % args.model_option
    )
    hyperparameters = ju.read(hyperparameter_json)

    cache = VoxelModelCache(manifest_file=manifest_file)
    structure_ids = [get_structure_id(cache, s) for s in structures]

    annotation = cache.get_annotation_volume()[0]
    cumm_source_mask = np.zeros(annotation.shape, dtype=np.int)

    offset = 1
    weights, nodes = [], []
    data = None
    for sid, sac in zip(structure_ids, structures):
        logging.debug("Building model for structure: %s", sac)

        data, reg = fit_structure(
            cache, sid, experiments_exclude, hyperparameters[sac],
            model_option=args.model_option)

        w = reg.get_weights(data.injection_mask.coordinates)

        ordering = np.arange(offset, w.shape[0] + offset, dtype=np.int)
        offset += w.shape[0]

        data.injection_mask.fill_volume_where_masked(cumm_source_mask, ordering)
        weights.append(w)
        nodes.append(reg.nodes)

    weights = padded_diagonal_fill(weights)
    nodes = np.vstack(nodes)

    permutation = cumm_source_mask[cumm_source_mask.nonzero()] - 1
    weights = weights[permutation, :]

    logging.debug("regionalizing voxel weights")
    if args.aba_ids is None:
        aba_ids = get_ordered_summary_structures(cache)
    else:
        if not os.path.isfile(args.aba_ids):
            raise IOError("ABA IDs file not found: %s" % args.aba_ids)
        aba_ids = np.loadtxt(args.aba_ids, dtype=np.int)

    source_mask = Mask.from_cache(cache, structure_ids=structure_ids, hemisphere_id=2)
    source_key = source_mask.get_key(structure_ids=aba_ids)
    ipsi_key = data.projection_mask.get_key(structure_ids=aba_ids, hemisphere_id=2)
    contra_key = data.projection_mask.get_key(structure_ids=aba_ids, hemisphere_id=1)
    ipsi_model = RegionalizedModel(
        weights, nodes, source_key, ipsi_key, ordering=aba_ids, dataframe=True)
    contra_model = RegionalizedModel(
        weights, nodes, source_key, contra_key, ordering=aba_ids, dataframe=True)
    get_metric = lambda s: pd.concat(
        (getattr(ipsi_model, s), getattr(contra_model, s)),
        keys=("ipsi", "contra"), axis=1)

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    outfile_suffix = args.outfile_suffix
    logging.debug("saving to directory: %s", output_dir)
    get_metric("connection_density").to_csv(
        os.path.join(output_dir, "connection_density_%s.csv" % outfile_suffix))
    get_metric("connection_strength").to_csv(
        os.path.join(output_dir, "connection_strength_%s.csv" % outfile_suffix))
    get_metric("normalized_connection_density").to_csv(
        os.path.join(output_dir, "normalized_connection_density_%s.csv" % outfile_suffix))
    get_metric("normalized_connection_strength").to_csv(
        os.path.join(output_dir, "normalized_connection_strength_%s.csv" % outfile_suffix))

    ju.write(os.path.join(output_dir, "target_mask_params.json"),
             dict(structure_ids=structure_ids, hemisphere_id=3))
    ju.write(os.path.join(output_dir, "source_mask_params.json"),
             dict(structure_ids=structure_ids, hemisphere_id=2))

    if args.save_weights_nodes:
        np.savez(
            os.path.join(output_dir, "weights_%s.npz" % outfile_suffix),
            weights=weights.astype(np.float32))
        np.savez(
            os.path.join(output_dir, "nodes_%s.npz" % outfile_suffix),
            nodes=nodes.astype(np.float32))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build regionalized structural connectivity matrices."
    )
    parser.add_argument(
        "--aba-ids",
        help="Text file with ABA IDs, one per line. "
        "If omitted, uses the 292-region ontological order.",
    )
    parser.add_argument(
        "--outfile-suffix",
        required=True,
        help="Suffix for output files, e.g. N78.",
    )
    parser.add_argument(
        "--model-option",
        choices=["standard", "log"],
        default="standard",
        help="Model option for hyperparameters and output naming.",
    )
    parser.add_argument(
        "--excluded-experiments",
        default="nathan",
        help="Exclusion list: 'none', 'knox', 'nathan', or path to a txt file "
        "with one experiment ID per line.",
    )
    parser.add_argument(
        "--aba-cache-dir",
        default="/aba_cache",
        help="Directory containing mcmodels_manifest.json and Allen data cache "
        "(default: /aba_cache).",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where output connectivity matrices are written.",
    )
    parser.add_argument(
        "--save-weights-nodes",
        action="store_true",
        help="Also save voxel weights and nodes as separate npz files.",
    )
    main(parser.parse_args())
