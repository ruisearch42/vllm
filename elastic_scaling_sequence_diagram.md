# Elastic Scaling Sequence Diagram

This diagram shows the sequence of interactions for the elastic scaling functionality in vLLM, based on the current PR changes.

```mermaid
sequenceDiagram
    participant Client as HTTP Client
    participant API as API Server
    participant Middleware as ScalingMiddleware
    participant AsyncLLM as AsyncLLM Engine
    participant CoreClient as DPLBAsyncMPClient
    participant Coordinator as DPCoordinator
    participant Engines as Engine Cores
    participant Ray as Ray Cluster

    Note over Client, Ray: Elastic Scaling Request Flow

    Client->>API: POST /scale_elastic_ep<br/>{new_data_parallel_size, drain_timeout}
    
    API->>API: Validate request parameters
    API->>API: Set _scaling_elastic_ep = True
    
    API->>AsyncLLM: scale_elastic_ep(new_data_parallel_size, drain_timeout)
    
    Note over AsyncLLM: Check if scaling is needed
    AsyncLLM->>AsyncLLM: Check if old_size == new_size
    alt No scaling needed
        AsyncLLM-->>API: Return early (skip scaling)
    else Scaling needed
        AsyncLLM->>AsyncLLM: wait_for_requests_to_drain(drain_timeout)
        Note over AsyncLLM: Wait for all active requests to complete
        
        AsyncLLM->>CoreClient: scale_elastic_ep(new_data_parallel_size)
        
        Note over CoreClient: Determine scale direction
        CoreClient->>CoreClient: Check if scale_up or scale_down
        
        alt Scale Up
            CoreClient->>CoreClient: _scale_up_elastic_ep()
            
            Note over CoreClient, Engines: Phase 1: Send reconfig messages
            loop For each existing engine
                CoreClient->>Engines: Send ReconfigureDistributedRequest<br/>(KEEP_CURRENT_RANK)
            end
            
            Note over CoreClient, Ray: Phase 2: Create new engines
            CoreClient->>Ray: scale_up_elastic_ep(new_data_parallel_size)
            Ray->>Engines: Create new engine cores
            Engines->>CoreClient: Send ready messages
            
            Note over CoreClient, Engines: Phase 3: Wait for reconfig completion
            CoreClient->>Engines: Wait for all reconfig futures
            
            Note over CoreClient, Coordinator: Phase 4: Notify coordinator
            CoreClient->>Coordinator: Send scale_up notification
            
        else Scale Down
            CoreClient->>CoreClient: _scale_down_elastic_ep()
            
            Note over CoreClient, Engines: Send reconfig messages
            loop For each existing engine
                alt Engine rank >= new_size
                    CoreClient->>Engines: Send ReconfigureDistributedRequest<br/>(SHUTDOWN_CURRENT_RANK)
                else Engine rank < new_size
                    CoreClient->>Engines: Send ReconfigureDistributedRequest<br/>(KEEP_CURRENT_RANK)
                end
            end
            
            CoreClient->>CoreClient: Remove engines from core_engines list
            CoreClient->>Engines: Wait for all reconfig futures
            
            CoreClient->>Ray: scale_down_elastic_ep()
            Ray->>Engines: Shutdown excess engines
            
            CoreClient->>Coordinator: Send scale_down notification
        end
        
        Note over CoreClient: Update configuration
        CoreClient->>CoreClient: Update vllm_config.parallel_config.data_parallel_size
        
        CoreClient-->>AsyncLLM: Scaling completed
        
        Note over AsyncLLM: Update stat loggers
        alt Scale up
            AsyncLLM->>AsyncLLM: Add new stat loggers for new engines
        else Scale down
            AsyncLLM->>AsyncLLM: Remove stat loggers for removed engines
        end
    end
    
    AsyncLLM-->>API: Scaling completed
    
    API->>API: Set _scaling_elastic_ep = False
    API-->>Client: 200 OK<br/>{message: "Scaled to X data parallel engines"}

    Note over Client, Ray: Request Processing During Scaling

    Client->>API: POST /v1/chat/completions (during scaling)
    API->>Middleware: Process request
    Middleware->>Middleware: Check _scaling_elastic_ep flag
    
    alt Scaling in progress
        Middleware-->>Client: 503 Service Unavailable<br/>{error: "The model is currently scaling. Please try again later."}
    else Not scaling
        Middleware->>API: Continue processing request
        API->>AsyncLLM: Process normal request
    end

    Note over Client, Ray: Scaling Status Check

    Client->>API: POST /is_scaling_elastic_ep
    API->>API: Check _scaling_elastic_ep flag
    API-->>Client: 200 OK<br/>{is_scaling_elastic_ep: true/false}
```

## Key Changes in This PR

1. **Unified Scaling API**: The PR consolidates `scale_up_elastic_ep` and `scale_down_elastic_ep` into a single `scale_elastic_ep` method that automatically determines the scaling direction.

2. **Simplified AsyncLLM Logic**: Removed the `scaling` flag from AsyncLLM and simplified the scaling logic by delegating the direction determination to the CoreClient.

3. **Improved Error Handling**: Better handling of edge cases like when the new size equals the current size.

4. **Cleaner Code Structure**: The scaling logic is now more maintainable with clear separation of concerns between AsyncLLM and CoreClient.

5. **Middleware Integration**: The ScalingMiddleware ensures that requests are properly handled during scaling operations by returning 503 responses.

## Components Involved

- **API Server**: Handles HTTP requests and manages the global scaling state
- **ScalingMiddleware**: Prevents new requests during scaling operations
- **AsyncLLM**: High-level orchestration of the scaling process
- **DPLBAsyncMPClient**: Handles the actual scaling logic and engine management
- **DPCoordinator**: Manages distributed engine coordination
- **Ray Cluster**: Provides the underlying distributed computing infrastructure
- **Engine Cores**: The actual inference engines that get scaled up/down
