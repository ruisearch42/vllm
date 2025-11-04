# Detailed Scale Down Sequence Diagram

This diagram shows the detailed process of scaling down the elastic EP (Expert Parallel) system, including distributed environment cleanup, expert weight consolidation, and engine shutdown.

```mermaid
sequenceDiagram
    participant Client as Client
    participant Engine as vLLM Engine
    participant ShutdownEngineCore as EngineCore to shutdown
    participant KeepEngineCore as EngineCore to keep
    participant Worker1 as GPU Worker
    participant Worker2 as GPU Worker
    
    Client->>Engine: scale_elastic_ep(new_size=5)
    Engine->>Engine: Determine scale_down (5 < 6)
    
    loop For each EngineCore
        alt EngineCore rank < new_size (keep)
            Engine->>KeepEngineCore: Send ReconfigRequest<br/>(KEEP_CURRENT_RANK, new_size=5)
            KeepEngineCore->>Worker1: reinitialize_distributed(reconfig_request)

            Note over Worker1: Run EPLB reshuffle
            Note over Worker1: A series of reconfiguration steps (similar to scaling up)
            
        else EngineCore rank >= new_size (shutdown)
            Engine->>ShutdownEngineCore: Send ReconfigRequest<br/>(SHUTDOWN_CURRENT_RANK, new_dp_size=5)
            ShutdownEngineCore->>Worker2: reinitialize_distributed(reconfig_request)
            
            Note over Worker2: Pre-shutdown EPLB reshuffle
            Note over Worker2: Clean up distributed environment & communicators
            
        end
    end
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
