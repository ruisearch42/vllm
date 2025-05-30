# SPDX-License-Identifier: Apache-2.0
import os
import time

import ray
import torch


@ray.remote(num_gpus=1)
class DPActor:

    def __init__(self, data_parallel_master_ip: str, data_parallel_port: int,
                 data_parallel_rank: int, data_parallel_size: int,
                 group_ranks: list[list[int]]):
        self.data_parallel_master_ip = data_parallel_master_ip
        self.data_parallel_port = data_parallel_port
        self.data_parallel_rank = data_parallel_rank
        self.data_parallel_size = data_parallel_size

        self.group_ranks = group_ranks

        self.counter = 0

    def init_dp_group(self):
        import torch.distributed as dist
        if "CUDA_VISIBLE_DEVICES" in os.environ:
            del os.environ["CUDA_VISIBLE_DEVICES"]
        distributed_init_method = f"tcp://{self.data_parallel_master_ip}:{self.data_parallel_port}"
        dist.init_process_group(backend="nccl",
                                init_method=distributed_init_method,
                                world_size=self.data_parallel_size,
                                rank=self.data_parallel_rank)

        print("local_rank", self.data_parallel_rank)
        print("world_size", self.data_parallel_size)
        print("group_ranks", self.group_ranks)
        self.device = torch.device(f"cuda:{self.data_parallel_rank}")

        from vllm.distributed.parallel_state import init_model_parallel_group
        self.dp_group = init_model_parallel_group(
            group_ranks=self.group_ranks,
            local_rank=self.data_parallel_rank,
            backend="nccl",
            group_name="dp_group")

    def do_work(self):
        self.counter = 0
        for _ in range(10):
            val = self.counter * self.data_parallel_size
            tensor = torch.tensor([val], dtype=torch.int32, device=self.device)
            res = self.dp_group.all_reduce(tensor)
            aggregated_val = int(res.item())
            print("value", val, "got aggregated value ", aggregated_val,
                  " from rank ", self.data_parallel_rank)
            self.counter += 1
            # if self.data_parallel_rank == 0 and self.counter == 100:
            #     raise RuntimeError("failure")

    def resize(self, new_size: int):
        self.data_parallel_size = new_size

    def regroup(self, new_size: int, new_group_ranks: list[list[int]]):
        self.data_parallel_size = new_size
        self.group_ranks = new_group_ranks


def main():
    """
    DP Coordinator/Controller
    """
    actors = []
    inits = []
    group_ranks = [[0, 1]]
    for i in range(2):
        dp_actor = DPActor.remote(data_parallel_master_ip="127.0.0.1",
                                  data_parallel_port=50000,
                                  data_parallel_rank=i,
                                  data_parallel_size=2,
                                  group_ranks=group_ranks)
        actors.append(dp_actor)
        inits.append(dp_actor.init_dp_group.remote())

    print("Created actors")
    ray.get(inits)
    print("Initialized actors")

    works = []
    for i in range(2):
        actors[i].do_work.remote()
    ray.get(works)
    print("Started workers")

    time.sleep(1)

    # Scaling up
    new_group_ranks = [[0, 1, 2]]
    new_actor = DPActor.remote("127.0.0.1", 50000, 2, 3, new_group_ranks)
    print("Created new actor")

    resizes = [actor.regroup.remote(3, new_group_ranks) for actor in actors]
    ray.get(resizes)
    print("Resized actors")

    new_group = actors + [new_actor]
    reinits = []
    for actor in new_group:
        reinits.append(actor.init_dp_group.remote())
    ray.get(reinits)
    print("Renitialized actors")

    works = []
    for actor in new_group:
        works.append(actor.do_work.remote())
    ray.get(works)
    print("Restarted workers")

    time.sleep(1)


if __name__ == "__main__":
    main()
