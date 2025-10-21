# Detailed Scale Down Sequence Diagram

This diagram shows the detailed process of scaling down the elastic EP (Expert Parallel) system, including distributed environment cleanup, expert weight consolidation, and engine shutdown.

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant API as API Server
    participant AsyncLLM as AsyncLLM Engine
    participant CoreClient as DPLBAsyncMPClient
    participant Ray as Ray Cluster
    participant ShutdownEngine as Engine to Shutdown
    participant KeepEngine as Engine to Keep
    participant Worker as GPU Worker
    participant ModelRunner as GPU Model Runner
    participant EPLB as EPLB State
    participant DistEnv as Distributed Environment
    participant ExpertWeights as Expert Weights

    Note over Client, ExpertWeights: Detailed Scale Down Process

    Client->>API: POST /scale_elastic_ep<br/>{new_data_parallel_size: 2, drain_timeout: 120}
    API->>API: Validate parameters
    API->>API: Set _scaling_elastic_ep = True
    
    API->>AsyncLLM: scale_elastic_ep(2, 120)
    AsyncLLM->>AsyncLLM: Check if old_size == new_size
    Note over AsyncLLM: Skip if no change needed
    
    AsyncLLM->>AsyncLLM: wait_for_requests_to_drain(120)
    Note over AsyncLLM: Wait for all active requests to complete
    
    AsyncLLM->>CoreClient: scale_elastic_ep(2)
    CoreClient->>CoreClient: Determine scale_down (2 < 4)
    
    Note over CoreClient: Phase 1: Send reconfig messages to all engines
    loop For each engine (keep and shutdown)
        alt Engine rank < new_size (Keep)
            CoreClient->>KeepEngine: Send ReconfigureDistributedRequest<br/>(KEEP_CURRENT_RANK, new_dp_size=2)
            KeepEngine->>Worker: reinitialize_distributed(reconfig_request)
            
            Note over Worker: Pre-scale-down EPLB processing
            Worker->>Worker: _eplb_before_scale_down(old_ep_size, new_ep_size)
            Note over Worker: Collect expert load statistics from all engines
            Worker->>EPLB: Collect global expert load data
            EPLB->>EPLB: Calculate load distribution across remaining engines
            
            Note over Worker: Cleanup distributed environment
            Worker->>DistEnv: cleanup_dist_env_and_memory()
            DistEnv->>DistEnv: Destroy old process groups
            
            Note over Worker: Update parallel configuration
            Worker->>Worker: _reconfigure_parallel_config(reconfig_request)
            Worker->>Worker: Update data_parallel_size, master_ip, master_port
            
            Note over Worker: Reinitialize distributed environment
            Worker->>DistEnv: init_worker_distributed_environment()
            DistEnv->>DistEnv: Create new process groups with reduced size
            
            Note over Worker: Reconfigure MoE (Mixture of Experts)
            Worker->>Worker: _reconfigure_moe(old_ep_size, new_ep_size)
            Worker->>Worker: Calculate global_expert_load for remaining engines
            
            Note over Worker: Expert weight consolidation
            Worker->>EPLB: rearrange(model, execute_shuffle=True, global_expert_load, rank_mapping)
            
            Note over EPLB: Expert consolidation process
            EPLB->>EPLB: Calculate new expert mappings for reduced engine count
            EPLB->>EPLB: Create rank_mapping for remaining engines
            EPLB->>ExpertWeights: rearrange_expert_weights_inplace()
            
            Note over ExpertWeights: Weight consolidation
            ExpertWeights->>ExpertWeights: Map experts from shutdown engines to remaining engines
            ExpertWeights->>ExpertWeights: Transfer expert weights from shutdown engines
            ExpertWeights->>ExpertWeights: Update physical_to_logical_map for new topology
            ExpertWeights->>ExpertWeights: Redistribute expert load across remaining engines
            
            KeepEngine-->>CoreClient: Reconfiguration completed
            
        else Engine rank >= new_size (Shutdown)
            CoreClient->>ShutdownEngine: Send ReconfigureDistributedRequest<br/>(SHUTDOWN_CURRENT_RANK, new_dp_size=2)
            ShutdownEngine->>Worker: reinitialize_distributed(reconfig_request)
            
            Note over Worker: Pre-shutdown EPLB processing
            Worker->>Worker: _eplb_before_scale_down(old_ep_size, new_ep_size)
            Note over Worker: Prepare expert weights for transfer
            Worker->>ExpertWeights: Prepare expert weights for transfer to remaining engines
            
            Note over Worker: Cleanup distributed environment
            Worker->>DistEnv: cleanup_dist_env_and_memory()
            DistEnv->>DistEnv: Destroy process groups
            
            Note over Worker: Check shutdown condition
            Worker->>Worker: Check if new_data_parallel_rank == SHUTDOWN_CURRENT_RANK
            Worker->>Worker: Assert old_ep_rank >= new_ep_size
            Worker->>Worker: Return (shutdown this engine)
            
            ShutdownEngine-->>CoreClient: Shutdown completed
        end
    end
    
    Note over CoreClient: Phase 2: Remove engines from core_engines list
    CoreClient->>CoreClient: Remove engines with rank >= new_size from core_engines
    
    Note over CoreClient: Phase 3: Wait for all reconfigurations
    CoreClient->>CoreClient: Wait for all reconfig futures to complete
    
    Note over CoreClient: Phase 4: Shutdown engines via Ray
    CoreClient->>Ray: scale_down_elastic_ep(cur_size=4, new_size=2)
    Ray->>Ray: Shutdown excess engine actors/processes
    
    loop For each engine to shutdown
        Ray->>ShutdownEngine: Terminate engine process
        ShutdownEngine->>ShutdownEngine: Cleanup resources
        ShutdownEngine->>ShutdownEngine: Exit process
    end
    
    Note over CoreClient: Phase 5: Notify coordinator
    CoreClient->>CoreClient: Send scale_down notification to coordinator
    CoreClient->>CoreClient: Update vllm_config.parallel_config.data_parallel_size = 2
    
    CoreClient-->>AsyncLLM: Scale down completed
    
    Note over AsyncLLM: Update stat loggers
    AsyncLLM->>AsyncLLM: Remove stat loggers for shutdown engines
    AsyncLLM->>AsyncLLM: Update stat_loggers list
    
    AsyncLLM-->>API: Scaling completed
    API->>API: Set _scaling_elastic_ep = False
    API-->>Client: 200 OK<br/>{message: "Scaled to 2 data parallel engines"}

    Note over Client, ExpertWeights: Key Scale Down Processes

    Note over EPLB: Expert Consolidation
    Note over EPLB: - Collects expert load from all engines
    Note over EPLB: - Calculates optimal distribution for remaining engines
    Note over EPLB: - Creates rank_mapping for remaining engines
    Note over EPLB: - Manages expert weight transfer and consolidation

    Note over ExpertWeights: Weight Transfer Process
    Note over ExpertWeights: - Identifies experts from shutdown engines
    Note over ExpertWeights: - Transfers expert weights to remaining engines
    Note over ExpertWeights: - Updates expert mappings for new topology
    Note over ExpertWeights: - Redistributes load across remaining engines

    Note over DistEnv: Environment Cleanup
    Note over DistEnv: - Destroys old process groups
    Note over DistEnv: - Creates new groups with reduced size
    Note over DistEnv: - Updates rank mappings and topology
    Note over DistEnv: - Coordinates cleanup across all engines
```

## Key Scale Down Processes

### 1. **Pre-Scale EPLB Processing**
- Collect expert load statistics from all engines
- Calculate optimal distribution for remaining engines
- Prepare for expert weight consolidation

### 2. **Engine Classification**
- **Keep Engines**: Engines with rank < new_size
  - Receive KEEP_CURRENT_RANK reconfig request
  - Participate in expert weight consolidation
  - Continue operation with new configuration
- **Shutdown Engines**: Engines with rank >= new_size
  - Receive SHUTDOWN_CURRENT_RANK reconfig request
  - Transfer expert weights to remaining engines
  - Clean up and exit

### 3. **Expert Weight Consolidation**
- Calculate new expert mappings for reduced engine count
- Create rank mapping for remaining engines
- Transfer expert weights from shutdown engines to remaining engines
- Update physical-to-logical expert mappings
- Redistribute expert load across remaining engines

### 4. **Distributed Environment Cleanup**
- Destroy old process groups
- Update parallel configuration for reduced size
- Reinitialize distributed environment with new topology
- Create new process groups for remaining engines

### 5. **Engine Shutdown and Cleanup**
- Remove shutdown engines from core_engines list
- Terminate excess engine processes via Ray
- Clean up resources and exit processes
- Update configuration and stat loggers

## Critical Considerations

### **Data Preservation**
- Expert weights must be transferred before engine shutdown
- No data loss during consolidation process
- Maintain model integrity throughout scale down

### **Load Balancing**
- Redistribute expert load evenly across remaining engines
- Optimize for new topology and engine count
- Maintain performance characteristics

### **Coordination**
- Synchronize expert weight transfers
- Ensure all engines complete reconfiguration before shutdown
- Maintain distributed system consistency

