# AWS Deployment Architecture

## Overview

This document describes the complete AWS infrastructure for the Voice Workout Tracker (Titan Trakr), replicating your successful PassportPhotoFactory architecture with PostgreSQL instead of DynamoDB.

---

## High-Level Architecture

```mermaid
graph TB
    User[👤 User Browser]
    
    subgraph DNS["Route53 DNS"]
        D1[titantrakr.com]
        D2[traktitan.com]
        D3[tritontracker.com]
        D4[staging.titantrakr.com]
    end
    
    subgraph CDN["CloudFront CDN"]
        CF[CloudFront Distribution<br/>SSL: ACM Certificate<br/>Cache: Static Assets]
    end
    
    subgraph Compute["AWS Lambda"]
        L[Lambda Function<br/>Docker Image<br/>FastAPI + Mangum<br/>512 MB, 30s timeout]
        URL[Function URL<br/>Public HTTPS]
    end
    
    subgraph Database["Database Layer"]
        Proxy[RDS Proxy<br/>Connection Pooling]
        DB[(RDS PostgreSQL<br/>db.t4g.micro<br/>20 GB gp3)]
    end
    
    subgraph Backup["Backup & DR"]
        Snap[RDS Automated<br/>Snapshots<br/>30-day PITR]
        Vault[AWS Backup Vault<br/>Daily/Weekly/Monthly]
    end
    
    User -->|HTTPS| DNS
    DNS -->|Alias| CF
    CF -->|Cache Miss| URL
    URL -->|Invoke| L
    L -->|PostgreSQL| Proxy
    Proxy -->|Connection Pool| DB
    DB -.->|Automated| Snap
    DB -.->|Scheduled| Vault
    
    style User fill:#4CAF50
    style CF fill:#FF9800
    style L fill:#2196F3
    style DB fill:#9C27B0
    style Vault fill:#F44336
```

---

## Network Architecture (VPC)

```mermaid
graph TB
    subgraph VPC["VPC: 10.0.0.0/16"]
        subgraph AZ1["Availability Zone 1"]
            PubSub1[Public Subnet<br/>10.0.1.0/24]
            PrivSub1[Private Subnet<br/>10.0.10.0/24<br/>RDS Primary]
        end
        
        subgraph AZ2["Availability Zone 2"]
            PubSub2[Public Subnet<br/>10.0.2.0/24]
            PrivSub2[Private Subnet<br/>10.0.11.0/24<br/>RDS Standby]
        end
        
        subgraph Security["Security Groups"]
            LambdaSG[Lambda SG<br/>Egress: All]
            ProxySG[RDS Proxy SG<br/>5432 from Lambda]
            DBSG[RDS SG<br/>5432 from Proxy]
        end
        
        IGW[Internet Gateway]
        NAT[NAT Gateway<br/>Optional]
    end
    
    Internet((Internet))
    
    Internet -->|HTTPS| IGW
    IGW --> PubSub1
    IGW --> PubSub2
    
    PubSub1 -.->|Route| NAT
    NAT -.->|For Lambda| PrivSub1
    
    PrivSub1 --> LambdaSG
    PrivSub2 --> LambdaSG
    LambdaSG -->|Port 5432| ProxySG
    ProxySG -->|Port 5432| DBSG
    DBSG --> PrivSub1
    DBSG --> PrivSub2
    
    style VPC fill:#E3F2FD
    style AZ1 fill:#FFF3E0
    style AZ2 fill:#FFF3E0
    style Security fill:#F3E5F5
```

**Note:** Lambda is in VPC to reach RDS, but can still access internet for LLM APIs (via NAT Gateway or VPC endpoints).

---

## Request Flow (User Logs a Set)

```mermaid
sequenceDiagram
    participant U as User<br/>(Browser)
    participant CF as CloudFront
    participant L as Lambda<br/>(FastAPI)
    participant P as RDS Proxy
    participant DB as PostgreSQL
    participant LLM as Anthropic<br/>Claude API
    
    U->>CF: POST /api/voice/process<br/>{"transcript": "80kg for 10"}
    
    alt Cache Miss
        CF->>L: Forward to Lambda URL
    end
    
    L->>LLM: Process voice command
    LLM-->>L: {"action": "emit", "exercise_id": "bench-press"}
    
    L->>P: BEGIN TRANSACTION
    P->>DB: Get current_workout projection
    DB-->>P: {id: "abc", exercises: [...]}
    P-->>L: Projection data
    
    L->>L: Validate preconditions
    
    L->>P: INSERT INTO events (...)
    P->>DB: Write event
    L->>P: UPDATE projections SET data = ...
    P->>DB: Update projection
    L->>P: COMMIT
    
    P-->>L: Transaction success
    L-->>CF: 200 OK {success: true}
    CF-->>U: Response (cached if GET)
    
    U->>U: Display "Logged 80kg × 10"
```

---

## Data Storage Architecture

```mermaid
graph LR
    subgraph Lambda["Lambda Application Layer"]
        API[FastAPI Endpoints]
        Events[Event Handler<br/>Validation & Logic]
    end
    
    subgraph Database["PostgreSQL Tables"]
        T1[(events<br/>Append-only log)]
        T2[(projections<br/>Derived state)]
        T3[(exercises<br/>Library)]
        T4[(aggregates<br/>Stats)]
    end
    
    subgraph Backup["Backup Storage"]
        B1[RDS Snapshots<br/>S3<br/>30-day retention]
        B2[AWS Backup<br/>S3 Standard<br/>Daily backups]
        B3[AWS Backup<br/>S3 Glacier<br/>Long-term archives]
    end
    
    API -->|Write| Events
    Events -->|append_event| T1
    Events -->|update_projections| T2
    API -->|Read| T2
    API -->|Lookup| T3
    
    T1 -.->|Snapshot| B1
    T1 -.->|Backup Job| B2
    B2 -->|Lifecycle| B3
    
    style T1 fill:#4CAF50
    style T2 fill:#2196F3
    style B1 fill:#FF9800
    style B3 fill:#9E9E9E
```

### Table Schemas

#### Events Table (Append-Only)
```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    event_id UUID UNIQUE NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    schema_version INTEGER DEFAULT 1
);

CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
```

#### Projections Table (Derived State)
```sql
CREATE TABLE projections (
    key VARCHAR(255) PRIMARY KEY,
    data JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
```

---

## Component Architecture

```mermaid
graph TB
    subgraph Client["Client Layer"]
        Browser[Web Browser<br/>Alpine.js + Tailwind]
        Voice[Web Speech API<br/>STT + TTS]
    end
    
    subgraph Application["Application Layer"]
        FastAPI[FastAPI Application]
        
        subgraph Routes["API Routes"]
            R1[/api/events]
            R2[/api/voice]
            R3[/api/history]
            R4[/api/templates]
        end
        
        subgraph Core["Business Logic"]
            EventHandler[Event Handler<br/>Validation]
            Projections[Projection Builder]
            VoiceProcessor[Voice Command<br/>LLM Processing]
        end
        
        subgraph Data["Data Layer"]
            DBAdapter[Database Adapter<br/>SQLite ↔ PostgreSQL]
        end
    end
    
    subgraph External["External Services"]
        Claude[Anthropic Claude<br/>3.5 Haiku]
        OpenAI[OpenAI GPT-4<br/>Optional]
    end
    
    Browser -->|REST API| FastAPI
    Voice -->|Transcript| R2
    
    FastAPI --> R1
    FastAPI --> R2
    FastAPI --> R3
    FastAPI --> R4
    
    R1 --> EventHandler
    R2 --> VoiceProcessor
    VoiceProcessor --> Claude
    VoiceProcessor --> OpenAI
    
    EventHandler --> Projections
    EventHandler --> DBAdapter
    Projections --> DBAdapter
    
    style FastAPI fill:#4CAF50
    style Claude fill:#FF9800
    style DBAdapter fill:#2196F3
```

---

## Backup & Disaster Recovery Architecture

```mermaid
graph TB
    subgraph Primary["Primary Database - us-west-1"]
        RDS[RDS PostgreSQL<br/>prod-gym-app-db]
    end
    
    subgraph BackupTiers["Backup Tiers"]
        T1[Tier 1: RDS Automated<br/>30-day PITR<br/>Every 5 minutes<br/>RTO: 15 min]
        T2[Tier 2: Daily Backup<br/>30-day retention<br/>Standard storage<br/>RTO: 20 min]
        T3[Tier 3: Weekly Backup<br/>90-day retention<br/>Cold storage<br/>RTO: 30 min]
        T4[Tier 4: Monthly Backup<br/>365-day retention<br/>Cold storage<br/>RTO: 1 hour]
    end
    
    subgraph DR["Disaster Recovery (Optional)"]
        CrossRegion[Cross-Region Copy<br/>us-east-1<br/>Monthly backups]
        S3Archive[S3 Glacier Deep<br/>Event log archive<br/>$0.001/GB/month]
    end
    
    RDS -->|Continuous| T1
    RDS -->|3 AM UTC| T2
    RDS -->|Sunday 4 AM| T3
    RDS -->|1st of month| T4
    
    T4 -.->|Replicate| CrossRegion
    T1 -.->|Export| S3Archive
    
    style RDS fill:#4CAF50
    style T1 fill:#2196F3
    style T2 fill:#03A9F4
    style T3 fill:#00BCD4
    style T4 fill:#009688
    style CrossRegion fill:#FF9800
```

---

## Multi-Environment Setup

```mermaid
graph TB
    subgraph Production["Production Environment"]
        ProdDomain1[titantrakr.com]
        ProdDomain2[traktitan.com]
        ProdDomain3[tritontracker.com]
        ProdCF[CloudFront Prod]
        ProdLambda[Lambda: prod-gym-app<br/>Image: gym-app:prod]
        ProdDB[(RDS PostgreSQL<br/>prod-gym-app-db<br/>Always On)]
        
        ProdDomain1 --> ProdCF
        ProdDomain2 --> ProdCF
        ProdDomain3 --> ProdCF
        ProdCF --> ProdLambda
        ProdLambda --> ProdDB
    end
    
    subgraph Staging["Staging Environment"]
        StageDomain[staging.titantrakr.com]
        StageCF[CloudFront Staging]
        StageLambda[Lambda: staging-gym-app<br/>Image: gym-app:staging]
        StageDB[(RDS PostgreSQL<br/>staging-gym-app-db<br/>Stop Off-Hours)]
        
        StageDomain --> StageCF
        StageCF --> StageLambda
        StageLambda --> StageDB
    end
    
    subgraph Local["Local Development"]
        LocalApp[FastAPI + Uvicorn<br/>localhost:8000]
        LocalDB[(SQLite<br/>workspace/default/gym.db)]
        
        LocalApp --> LocalDB
    end
    
    subgraph Shared["Shared AWS Resources"]
        ECR[ECR Repository<br/>gym-app<br/>Tags: prod, staging, dev]
        Route53[Route53 Hosted Zones<br/>3 domains]
        ACM[ACM Certificates<br/>us-east-1]
    end
    
    ProdLambda -.->|Pull image| ECR
    StageLambda -.->|Pull image| ECR
    
    style Production fill:#4CAF50,color:#fff
    style Staging fill:#FF9800,color:#fff
    style Local fill:#2196F3,color:#fff
    style Shared fill:#9C27B0,color:#fff
```

---

## Deployment Pipeline

```mermaid
graph LR
    Dev[Developer<br/>Local Machine]
    Git[Git Repository<br/>main branch]
    
    subgraph Build["Build Phase"]
        Docker[Docker Build<br/>Dockerfile]
        Test[Run Tests<br/>pytest]
    end
    
    subgraph Deploy["Deployment"]
        ECR[Push to ECR<br/>Tag: staging]
        CFStaging[Deploy to Staging<br/>CloudFormation]
        TestStaging[Test Staging<br/>Manual QA]
        Promote[Promote Image<br/>Retag as prod]
        CFProd[Deploy to Prod<br/>CloudFormation Update]
    end
    
    Dev -->|git push| Git
    Git -->|Trigger| Docker
    Docker --> Test
    Test -->|Pass| ECR
    ECR --> CFStaging
    CFStaging --> TestStaging
    TestStaging -->|✓ Approved| Promote
    Promote --> CFProd
    
    style Dev fill:#4CAF50
    style TestStaging fill:#FF9800
    style CFProd fill:#F44336
```

---

## Request Flow (Detailed)

```mermaid
sequenceDiagram
    autonumber
    
    participant User as 👤 User
    participant DNS as Route53<br/>DNS
    participant CF as CloudFront<br/>CDN
    participant Lambda as AWS Lambda<br/>FastAPI
    participant Proxy as RDS Proxy
    participant DB as PostgreSQL
    participant Claude as Anthropic<br/>Claude API
    
    User->>DNS: https://titantrakr.com
    DNS-->>User: CNAME → CloudFront
    
    User->>CF: GET /
    
    alt Static Asset (Cached)
        CF-->>User: index.html (from cache)
    else Cache Miss
        CF->>Lambda: Invoke Function URL
        Lambda-->>CF: Serve frontend/index.html
        CF-->>User: HTML (cache for 5 min)
    end
    
    Note over User: User taps mic, says<br/>"bench press 100 for 8"
    
    User->>CF: POST /api/voice/process
    CF->>Lambda: Forward (no cache for /api/*)
    
    Lambda->>Claude: Process transcript<br/>+ workout context
    Claude-->>Lambda: Exercise: bench-press<br/>Weight: 100kg, Reps: 8
    
    Lambda->>Proxy: BEGIN TRANSACTION
    Proxy->>DB: SELECT data FROM projections<br/>WHERE key='current_workout'
    DB-->>Lambda: Current workout state
    
    Lambda->>Lambda: validate_preconditions()<br/>Check workout active
    
    Lambda->>Proxy: INSERT INTO events (...)
    Lambda->>Proxy: UPDATE projections SET data = ...
    Lambda->>Proxy: COMMIT
    
    Proxy->>DB: Execute transaction
    DB-->>Proxy: Success
    Proxy-->>Lambda: Committed
    
    Lambda-->>CF: 200 OK {success: true,<br/>message: "Logged 100kg × 8"}
    CF-->>User: JSON response
    
    Note over User: Display success<br/>Speak confirmation
```

---

## CloudFormation Stack Resources

```mermaid
graph TB
    subgraph Stack["CloudFormation Stack: gym-app-prod"]
        
        subgraph Networking["Networking (9 resources)"]
            VPC[VPC]
            IGW[Internet Gateway]
            Sub1[Public Subnet 1]
            Sub2[Public Subnet 2]
            Sub3[Private Subnet 1]
            Sub4[Private Subnet 2]
            RT[Route Table]
            SG1[Lambda Security Group]
            SG2[RDS Security Group]
        end
        
        subgraph Database["Database (8 resources)"]
            RDS[RDS DB Instance]
            Proxy[RDS Proxy]
            ProxyTG[Proxy Target Group]
            SubnetGrp[DB Subnet Group]
            Secret[Secrets Manager]
            ProxyRole[RDS Proxy IAM Role]
            KMS[KMS Key]
            ProxySG[RDS Proxy SG]
        end
        
        subgraph Compute["Compute (4 resources)"]
            Func[Lambda Function]
            Role[Lambda Execution Role]
            URL[Function URL]
            Perm[URL Permission]
        end
        
        subgraph CDN["CDN & DNS (4 resources)"]
            CFDist[CloudFront Distribution]
            DNS1[Route53 Record: titantrakr]
            DNS2[Route53 Record: www]
            DNS3[Route53 Record: alts]
        end
        
        subgraph SSL["SSL (1 resource)"]
            Cert[ACM Certificate<br/>us-east-1]
        end
        
        subgraph Backup["Backup (5 resources)"]
            BVault[Backup Vault]
            BPlan[Backup Plan]
            BSelect[Backup Selection]
            BRole[Backup IAM Role]
            BKMS[Backup KMS Key]
        end
    end
    
    Func --> Proxy
    Proxy --> RDS
    CFDist --> URL
    URL --> Func
    DNS1 --> CFDist
    CFDist -.->|SSL| Cert
    RDS -.->|Backups| BVault
    
    style Stack fill:#E8F5E9
    style Networking fill:#E3F2FD
    style Database fill:#F3E5F5
    style Compute fill:#FFF3E0
    style CDN fill:#FCE4EC
    style Backup fill:#FFEBEE
```

**Total Resources:** ~31 AWS resources created by one CloudFormation template

---

## Security Architecture

```mermaid
graph TB
    subgraph Public["Public Internet"]
        Users[Users Worldwide]
    end
    
    subgraph CloudFront["CloudFront Edge Locations"]
        Edge[150+ Edge Locations<br/>HTTPS Only<br/>TLS 1.2+]
    end
    
    subgraph Lambda["Lambda (No VPC for PFF Pattern)"]
        Func[Lambda Function<br/>Public subnet access<br/>Mangum + FastAPI]
    end
    
    subgraph VPC["VPC - Private Network"]
        subgraph PrivateSubnets["Private Subnets"]
            Proxy[RDS Proxy<br/>Connection pooling<br/>No public IP]
            DB[RDS PostgreSQL<br/>Encrypted at rest<br/>No public access]
        end
    end
    
    subgraph IAM["Identity & Access"]
        LambdaRole[Lambda Execution Role<br/>Secrets: Read<br/>CloudWatch: Write<br/>VPC: Access]
        ProxyRole[RDS Proxy Role<br/>Secrets: Read only]
        BackupRole[Backup Service Role<br/>RDS: Snapshot<br/>S3: Write]
    end
    
    subgraph Secrets["Secrets Management"]
        SM[Secrets Manager<br/>DB Credentials<br/>Encrypted with KMS]
        KMS[KMS Keys<br/>Backup encryption<br/>DB encryption]
    end
    
    Users -->|HTTPS<br/>ACM Cert| Edge
    Edge -->|TLS| Func
    Func -.->|Assume| LambdaRole
    Func -->|Encrypted conn| Proxy
    Proxy -.->|Assume| ProxyRole
    ProxyRole -->|Read| SM
    Proxy -->|TLS| DB
    
    DB -.->|Encrypt| KMS
    DB -.->|Snapshot| BackupRole
    
    style Users fill:#4CAF50
    style Edge fill:#FF9800
    style Func fill:#2196F3
    style DB fill:#9C27B0
    style KMS fill:#F44336
```

### Security Features

| Layer | Security Measure |
|-------|------------------|
| **Transport** | TLS 1.2+ (CloudFront to user) |
| **Application** | JWT tokens (future auth) |
| **Network** | Security groups (least privilege) |
| **Database** | Private subnet, no public IP |
| **Data at rest** | RDS encryption, KMS keys |
| **Credentials** | Secrets Manager (not env vars) |
| **Backups** | KMS encrypted vault |

---

## Cost Architecture (Monthly)

```mermaid
graph TB
    subgraph Production["Production: $31.50/month"]
        P1[RDS PostgreSQL<br/>$12]
        P2[RDS Proxy<br/>$11]
        P3[CloudFront<br/>$5]
        P4[AWS Backup<br/>$2]
        P5[Route53<br/>$1.50]
        P6[Lambda<br/>$0 free tier]
    end
    
    subgraph Staging["Staging: $6/month"]
        S1[RDS PostgreSQL<br/>$5 w/ stop schedule]
        S2[CloudFront<br/>$1]
        S3[Lambda<br/>$0 free tier]
    end
    
    subgraph Variable["Variable Costs"]
        V1[LLM API Calls<br/>$10-50/month<br/>depends on usage]
        V2[Data Transfer<br/>$0.09/GB<br/>after 1TB/month]
    end
    
    Total[Total: $37.50/month base<br/>+ $10-50 LLM usage]
    
    Production --> Total
    Staging --> Total
    Variable -.->|Usage-based| Total
    
    style Production fill:#4CAF50,color:#fff
    style Staging fill:#FF9800,color:#fff
    style Variable fill:#F44336,color:#fff
    style Total fill:#9C27B0,color:#fff
```

### Cost Breakdown Table

| Tier | Component | Staging | Production | Notes |
|------|-----------|---------|------------|-------|
| **Always On** | RDS db.t4g.micro | $5 | $12 | Stop staging off-hours |
| **Always On** | RDS Proxy | $0 | $11 | Staging direct connect |
| **Always On** | Route53 (3 zones) | Shared | $1.50 | Shared cost |
| **Usage-Based** | Lambda | $0 | $0 | Within free tier (1M requests) |
| **Usage-Based** | CloudFront | $1 | $5 | Data transfer + requests |
| **Usage-Based** | AWS Backup | $0 | $2 | Storage only |
| **Usage-Based** | LLM APIs | ~$5 | ~$30 | Voice command processing |
| **Total** | | **$6-11** | **$31.50-61.50** | Depends on usage |

---

## Scaling Path

```mermaid
graph LR
    subgraph Current["Current: MVP<br/>$40/month"]
        L1[Lambda 512MB]
        R1[RDS t4g.micro]
        C1[CloudFront]
    end
    
    subgraph Phase2["Phase 2: 10k DAU<br/>$80/month"]
        L2[Lambda 1024MB]
        R2[RDS t4g.small<br/>Read Replica]
        C2[CloudFront]
        Cache[ElastiCache Redis<br/>Session cache]
    end
    
    subgraph Phase3["Phase 3: 100k DAU<br/>$300/month"]
        L3[Lambda 2048MB]
        R3[Aurora Serverless v2<br/>Multi-AZ]
        C3[CloudFront]
        Cache2[ElastiCache Redis<br/>Cluster mode]
        ECS[ECS Fargate<br/>Background workers]
    end
    
    subgraph Phase4["Phase 4: 1M+ DAU<br/>$1000+/month"]
        L4[Lambda @Edge]
        R4[Aurora Global DB<br/>Multi-region]
        C4[CloudFront]
        DDB[DynamoDB<br/>Real-time data]
        Kinesis[Kinesis<br/>Event streaming]
    end
    
    Current -->|Growth| Phase2
    Phase2 -->|Scale| Phase3
    Phase3 -->|Enterprise| Phase4
    
    style Current fill:#4CAF50,color:#fff
    style Phase2 fill:#2196F3,color:#fff
    style Phase3 fill:#FF9800,color:#fff
    style Phase4 fill:#F44336,color:#fff
```

---

## Infrastructure Components Summary

### Core Services (7)

1. **Route53** - DNS management for 3 domains
2. **ACM** - SSL certificates (free)
3. **CloudFront** - Global CDN (150+ edge locations)
4. **Lambda** - Serverless compute (FastAPI + Mangum)
5. **RDS PostgreSQL** - Relational database
6. **RDS Proxy** - Connection pooling
7. **AWS Backup** - Advanced backup management

### Supporting Services (4)

8. **VPC** - Network isolation for database
9. **Secrets Manager** - Database credentials
10. **IAM Roles** - Least-privilege access
11. **CloudWatch** - Logs and metrics

### Optional Services (3)

12. **SES** - Email (if you add notifications)
13. **S3** - Long-term archives (optional)
14. **EventBridge** - Scheduled tasks (DB start/stop)

---

## Comparison: PassportPhotoFactory vs Gym App

```mermaid
graph TB
    subgraph PFF["PassportPhotoFactory Architecture"]
        PFFDNS[Route53:<br/>passportphotofactory.com]
        PFFCF[CloudFront]
        PFFLambda[Lambda: passport<br/>Docker, 768MB, 60s]
        PFFDB[(DynamoDB<br/>Pay-per-request<br/>18,627 items)]
        PFFS3[S3: passport-photo-factory<br/>Photo storage]
        PFFSQS[SQS: Processing queue<br/>Async jobs]
        PFFSES[SES: Email<br/>Order confirmations]
        
        PFFDNS --> PFFCF
        PFFCF --> PFFLambda
        PFFLambda --> PFFDB
        PFFLambda --> PFFS3
        PFFLambda --> PFFSQS
        PFFLambda --> PFFSES
    end
    
    subgraph GYM["Gym App Architecture"]
        GYMDNS[Route53:<br/>titantrakr.com + 2 alts]
        GYMCF[CloudFront]
        GYMLambda[Lambda: gym-app<br/>Docker, 512MB, 30s]
        GYMDB[(RDS PostgreSQL<br/>db.t4g.micro<br/>+ RDS Proxy)]
        GYMBackup[AWS Backup<br/>3-tier strategy]
        
        GYMDNS --> GYMCF
        GYMCF --> GYMLambda
        GYMLambda --> GYMDB
        GYMDB -.-> GYMBackup
    end
    
    style PFF fill:#E1F5FE
    style GYM fill:#F3E5F5
```

### Key Similarities

- ✅ CloudFront → Lambda Function URL pattern
- ✅ FastAPI serves both frontend and API
- ✅ Docker-based Lambda (easier deployment)
- ✅ No API Gateway (simpler, cheaper)
- ✅ Route53 + ACM for custom domains
- ✅ Serverless compute (Lambda scales automatically)

### Key Differences

| Aspect | PFF | Gym App |
|--------|-----|---------|
| **Database** | DynamoDB (NoSQL) | RDS PostgreSQL (SQL) |
| **VPC** | No | Yes (for RDS) |
| **Connection Pooling** | N/A | RDS Proxy |
| **Backup** | DynamoDB PITR | RDS + AWS Backup |
| **Storage** | S3 (photos) | None (no files) |
| **Async Jobs** | SQS + Lambda | None yet |
| **Email** | SES | None yet |

---

## Event-Sourcing Pattern on AWS

```mermaid
graph TB
    subgraph Events["Event Store (Immutable)"]
        E1[WorkoutStarted<br/>timestamp: 2024-01-01T10:00:00Z]
        E2[ExerciseAdded<br/>timestamp: 2024-01-01T10:01:00Z]
        E3[SetLogged<br/>timestamp: 2024-01-01T10:05:00Z]
        E4[SetLogged<br/>timestamp: 2024-01-01T10:08:00Z]
        E5[WorkoutCompleted<br/>timestamp: 2024-01-01T11:00:00Z]
    end
    
    subgraph Projections["Projections (Derived State)"]
        P1[current_workout<br/>Null]
        P2[workout_history<br/>[{...workout data...}]]
        P3[exercise_history:bench-press<br/>{last_weight: 80kg}]
        P4[personal_records:bench-press<br/>{max_weight: 100kg}]
    end
    
    subgraph Storage["PostgreSQL Storage"]
        Events -->|events table<br/>JSONB payload| PG[(PostgreSQL)]
        Projections -->|projections table<br/>JSONB data| PG
    end
    
    E1 -.->|Build| P1
    E2 -.->|Build| P1
    E3 -.->|Build| P1
    E4 -.->|Build| P1
    E5 -.->|Build| P2
    E5 -.->|Clear| P1
    E3 -.->|Update| P3
    E4 -.->|Update| P3
    E4 -.->|Check PR| P4
    
    style Events fill:#4CAF50
    style Projections fill:#2196F3
    style PG fill:#9C27B0
```

**Why This Works on PostgreSQL:**
- ✅ JSONB columns for flexible event payloads
- ✅ ACID transactions (validate → write → update atomically)
- ✅ Indexes on timestamp and event_type
- ✅ Your `IMMEDIATE` isolation level prevents race conditions

---

## Deployment States

```mermaid
stateDiagram-v2
    [*] --> LocalDevelopment
    
    LocalDevelopment --> BuildDocker: Code Complete
    BuildDocker --> PushECR: Tests Pass
    PushECR --> DeployStaging: Image Ready
    
    DeployStaging --> TestingStaging: Stack Created
    TestingStaging --> DeployStaging: Bugs Found
    TestingStaging --> PromoteToProduction: QA Approved
    
    PromoteToProduction --> ProductionLive: Stack Updated
    ProductionLive --> MonitorProduction: Deploy Complete
    
    MonitorProduction --> Rollback: Errors Detected
    MonitorProduction --> LocalDevelopment: New Features
    Rollback --> ProductionLive: Previous Version
    
    note right of LocalDevelopment
        SQLite database
        Uvicorn server
        Hot reload
    end note
    
    note right of TestingStaging
        staging.titantrakr.com
        Separate RDS
        Safe to break
    end note
    
    note right of ProductionLive
        titantrakr.com
        Full backups
        Monitoring active
    end note
```

---

## Monitoring & Observability

```mermaid
graph TB
    subgraph Sources["Data Sources"]
        L[Lambda Logs<br/>CloudWatch Logs]
        DB[RDS Metrics<br/>CPU, Connections, IOPS]
        CF[CloudFront Metrics<br/>Requests, Errors, Latency]
        Backup[Backup Jobs<br/>Success/Failure]
    end
    
    subgraph Processing["Processing"]
        CW[CloudWatch<br/>Metrics & Logs]
        Alarms[CloudWatch Alarms]
    end
    
    subgraph Notifications["Notifications"]
        SNS[SNS Topic<br/>gym-app-alerts]
        Email[📧 Email]
        SMS[📱 SMS Optional]
        Slack[💬 Slack Webhook]
    end
    
    subgraph Dashboards["Dashboards"]
        D1[CloudWatch Dashboard<br/>Real-time metrics]
        D2[Cost Explorer<br/>Spending trends]
        D3[RDS Performance Insights<br/>Query analysis]
    end
    
    L --> CW
    DB --> CW
    CF --> CW
    Backup --> CW
    
    CW --> Alarms
    Alarms -->|Trigger| SNS
    SNS --> Email
    SNS --> SMS
    SNS --> Slack
    
    CW --> D1
    DB --> D3
    
    style Alarms fill:#F44336,color:#fff
    style SNS fill:#FF9800
    style D1 fill:#2196F3,color:#fff
```

---

## Key Metrics to Monitor

### Application Health

- Lambda invocations per minute
- Lambda errors (4xx, 5xx)
- Lambda duration (p50, p95, p99)
- Lambda cold start rate
- Voice processing success rate

### Database Health

- RDS CPU utilization
- RDS freeable memory
- RDS database connections (should be < 100)
- RDS read/write IOPS
- RDS Proxy connections (pool efficiency)

### CDN Performance

- CloudFront cache hit ratio (target: >80%)
- CloudFront origin latency
- CloudFront 4xx/5xx error rate
- CloudFront data transfer (cost tracking)

### Backup Integrity

- Backup job success rate (target: 100%)
- Backup storage used (growth trend)
- Backup restore test results (monthly)

---

## Architecture Decisions Rationale

### Why Lambda (not EC2/ECS)?
- ✅ Serverless = zero maintenance
- ✅ Auto-scaling (0 to thousands of concurrent users)
- ✅ Pay per request (not idle time)
- ✅ Matches your proven PFF pattern

### Why RDS Proxy?
- ✅ Lambda creates new DB connections per invocation
- ✅ Without proxy: connection exhaustion at scale
- ✅ With proxy: connection pooling + reuse
- ✅ Production-grade best practice

### Why PostgreSQL (not DynamoDB like PFF)?
- ✅ Full SQL support (complex queries, JOINs)
- ✅ JSONB for flexible event payloads
- ✅ ACID transactions (your event-sourcing needs this)
- ✅ Easier migration from SQLite (minimal code changes)
- ✅ Better for relational data (users, workouts, exercises)

### Why VPC (PFF doesn't use it)?
- ✅ RDS requires VPC (private subnets)
- ✅ Database not exposed to public internet
- ✅ Security best practice
- ⚠️ Adds complexity (NAT Gateway for internet access)

### Why Docker Image (not ZIP)?
- ✅ Easier dependency management (psycopg2 compiled binaries)
- ✅ Consistent builds (local = prod)
- ✅ Faster deployments (layer caching)
- ✅ Matches your PFF pattern

---

## Summary

You now have a **production-ready, serverless, multi-environment AWS architecture** that:

1. ✅ Replicates your PassportPhotoFactory pattern
2. ✅ Uses PostgreSQL (your preference over DynamoDB)
3. ✅ Supports staging + production environments
4. ✅ Includes comprehensive 3-tier backup strategy
5. ✅ Handles SSL for 3 domains automatically
6. ✅ Scales automatically with Lambda
7. ✅ Costs ~$40/month for both environments
8. ✅ One-command deployment scripts
9. ✅ Complete monitoring and alerting
10. ✅ Disaster recovery capabilities

**Total Infrastructure: 31 AWS resources, managed by CloudFormation**

Deploy with:
```bash
./infrastructure/scripts/deploy.sh staging
./infrastructure/scripts/deploy.sh prod
```



