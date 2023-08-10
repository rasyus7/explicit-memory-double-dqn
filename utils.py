"""utility functions"""
import json
import logging
import os
import random
import shutil
from glob import glob
from typing import List

import numpy as np
import torch
import yaml

logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO").upper(),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def seed_everything(seed: int) -> None:
    """Seed every randomness to seed"""
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True


def read_json(fname: str) -> dict:
    """Read json"""
    logging.debug(f"reading json {fname} ...")
    with open(fname, "r") as stream:
        return json.load(stream)


def write_json(content: dict, fname: str) -> None:
    """Write json"""
    logging.debug(f"writing json {fname} ...")
    with open(fname, "w") as stream:
        json.dump(content, stream, indent=4, sort_keys=False)


def read_yaml(fname: str) -> dict:
    """Read yaml."""
    logging.debug(f"reading yaml {fname} ...")
    with open(fname, "r") as stream:
        return yaml.safe_load(stream)


def write_yaml(content: dict, fname: str) -> None:
    """write yaml."""
    logging.debug(f"writing yaml {fname} ...")
    with open(fname, "w") as stream:
        yaml.dump(content, stream, indent=2, sort_keys=False)


def argmax(iterable):
    """argmax"""
    return max(enumerate(iterable), key=lambda x: x[1])[0]


def get_duplicate_dicts(search: dict, target: list) -> List:
    """Find if there are duplicate dicts.

    Args
    ----
    search: dict
    target: target list to look up.

    Returns
    -------
    duplicates: a list of dicts or None

    """
    assert isinstance(search, dict)
    logging.debug("finding if duplicate dicts exist ...")
    duplicates = []

    for candidate in target:
        assert isinstance(candidate, dict)
        if set(search).issubset(set(candidate)):
            if all([val == candidate[key] for key, val in search.items()]):
                duplicates.append(candidate)

    logging.info(f"{len(duplicates)} duplicates were found!")

    return duplicates


def list_duplicates_of(seq, item) -> List:
    # https://stackoverflow.com/questions/5419204/index-of-duplicates-items-in-a-python-list
    start_at = -1
    locs = []
    while True:
        try:
            loc = seq.index(item, start_at + 1)
        except ValueError:
            break
        else:
            locs.append(loc)
            start_at = loc
    return locs


def rename_training_dirs(root_dir: str = "./training_results/"):
    old_dirs = []
    new_dirs = []
    for foo in glob(os.path.join(root_dir, "*")):
        bar = glob(os.path.join(foo, "*/*/*test*"))
        if len(bar) == 0:
            continue
        bar = bar[0]
        old_dir = "/".join(bar.split("/")[:-1])
        old_dirs.append(old_dir)
        hparams = read_yaml(os.path.join(old_dir, "hparams.yaml"))

        allow_random_human = hparams["allow_random_human"]
        allow_random_question = hparams["allow_random_question"]
        pretrain_semantic = hparams["pretrain_semantic"]
        varying_rewards = hparams["varying_rewards"]
        capacity = hparams["capacity"]["episodic"] + hparams["capacity"]["semantic"]
        question_prob = hparams["question_prob"]
        des_size = hparams["des_size"]
        seed = hparams["seed"]
        sync_rate = hparams["sync_rate"]

        new_dir = (
            f"training_results/"
            f"allow_random_human={allow_random_human}_"
            f"allow_random_question={allow_random_question}_"
            f"pretrain_semantic={pretrain_semantic}_"
            f"varying_rewards={varying_rewards}_"
            f"des_size={des_size}_"
            f"capacity={capacity}_"
            f"question_prob={question_prob}_"
            f"sync_rate={sync_rate}_"
            f"seed={seed}"
        )
        new_dirs.append(new_dir)
        os.rename(old_dir, new_dir)

    for foo in glob(os.path.join(root_dir, "*/lightning_logs")):
        if len(os.listdir(foo)) == 0:
            dir_to_delete = os.path.dirname(foo)
            shutil.rmtree(dir_to_delete)
