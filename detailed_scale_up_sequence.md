# Detailed Scale Up Sequence Diagram

This diagram shows the detailed process of scaling up the elastic EP (Expert Parallel) system, including distributed environment setup, weight loading, and expert rebalancing.

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant API as API Server
    participant AsyncLLM as AsyncLLM Engine
    participant CoreClient as DPLBAsyncMPClient
    participant Ray as Ray Cluster
    participant NewEngine as New Engine Core
    participant ExistingEngine as Existing Engine Core
    participant Worker as GPU Worker
    participant ModelRunner as GPU Model Runner
    participant EPLB as EPLB State
    participant DistEnv as Distributed Environment
    participant ExpertWeights as Expert Weights

    Note over Client, ExpertWeights: Detailed Scale Up Process

    Client->>API: POST /scale_elastic_ep<br/>{new_data_parallel_size: 4, drain_timeout: 120}
    API->>API: Validate parameters
    API->>API: Set _scaling_elastic_ep = True
    
    API->>AsyncLLM: scale_elastic_ep(4, 120)
    AsyncLLM->>AsyncLLM: Check if old_size == new_size
    Note over AsyncLLM: Skip if no change needed
    
    AsyncLLM->>AsyncLLM: wait_for_requests_to_drain(120)
    Note over AsyncLLM: Wait for all active requests to complete
    
    AsyncLLM->>CoreClient: scale_elastic_ep(4)
    CoreClient->>CoreClient: Determine scale_up (4 > 2)
    
    Note over CoreClient: Phase 1: Send reconfig messages to existing engines
    loop For each existing engine
        CoreClient->>ExistingEngine: Send ReconfigureDistributedRequest<br/>(KEEP_CURRENT_RANK, new_dp_size=4)
        ExistingEngine->>Worker: reinitialize_distributed(reconfig_request)
        
        Note over Worker: Pre-scale-down EPLB processing
        Worker->>Worker: _eplb_before_scale_down(old_ep_size, new_ep_size)
        Note over Worker: Collect expert load statistics
        
        Note over Worker: Cleanup distributed environment
        Worker->>DistEnv: cleanup_dist_env_and_memory()
        DistEnv->>DistEnv: Destroy old process groups
        
        Note over Worker: Update parallel configuration
        Worker->>Worker: _reconfigure_parallel_config(reconfig_request)
        Worker->>Worker: Update data_parallel_size, master_ip, master_port
        
        Note over Worker: Reinitialize distributed environment
        Worker->>DistEnv: init_worker_distributed_environment()
        DistEnv->>DistEnv: Create new process groups with new size
        
        Note over Worker: Reconfigure MoE (Mixture of Experts)
        Worker->>Worker: _reconfigure_moe(old_ep_size, new_ep_size)
        Worker->>Worker: Calculate global_expert_load statistics
        
        Note over Worker: Post-scale-up EPLB processing
        Worker->>Worker: _eplb_after_scale_up(old_ep_size, new_ep_size, global_expert_load)
        Worker->>EPLB: rearrange(model, execute_shuffle=True, global_expert_load, rank_mapping)
        
        Note over EPLB: Expert rebalancing process
        EPLB->>EPLB: Collect global expert load statistics
        EPLB->>EPLB: Calculate new expert mappings using rebalance_experts()
        EPLB->>ExpertWeights: rearrange_expert_weights_inplace()
        
        Note over ExpertWeights: Weight redistribution
        ExpertWeights->>ExpertWeights: Map old expert indices to new indices
        ExpertWeights->>ExpertWeights: Shuffle expert weights across ranks
        ExpertWeights->>ExpertWeights: Update physical_to_logical_map
        
        Worker-->>CoreClient: Reconfiguration completed
    end
    
    Note over CoreClient: Phase 2: Create new engines via Ray
    CoreClient->>Ray: scale_up_elastic_ep(new_data_parallel_size=4)
    Ray->>Ray: Create new engine actors/processes
    
    loop For each new engine
        Ray->>NewEngine: Start new engine core process
        NewEngine->>Worker: Initialize GPU Worker
        Worker->>DistEnv: init_worker_distributed_environment()
        DistEnv->>DistEnv: Join existing process groups
        
        Note over Worker: Model loading for scale up
        Worker->>ModelRunner: load_model(eep_scale_up=True)
        ModelRunner->>ModelRunner: Receive EPLB state from existing engines
        ModelRunner->>ModelRunner: Get global_expert_load and old_global_expert_indices
        ModelRunner->>ModelRunner: Calculate num_redundant_experts
        ModelRunner->>ModelRunner: Set up rank_mapping for existing engines
        
        Note over ModelRunner: Load and configure model
        ModelRunner->>ModelRunner: Initialize model with new configuration
        ModelRunner->>ExpertWeights: Load expert weights with EPLB state
        ExpertWeights->>ExpertWeights: Apply expert mappings from EPLB
        ExpertWeights->>ExpertWeights: Set up local expert indices
        
        NewEngine->>CoreClient: Send ready message
    end
    
    Note over CoreClient: Phase 3: Wait for all reconfigurations
    CoreClient->>CoreClient: Wait for all reconfig futures to complete
    
    Note over CoreClient: Phase 4: Notify coordinator
    CoreClient->>CoreClient: Send scale_up notification to coordinator
    CoreClient->>CoreClient: Update vllm_config.parallel_config.data_parallel_size = 4
    
    CoreClient-->>AsyncLLM: Scale up completed
    
    Note over AsyncLLM: Update stat loggers
    AsyncLLM->>AsyncLLM: Add new stat loggers for new engines
    AsyncLLM->>AsyncLLM: Update stat_loggers list
    
    AsyncLLM-->>API: Scaling completed
    API->>API: Set _scaling_elastic_ep = False
    API-->>Client: 200 OK<br/>{message: "Scaled to 4 data parallel engines"}

    Note over Client, ExpertWeights: Key Components and Processes

    Note over EPLB: EPLB (Expert Parallel Load Balancing)
    Note over EPLB: - Collects expert load statistics
    Note over EPLB: - Calculates optimal expert distribution
    Note over EPLB: - Manages expert weight redistribution
    Note over EPLB: - Updates physical-to-logical expert mappings

    Note over ExpertWeights: Expert Weight Management
    Note over ExpertWeights: - Stores expert weights for each layer
    Note over ExpertWeights: - Handles weight sharding across ranks
    Note over ExpertWeights: - Manages expert weight redistribution
    Note over ExpertWeights: - Updates local expert indices

    Note over DistEnv: Distributed Environment
    Note over DistEnv: - Manages process groups (DP, TP, PP, EP)
    Note over DistEnv: - Handles collective communications
    Note over DistEnv: - Manages rank mappings and topology
    Note over DistEnv: - Coordinates distributed operations
```

## Key Scale Up Processes

### 1. **Pre-Scale EPLB Processing**
- Collect expert load statistics from existing engines
- Calculate global expert load distribution
- Prepare for expert weight redistribution

### 2. **Distributed Environment Reconfiguration**
- Clean up old process groups
- Update parallel configuration (DP size, master IP/port)
- Reinitialize distributed environment with new size
- Create new process groups for all ranks

### 3. **Expert Weight Redistribution**
- Calculate new expert mappings using load balancing algorithm
- Redistribute expert weights across all ranks
- Update physical-to-logical expert mappings
- Ensure load balancing across new engine count

### 4. **New Engine Initialization**
- Create new engine processes via Ray
- Initialize distributed environment for new engines
- Load model with EPLB state from existing engines
- Configure expert weights and mappings

### 5. **Coordination and Cleanup**
- Wait for all reconfigurations to complete
- Notify coordinator about scale up
- Update configuration and stat loggers

