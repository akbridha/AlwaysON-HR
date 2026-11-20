# Container Services Architecture

Diagram berikut menggambarkan interaksi dan topologi service container yang berjalan di Docker Compose.


```mermaid
flowchart TB
    %% Host Client
    subgraph Host ["Host / Client Environment"]
        User(["👤 User / Web Browser"])
    end

    %% Docker Compose Boundary
    subgraph DockerCompose ["Docker Compose Network"]
        direction TB

        subgraph FrontendGroup ["Frontend Service"]
            ST["<b>Service: streamlit</b><br/>Image: Local Build (Dockerfile)<br/>Port: 8501:8501<br/>Framework: Streamlit"]
        end

        subgraph BackendGroup ["Core API & Agent Service"]
            API["<b>Service: api</b><br/>Image: Local Build (Dockerfile)<br/>Port: 8000:8000<br/>Framework: FastAPI / Uvicorn"]
        end

        subgraph StorageGroup ["Data & Caching Layer"]
            PG[("<b>Service: postgres</b><br/>Image: pgvector/pgvector:pg16<br/>Port: 5432:5432<br/>DB: hr_assistant")]
            RD[("<b>Service: redis</b><br/>Image: redis:7-alpine<br/>Port: 6379:6379<br/>In-Memory Cache")]
        end
    end

    %% External APIs
    subgraph External ["External Provider"]
        LLM["OpenAI / LLM API Provider<br/>(Embeddings & Completions)"]
    end

    %% Persistent Storage
    Vol[("Persistent Volume<br/>postgres_data")] --- PG

    %% Relationships & Communication
    User -->|"HTTP :8501"| ST
    User -.->|"HTTP :8000 (Direct/Debug)"| API

    ST -->|"HTTP API calls<br/>http://api:8000"| API

    API -->|"SQL Queries & Vector Search<br/>Port 5432"| PG
    API -->|"Session State & Cache<br/>Port 6379"| RD
    API -->|"HTTPS API Requests"| LLM
```



## Spesifikasi Service

| Service | Image / Base | Port (Host:Container) | Dependensi | Deskripsi & Tanggung Jawab |
|---|---|---|---|---|
| **`streamlit`** | Build lokal ([Dockerfile](Dockerfile)) | `8501:8501` | `api` | UI interaktif untuk chat HR, visualisasi persona, dan interaksi user. |
| **`api`** | Build lokal ([Dockerfile](Dockerfile)) | `8000:8000` | `postgres`, `redis` (healthy) | Backend FastAPI yang menjalankan reasoning loop AI agent, eksekusi tools, dan RAG retrieval. |
| **`postgres`** | `pgvector/pgvector:pg16` | `5432:5432` | - | Relational database (data karyawan/request) + vector extension untuk policy documents retrieval. |
| **`redis`** | `redis:7-alpine` | `6379:6379` | - | In-memory key-value cache untuk caching query, context/session state, dan resilience. |