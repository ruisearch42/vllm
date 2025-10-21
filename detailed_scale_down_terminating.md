# Detailed Scale Down Sequence Diagram

This diagram shows the detailed process of scaling down the elastic EP (Expert Parallel) system, including distributed environment cleanup, expert weight consolidation, and engine shutdown.

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant API as API Server
    participant AsyncLLM as AsyncLLM Engine
    participant CoreClient as DPLBAsyncMPClient
    participant ShutdownEngine as Engine to Shutdown
    participant KeepEngine as Engine to Keep
    participant Worker as GPU Worker

    Client->>API: POST /scale_elastic_ep<br/>{new_data_parallel_size: 2, drain_timeout: 120}
    API->>API: Validate parameters
    
    API->>AsyncLLM: scale_elastic_ep(2, 120)
    
    AsyncLLM->>AsyncLLM: wait_for_requests_to_drain(120)
    Note over AsyncLLM: Wait for all active requests to complete
    
    AsyncLLM->>CoreClient: scale_elastic_ep(2)
    CoreClient->>CoreClient: Determine scale_down (2 < 4)
    
    Note over CoreClient: Send reconfig messages to all engines
    loop For each engine (keep and shutdown)
        alt Engine rank < new_size (Keep)
            CoreClient->>KeepEngine: Send ReconfigRequest<br/>(KEEP_CURRENT_RANK, new_dp_size=2)
            KeepEngine->>Worker: reinitialize_distributed(reconfig_request)
            
            Note over Worker: A series of reconfiguration steps (similar as scaling up)
            Note over Worker: Run EPLB reshuffle
            
            KeepEngine-->>CoreClient: Reconfiguration completed
            
        else Engine rank >= new_size (Shutdown)
            CoreClient->>ShutdownEngine: Send ReconfigRequest<br/>(SHUTDOWN_CURRENT_RANK, new_dp_size=2)
            ShutdownEngine->>Worker: reinitialize_distributed(reconfig_request)
            
            Note over Worker: Pre-shutdown EPLB reshuffle
            Note over Worker: Clean up distributed environment & communicators
            
            ShutdownEngine-->>CoreClient: Shutdown completed
        end
    end
    
    CoreClient-->>AsyncLLM: Scale down completed
    
    AsyncLLM-->>API: Scaling completed
    API-->>Client: 200 OK<br/>{message: "Scaled to 2 data parallel engines"}
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

