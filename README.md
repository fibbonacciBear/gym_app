# Titan Trakr 💪

A **voice-first** workout tracking application built for speed, simplicity, and intelligent logging. Log sets with your voice in seconds, track progress with automatic PR detection, and sync across devices with cloud deployment.

## ✨ Features

### Core Functionality
- 🎤 **Voice-First Logging**: Log sets naturally with voice commands like "185 for 8"
- 📊 **Automatic PR Detection**: Get instant feedback when you hit a new personal record
- 📱 **Card Mode**: Full-screen glanceable HUD optimized for voice interaction at the gym
- 🎯 **Smart Templates**: Create workout templates with target sets, reps, and rest timers
- 📈 **Progress Tracking**: View workout history with volume and exercise analytics
- 🔄 **Event Sourcing**: Immutable event log ensures data integrity and full audit trail

### Voice Experience
- Continuous listening with interim results
- Text-to-speech confirmations (toggle on/off)
- Contextual voice hints
- Plan Builder mode for creating templates via voice
- Auto-add exercises when logging sets

### Technical Highlights
- **Event-Driven Architecture**: Append-only event store with derived projections
- **Multi-LLM Support**: OpenAI GPT-4o-mini or Anthropic Claude Haiku (configurable)
- **Serverless AWS Deployment**: Lambda + RDS + CloudFront for global scale
- **Responsive UI**: Dark mode, large touch targets, mobile-optimized

## 🏗️ Tech Stack

### Frontend
- **Alpine.js** - Lightweight reactive framework
- **TailwindCSS** - Utility-first styling
- **Web Speech API** - Voice recognition and synthesis
- Vanilla JavaScript (ES6+)

### Backend
- **FastAPI** - Modern Python web framework
- **SQLite** (local dev) / **PostgreSQL** (production & local testing)
- **Pydantic** - Data validation and schemas
- **OpenAI/Anthropic** - LLM for voice command parsing
- **psycopg2** - PostgreSQL adapter

### Infrastructure
- **AWS Lambda** (Docker) - Serverless compute
- **AWS RDS PostgreSQL** - Managed database
- **AWS RDS Proxy** - Connection pooling
- **AWS CloudFront** - Global CDN
- **AWS Route53** - DNS management
- **AWS ACM** - SSL certificates
- **CloudFormation** - Infrastructure as Code

## 🚀 Quick Start

### Local Development

1. **Clone the repository**
```bash
git clone <repo-url>
cd gym_app
```

2. **Set up Python environment**
```bash
conda env create -f environment.yml
conda activate gym_app
```

3. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys:
# ANTHROPIC_API_KEY=your-key-here
# or
# OPENAI_API_KEY=your-key-here
# USE_OPENAI=false  # Set to true for OpenAI
```

4. **Run the development server**
```bash
uvicorn backend.main:app --reload --port 8000
```

5. **Open in browser**
```
http://localhost:8000
```

### Local PostgreSQL Testing (Optional)

For production-like testing with PostgreSQL before AWS deployment:

1. **Start PostgreSQL with Docker**
```bash
docker-compose up -d
```

2. **Configure PostgreSQL connection**
```bash
# In .env file, add:
DATABASE_URL=postgresql://gymuser:gympass123@localhost:5432/gym_app
```

3. **Test database connection**
```bash
python test_database.py
```

4. **Run app with PostgreSQL**
```bash
uvicorn backend.main:app --reload --port 8000
```

See [infrastructure/LOCAL_POSTGRES_SETUP.md](infrastructure/LOCAL_POSTGRES_SETUP.md) for detailed PostgreSQL setup guide.

### Testing Voice Commands

Once running, try these voice commands:
- **Start workout**: "Start push day"
- **Log a set**: "185 for 8" (assumes current exercise)
- **Add exercise**: "Add bench press"
- **Finish workout**: "Finish workout"

## 🏗️ Project Structure

```
gym_app/
├── backend/                    # FastAPI backend
│   ├── api/                   # API endpoints
│   │   ├── history.py        # Workout history
│   │   ├── templates.py      # Template management
│   │   └── voice.py          # Voice processing
│   ├── schema/               # Event schemas
│   │   └── events.py         # Event type definitions
│   ├── config.py             # Configuration
│   ├── database.py           # Database layer
│   ├── events.py             # Event sourcing logic
│   ├── llm.py                # LLM integration
│   ├── main.py               # FastAPI app entry
│   └── models.py             # Pydantic models
├── frontend/                  # Static frontend
│   ├── css/
│   │   └── styles.css        # Custom styles
│   ├── js/
│   │   ├── api.js            # API client
│   │   ├── app.js            # Alpine.js app logic
│   │   └── voice.js          # Voice integration
│   └── index.html            # Main UI
├── infrastructure/            # AWS deployment
│   ├── scripts/
│   │   ├── build-and-push.sh # Docker build script
│   │   └── deploy.sh         # CloudFormation deploy
│   ├── cloudformation-simple.yaml
│   ├── Dockerfile
│   ├── lambda_handler.py
│   ├── requirements-lambda.txt
│   ├── deploy-parameters.json          # Production config
│   ├── deploy-parameters-staging.json  # Staging config
│   ├── AWS_DEPLOYMENT_ARCHITECTURE.md
│   ├── BACKUP_STRATEGY.md
│   ├── DEPLOYMENT.md
│   └── MULTI_ENVIRONMENT.md
├── data/
│   └── exercises.json        # Exercise database
├── docs/                      # Project documentation
│   ├── app_specification.md
│   ├── technical_specification.md
│   ├── implementation_plan.md
│   ├── future_features.md
│   ├── monetization_strategy.md
│   ├── production_architecture.md
│   └── ux_friction.md
├── tests/                     # Test suite
├── workspace/                 # User data (gitignored)
├── environment.yml            # Conda environment
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## ☁️ AWS Deployment

### Prerequisites
- AWS CLI configured with credentials
- Docker installed and running
- Domain registered in Route53 (e.g., `titantrakr.com`)
- API keys for Anthropic or OpenAI

### Deploy to Production

1. **Update deployment parameters**
```bash
# Edit infrastructure/deploy-parameters.json
# Set your DB password, API keys, and domain
```

2. **Make scripts executable**
```bash
chmod +x infrastructure/scripts/*.sh
```

3. **Deploy**
```bash
./deploy-production.sh
```

This will:
- Build Docker image for Lambda
- Push to ECR
- Deploy CloudFormation stack (31 resources)
- Configure SSL certificates
- Set up CloudFront CDN
- Create RDS PostgreSQL database
- Configure 3-tier backup strategy

### Deploy to Staging

```bash
./deploy-staging.sh
```

### Architecture Overview

```
User → CloudFront (CDN) → Lambda (FastAPI) → RDS Proxy → RDS PostgreSQL
                                     ↓
                              AWS Backup (3-tier)
```

See [infrastructure/AWS_DEPLOYMENT_ARCHITECTURE.md](infrastructure/AWS_DEPLOYMENT_ARCHITECTURE.md) for detailed architecture diagrams.

## 📚 Documentation

- **[Application Specification](docs/app_specification.md)** - Detailed feature specs and user stories
- **[Technical Specification](docs/technical_specification.md)** - Architecture and design decisions
- **[Implementation Plan](docs/implementation_plan.md)** - Sprint breakdown and development roadmap
- **[AWS Deployment Guide](infrastructure/DEPLOYMENT.md)** - Step-by-step deployment instructions
- **[Backup Strategy](infrastructure/BACKUP_STRATEGY.md)** - Database backup and recovery procedures
- **[Multi-Environment Setup](infrastructure/MULTI_ENVIRONMENT.md)** - Staging and production environments
- **[Future Features](docs/future_features.md)** - Planned enhancements and integrations
- **[Monetization Strategy](docs/monetization_strategy.md)** - Business model and revenue options

## 🧪 Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=backend tests/
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `USE_OPENAI` | Use OpenAI instead of Anthropic | No | `false` |
| `OPENAI_API_KEY` | OpenAI API key | If USE_OPENAI=true | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | If USE_OPENAI=false | - |
| `DATABASE_URL` | PostgreSQL connection string | No | SQLite (local) |

**Note**: When `DATABASE_URL` is set, the app uses PostgreSQL. When empty, it uses SQLite. This allows seamless switching between local dev (SQLite) and production-like testing (PostgreSQL).

### Database Migration

For production deployment with PostgreSQL:
1. Existing SQLite events can be exported
2. PostgreSQL schema matches SQLite (seamless migration)
3. Event sourcing ensures data integrity during migration

## 🎯 Event Types

The app uses event sourcing with these event types:

- `WorkoutStarted` - Begin a new workout session
- `WorkoutCompleted` - Finish and save a workout
- `WorkoutDiscarded` - Cancel a workout without saving
- `ExerciseAdded` - Add an exercise to current workout
- `SetLogged` - Log a set (weight × reps)
- `SetModified` - Modify an existing set
- `SetDeleted` - Remove a set
- `TemplateCreated` - Create a workout template
- `TemplateUpdated` - Modify a template
- `TemplateDeleted` - Remove a template

## 🚧 Known Limitations

- Voice recognition requires HTTPS (localhost or deployed)
- Browser must support Web Speech API (Chrome, Safari, Edge)
- LLM API key required for voice command parsing
- Single-user system (multi-user support planned)

## 🗺️ Roadmap

### Near Term
- [ ] Exercise library expansion
- [ ] Social features (share workouts)
- [ ] Progressive web app (PWA) support
- [ ] Export workout data (CSV, JSON)

### Long Term
- [ ] Native mobile apps (iOS, Android)
- [ ] Wearable integration (Apple Watch, Garmin)
- [ ] Health platform sync (Apple Health, Google Fit)
- [ ] AI workout recommendations
- [ ] Multi-user accounts and authentication

See [docs/future_features.md](docs/future_features.md) for complete roadmap.

## 🤝 Contributing

This is a personal project, but feedback and suggestions are welcome! Please open an issue for bugs or feature requests.

## 📝 License

[Your License Here - e.g., MIT]

## 👤 Author

Built with ❤️ by [Your Name]

---

**Live Demo**: [https://titantrakr.com](https://titantrakr.com) (coming soon)

**Staging**: [https://staging.titantrakr.com](https://staging.titantrakr.com) (coming soon)

