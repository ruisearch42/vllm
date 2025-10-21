# Detailed Scale Up Sequence Diagram

This diagram shows the detailed process of scaling up the elastic EP (Expert Parallel) system, including distributed environment setup, weight loading, and expert rebalancing.

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant API as API Server
    participant AsyncLLM as AsyncLLM Engine
    participant CoreClient as DPLBAsyncMPClient
    participant ExistingEngine as Existing Engine Core
    participant Worker as GPU Worker

    Client->>API: POST /scale_elastic_ep<br/>{new_data_parallel_size: 4, drain_timeout: 120}
    API->>API: Validate parameters
    
    API->>AsyncLLM: scale_elastic_ep(new_size=4)
    
    AsyncLLM->>AsyncLLM: wait_for_requests_to_drain(timeout=120)
    
    AsyncLLM->>CoreClient: scale_elastic_ep(4)
    CoreClient->>CoreClient: Determine scale_up (4 > 2)
    
    Note over CoreClient: Send reconfig messages to existing engines
    loop For each existing engine
        CoreClient->>ExistingEngine: Send ReconfigRequest<br/>(KEEP_CURRENT_RANK, new_dp_size=4)
        ExistingEngine->>Worker: reinitialize_distributed(reconfig_request)
        
        Note over Worker: Collect expert load statistics
        
        Note over Worker: Destroy distributed environment & communicators
        
        Note over Worker: Update parallel configuration
        
        Note over Worker: Reinitialize distributed environment & communicators
        
        Note over Worker: Reconfigure MoE (Mixture of Experts)
        
        Note over Worker: Run EPLB reshuffle
        
        Worker-->>CoreClient: Reconfiguration completed
    end
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

