# SPDX-License-Identifier: Apache-2.0
import time

import ray
import torch
from torch.distributed import ReduceOp


@ray.remote(num_gpus=1)
class DPActor:

    def __init__(self, data_parallel_master_ip: str, data_parallel_port: int,
                 data_parallel_rank: int, data_parallel_size: int):
        self.data_parallel_master_ip = data_parallel_master_ip
        self.data_parallel_port = data_parallel_port
        self.data_parallel_rank = data_parallel_rank
        self.data_parallel_size = data_parallel_size
        self.counter = 0

    def stateless_init_dp_group(self):
        from vllm.distributed.utils import (
            stateless_init_torch_distributed_process_group)

        self.dp_group = stateless_init_torch_distributed_process_group(
            self.data_parallel_master_ip,
            self.data_parallel_port,
            self.data_parallel_rank,
            self.data_parallel_size,
            backend="gloo")

    def do_work(self):
        self.counter = 0
        for _ in range(10):
            val = self.counter * self.data_parallel_size \
                + self.data_parallel_rank
            tensor = torch.tensor([val], dtype=torch.int32, device="cpu")
            torch.distributed.all_reduce(tensor,
                                         op=ReduceOp.MIN,
                                         group=self.dp_group)
            aggregated_val = int(tensor.item())
            print("Got value ", aggregated_val, " from rank ",
                  self.data_parallel_rank)
            self.counter += 1
            # if self.data_parallel_rank == 0 and self.counter == 100:
            #     raise RuntimeError("failure")

    def resize(self, new_size: int):
        self.data_parallel_size = new_size


def main():
    """
    DP Coordinator/Controller
    """
    actors = []
    inits = []
    for i in range(2):
        dp_actor = DPActor.remote("127.0.0.1", 50000, i, 2)
        actors.append(dp_actor)
        inits.append(dp_actor.stateless_init_dp_group.remote())

    print("Created actors")
    ray.get(inits)
    print("Initialized actors")

    works = []
    for i in range(2):
        actors[i].do_work.remote()
    ray.get(works)
    print("Started workers")

    time.sleep(5)

    # Scaling up
    new_actor = DPActor.remote("127.0.0.1", 50000, 2, 3)
    print("Created new actor")

    resizes = [actor.resize.remote(3) for actor in actors]
    ray.get(resizes)
    print("Resized actors")

    new_group = actors + [new_actor]
    reinits = []
    for actor in new_group:
        reinits.append(actor.stateless_init_dp_group.remote())
    ray.get(reinits)
    print("Renitialized actors")

    works = []
    for actor in new_group:
        works.append(actor.do_work.remote())
    ray.get(works)
    print("Restarted workers")

    time.sleep(5)


if __name__ == "__main__":
    main()
