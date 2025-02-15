# SPDX-License-Identifier: Apache-2.0

from openai import OpenAI

# Modify OpenAI's API key and API base to use vLLM's API server.
openai_api_key = "EMPTY"
openai_api_base = "http://localhost:8000/v1"

client = OpenAI(
    # defaults to os.environ.get("OPENAI_API_KEY")
    api_key=openai_api_key,
    base_url=openai_api_base,
)

models = client.models.list()
model = models.data[0].id

# Completion API
stream = False
completion = client.completions.create(
    model=model,
    prompt="A robot may not injure a human being",
    echo=False,
    n=1,
    stream=stream,
    # logprobs=3,
    max_tokens=30,
    temperature=0)

print("Completion results:")
if stream:
    for c in completion:
        print(c)
else:
    print(completion)

# (RayWorkerWrapper pid=1884932) layer 8 hidden_states tensor([[-0.0074,  0.0415, -0.0894,  ..., -0.0251, -0.0801,  0.0510],
# (RayWorkerWrapper pid=1884932)         [-0.0850,  0.0447,  0.0664,  ...,  0.0835, -0.0703, -0.0153],
# (RayWorkerWrapper pid=1884932)         [-0.0233,  0.0034, -0.0991,  ..., -0.1260,  0.0781,  0.0155],
# (RayWorkerWrapper pid=1884932)         ...,
# (RayWorkerWrapper pid=1884932)         [-0.0369,  0.1021,  0.0144,  ...,  0.0286,  0.0713, -0.1318],
# (RayWorkerWrapper pid=1884932)         [-0.0947,  0.1328, -0.0325,  ...,  0.0645,  0.0981, -0.0518],
# (RayWorkerWrapper pid=1884932)         [-0.0850,  0.1367, -0.0547,  ...,  0.0830,  0.0164, -0.0796]],
# (RayWorkerWrapper pid=1884932)        device='cuda:1', dtype=torch.bfloat16)
# (RayWorkerWrapper pid=1884932) layer 8 residual tensor([[ 1.4648e-01, -3.9453e-01,  1.5781e+00,  ..., -2.1387e-01,
# (RayWorkerWrapper pid=1884932)           1.2734e+00, -1.5332e-01],
# (RayWorkerWrapper pid=1884932)         [ 7.8613e-02,  6.5918e-03,  1.8848e-01,  ...,  1.8921e-02,
# (RayWorkerWrapper pid=1884932)          -2.4292e-02, -4.7607e-02],
# (RayWorkerWrapper pid=1884932)         [ 1.3965e-01, -1.5527e-01, -1.7871e-01,  ...,  1.0742e-01,
# (RayWorkerWrapper pid=1884932)          -9.3750e-02, -3.6621e-04],
# (RayWorkerWrapper pid=1884932)         ...,
# (RayWorkerWrapper pid=1884932)         [ 1.9043e-01, -1.3086e-01,  2.8809e-02,  ...,  1.3867e-01,
# (RayWorkerWrapper pid=1884932)           2.7344e-02,  8.8867e-02],
# (RayWorkerWrapper pid=1884932)         [ 1.7188e-01, -7.8613e-02,  9.7168e-02,  ...,  4.2480e-02,
# (RayWorkerWrapper pid=1884932)           9.2773e-03,  8.7891e-02],
# (RayWorkerWrapper pid=1884932)         [ 4.6631e-02, -3.0396e-02,  9.1309e-02,  ..., -3.6316e-03,
# (RayWorkerWrapper pid=1884932)          -7.5684e-03, -1.6602e-02]], device='cuda:1', dtype=torch.bfloat16)
# (RayWorkerWrapper pid=1884932) type of hidden_states <class 'torch.Tensor'>
# (RayWorkerWrapper pid=1884932) shape of hidden_states torch.Size([10, 2048])

# (RayWorkerWrapper pid=1884932) layer 8 hidden_states tensor([[-0.0562,  0.0442, -0.0757,  ..., -0.0496,  0.0243,  0.0147]],
# (RayWorkerWrapper pid=1884932)        device='cuda:1', dtype=torch.bfloat16)
# (RayWorkerWrapper pid=1884932) layer 8 residual tensor([[ 0.0938,  0.0889,  0.0972,  ...,  0.1216,  0.0098, -0.0835]],
# (RayWorkerWrapper pid=1884932)        device='cuda:1', dtype=torch.bfloat16)
