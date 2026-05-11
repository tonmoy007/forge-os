flowchart TD
    subgraph User_Interfaces [User Interfaces]
        CLI[CLI / Forge Commands]
        Web[Web Dashboard]
        Channels[Channel Adapters<br/>Slack/Telegram/WhatsApp]
    end

    subgraph Orchestration_Engine [Orchestration Engine]
        SM[State Machine<br/>12 SDLC Stages]
        Hooks[Lifecycle Hooks]
        Dispatcher[Async Agent Dispatcher]
        Backtrack[Backtrack Engine]
    end

    subgraph Agent_System [Specialized Agent System]
        StageAgents[12 Stage Agents<br/>Requirements Analyst, Builder, ...]
        CrossAgents[4 Cross-Stage Agents<br/>Reflector, Lesson Extractor, Skill Miner, Gate Checker]
        LangGraph[LangGraph Runtime]
    end

    subgraph Memory_Learning [Memory & Learning Subsystem]
        LKG[Lessons Knowledge Graph<br/>NeuG / Neo4j]
        ADG[Artifact Dependency Graph<br/>NetworkX]
        ContextPruner[Context Pruner<br/>+ Lazy Context Builder]
        VectorDB[Vector Store<br/>LanceDB / SQLite-vec]
    end

    subgraph Quality [Quality & Security]
        GateCoord[Gate Coordinator<br/>Multi-modal criteria]
        Sandbox[gVisor Sandbox<br/>ExternalCommand / Bash]
        CredProxy[Credential Proxy<br/>FORGE_SESSION_TOKEN]
        HITL[Human-in-the-Loop<br/>Risk-based routing]
    end

    subgraph External_Integrations [External Integrations]
        KernelAdapter[Kernel Adapter Layer<br/>LiteLLM]
        OpenClaw[OpenClawAdapter<br/>Channels / Agents]
        MCP[MCP Servers<br/>Tools / External commands]
        OTLP[OpenTelemetry Collector<br/>otlite / Grafana]
    end

    subgraph Data_Storage [Persistence]
        PipelineState[Pipeline State<br/>JSON/Markdown]
        AuditLedger[Audit Ledger<br/>HMAC-chained JSONL]
        Artifacts[Artifacts<br/>Markdown/YAML/Code]
        GlobalMemory[Global Memory<br/>~/.forge/]
    end

    subgraph Daemons [Background Services]
        HealthDaemon[Health & Sustainability Daemon]
        Dreamer[Dreamer Agent]
        Observer[Always-On Observer]
    end

    %% Connections
    CLI --> SM
    Web --> SM
    Channels --> SM

    SM --> Dispatcher
    Dispatcher --> LangGraph
    LangGraph --> StageAgents
    LangGraph --> CrossAgents

    StageAgents --> ContextPruner
    CrossAgents --> ContextPruner
    ContextPruner --> ADG
    ContextPruner --> LKG

    StageAgents --> GateCoord
    GateCoord --> Sandbox
    GateCoord --> HITL
    Sandbox --> CredProxy

    StageAgents --> KernelAdapter
    KernelAdapter --> OpenClaw
    KernelAdapter --> MCP
    StageAgents --> MCP

    SM --> Backtrack
    Backtrack --> ADG

    StageAgents --> Artifacts
    StageAgents --> PipelineState
    CrossAgents --> LKG
    CrossAgents --> AuditLedger

    HealthDaemon --> GateCoord
    HealthDaemon --> Hooks
    HealthDaemon --> LKG
    Dreamer --> LKG
    Dreamer --> AuditLedger
    Observer --> SM

    OTLP --> AuditLedger
    OTLP --> Hooks

    LKG --> GlobalMemory
    ADG --> GlobalMemory
    GlobalMemory --> ContextPruner

    %% Legend / styling
    classDef core fill:#e1f5fe,stroke:#01579b
    classDef agent fill:#fff3e0,stroke:#e65100
    classDef memory fill:#e8f5e9,stroke:#1b5e20
    classDef security fill:#ffebee,stroke:#b71c1c
    classDef external fill:#f3e5f5,stroke:#4a148c
    classDef storage fill:#fff8e1,stroke:#f57f17
    
    class SM,Dispatcher,Hooks,Backtrack core
    class LangGraph,StageAgents,CrossAgents agent
    class LKG,ADG,ContextPruner,VectorDB memory
    class GateCoord,Sandbox,CredProxy,HITL security
    class KernelAdapter,OpenClaw,MCP,OTLP external
    class PipelineState,AuditLedger,Artifacts,GlobalMemory storage
    class HealthDaemon,Dreamer,Observer daemon
