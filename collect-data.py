"""Collect data from ConceptNet."""
import requests
from tqdm import tqdm
import logging
from utils import write_json, read_json, read_yaml, write_csv
from collections import Counter
import random
import csv
import os
# for reproducibility
random.seed(42)

logging.basicConfig(
    level=os.environ.get('LOGLEVEL', 'INFO').upper(),
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)


class DataCollector():
    """Data (conceptnet) collector class."""

    def __init__(self, relation: str, raw_data_path: str, raw_data_stats_path: str,
                 semantic_knowledge_path: str, semantic_obs_path: str, weighting: bool,
                 num_repeat: int, episodic_factor: int, episodic_obs_path: str,
                 val_ratio: float, test_ratio: float, all_obs_path: str, final_data_path: str):
        """Data (conceptnet) collector class."""
        self.relation = relation
        self.relation_simple = self.relation.split('/')[-1]

        self.raw_data_path = raw_data_path
        self.raw_data_stats_path = raw_data_stats_path
        self.semantic_knowledge_path = semantic_knowledge_path
        self.semantic_obs_path = semantic_obs_path
        self.weighting = weighting
        self.num_repeat = num_repeat
        self.episodic_factor = episodic_factor
        self.episodic_obs_path = episodic_obs_path
        self.all_obs_path = all_obs_path
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.final_data_path = final_data_path

        logging.info(f"DataCollector object successfully instantiated!")

    def read_mscoco(self, path: str = './data/ms-coco-80-categories') -> list:
        """Return ms coco 80 object categories."""
        logging.debug(f"Reading {path} ...")
        with open(path, 'r') as stream:
            self.mscoco = stream.readlines()
        self.mscoco = [line.strip() for line in self.mscoco]
        self.mscoco = ['_'.join(foo.split()) for foo in self.mscoco]
        logging.info(
            f"Reading {path} complete! There are {len(self.mscoco)} object categories")

    def read_names(self, path: str = './data/top-human-names') -> list:
        """Read 20 names."""
        logging.debug(f"Reading {path} ...")
        with open(path, 'r') as stream:
            self.names = stream.readlines()
        self.names = [line.strip() for line in self.names]
        logging.info(
            f"Reading {path} complete! There are {len(self.names)} object categories")

    def get_from_conceptnet(self) -> None:
        logging.debug(f"retrieving data from conceptnet ...")

        self.raw_data = {}

        for object_category in tqdm(self.mscoco):
            self.raw_data[object_category] = []
            query = f'http://api.conceptnet.io/query?start=/c/en/{object_category}&rel={self.relation}'
            logging.debug(f"making an HTTP get request with query {query}")
            response = requests.get(query).json()

            logging.info(f"{len(response['edges'])} tails (entities) found!")
            for edge in tqdm(response['edges']):
                self.raw_data[object_category].append(
                    {'start': edge['start'],
                     'end': edge['end'],
                     'weight': edge['weight'],
                     'surfaceText': edge['surfaceText']})

        write_json(self.raw_data, self.raw_data_path)
        logging.info(
            f"conceptraw_data_path data retrieval done and saved at {self.raw_data_path}")

    def get_conceptnet_data_stats(self) -> None:
        """Get basic data statistics."""
        logging.info(f"getting conceptnet data stats ...")
        self.raw_data_stats = {'num_examples': {}}
        for key, val in self.raw_data.items():
            num_examples = len(val)
            self.raw_data_stats['num_examples'][key] = num_examples

        all_locations = [
            val_['end']['@id'].split('/')[-1] for key, val in self.raw_data.items() for val_ in val]
        self.raw_data_stats['num_locations_total'] = len(all_locations)
        self.raw_data_stats['num_unique_locations'] = len(set(all_locations))

        counts = dict(Counter(all_locations))
        counts = {key: val for key, val in sorted(
            counts.items(), key=lambda x: x[1], reverse=True)}

        self.raw_data_stats['location_counts'] = counts

        write_json(self.raw_data_stats, self.raw_data_stats_path)
        logging.info(
            f"conceptnet data stats saved at {self.raw_data_stats_path}")

    def create_semantic_knowledge(self) -> None:
        """Create semantic (factual) knowledge from the conceptnet data."""
        logging.info(f"creating semantic knowledge ...")
        self.semantic_knowledge = {}
        for key, val in self.raw_data.items():
            head = key
            self.semantic_knowledge[head] = {self.relation_simple: []}

            for val_ in val:
                tail = val_['end']['@id'].split('/')[-1]
                self.semantic_knowledge[head][self.relation_simple].append(
                    tail)

        write_json(self.semantic_knowledge, self.semantic_knowledge_path)
        logging.info(
            f"semantic knowledge saved at {self.semantic_knowledge_path} ...")

    def create_semantic_observations(self) -> None:
        """Create dummy semantic observations using 20 human names.

        10 male and 10 female names were used from here
        https://www.ssa.gov/oact/babynames/decades/century.html
        """
        logging.debug(f"Creating dummy semantic observations ...")
        self.data_weighted = []

        for key, val in self.raw_data.items():
            head = key

            for val_ in val:
                tail = val_['end']['@id'].split('/')[-1]
                weight = round(val_['weight'])

                if not self.weighting:
                    weight = 1
                for _ in range(weight):
                    self.data_weighted.append(
                        (head, self.relation_simple, tail))

        self.data_weighted = sorted(self.data_weighted)
        self.data_weighted = self.data_weighted * self.num_repeat

        random.shuffle(self.data_weighted)

        # Note that the observations are all semantic.
        self.obs_semantic = [(random.choice(self.names) + "'s " + head, edge, tail)
                             for head, edge, tail in self.data_weighted]

        write_csv(self.obs_semantic, self.semantic_obs_path)

        logging.info(
            f"dummy semantic observations saved at {self.semantic_obs_path}")

    def create_episodic_observations(self) -> None:
        """Create episodic observations based on semantic observations."""
        logging.debug(f"Creating dummy episodic observations ...")

        possible_locations = list(set(
            [loc for key, val in self.semantic_knowledge.items() for loc in val[self.relation_simple]]))
        possible_locations = sorted(possible_locations)
        self.obs_episodic = []

        for obs_s in self.obs_semantic:
            head_s = obs_s[0].split()[-1]
            assert obs_s[1] == self.relation_simple
            tail_s = obs_s[2]

            for _ in range(self.episodic_factor):
                while True:
                    location_random = random.choice(possible_locations)
                    if location_random not in self.semantic_knowledge[head_s][self.relation_simple]:
                        break
                self.obs_episodic.append(
                    (obs_s[0], self.relation_simple, location_random))

        write_csv(self.obs_episodic, self.episodic_obs_path)

        logging.info(
            f"dummy episodic observations saved at {self.semantic_obs_path}")

    def create_splits(self) -> None:
        """Create train, val, and test splits"""
        logging.debug(f"Creating train, val, and test splits ...")
        self.obs_all = self.obs_episodic + self.obs_semantic
        random.shuffle(self.obs_all)

        write_csv(self.obs_all, self.all_obs_path)
        self.data_final = {}
        self.data_final['test'] = self.obs_all[:int(
            len(self.obs_all)*self.test_ratio)]
        self.data_final['val'] = self.obs_all[int(len(
            self.obs_all)*self.test_ratio):int(len(self.obs_all)*(self.test_ratio + self.val_ratio))]
        self.data_final['train'] = self.obs_all[int(
            len(self.obs_all)*(self.test_ratio + self.val_ratio)):]

        assert (len(self.data_final['train']) + len(self.data_final['val']) + len(
            self.data_final['test'])) == len(self.obs_all)

        write_json(self.data_final, self.final_data_path)
        logging.info("Splitting train, val, and test splits is done!")


def main(**kwargs) -> None:
    """Collect data. See ./collect-data.yaml for the config."""
    dc = DataCollector(**kwargs)

    dc.read_mscoco()
    dc.read_names()
    dc.get_from_conceptnet()
    dc.get_conceptnet_data_stats()
    dc.create_semantic_knowledge()
    dc.create_semantic_observations()
    dc.create_episodic_observations()
    dc.create_splits()


if __name__ == "__main__":
    config = read_yaml('./collect-data.yaml')
    print("Arguments:")
    for k, v in config.items():
        print(f"  {k:>21} : {v}")

    main(**config)
