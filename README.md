# PAI Server (Pepper)

**Production-ready AI assistant backend with Clean Architecture, multi-platform client support, and Claude AI integration.**

- **External Name:** Pepper
- **Internal Name:** PAI (Personal AI)

## Vision

Pepper is a personal AI assistant with:
- **Chat-first interface** (WhatsApp-style) with voice option
- **Smart command routing** (#calendar, #note, #scan)
- **Multi-platform clients** (Web, iOS, Android, Windows PWA)
- **Calendar integration** (Google + Microsoft)
- **Claude AI** conversation with streaming responses

## Current Status: v0.5

### Completed Features

**v0.1 - OAuth & Calendar Integration:**
- JWT authentication (register, login, user management)
- OAuth 2.0 device flow (Google + Microsoft)
- Calendar CRUD operations (list, create, update, delete events)
- Multi-provider calendar support
- Token refresh handling

**v0.2 - Chat & AI Conversation:**
- Conversation management (create, list, delete)
- Message history and context
- Claude AI integration (Anthropic API)
- Streaming responses via SSE (Server-Sent Events)
- Command parser (#calendar, #note, #scan, #help)
- 4 conversation modes (chat, voice, note, scan)
- Mode-specific system prompts (Dutch optimized)

**v0.3-0.5 - Cross-Platform Web Client:**
- React 19 + TypeScript + Vite
- Capacitor for mobile (iOS + Android)
- PWA for Windows
- Paperless-ngx inspired UI (MainLayout + Sidebar)
- SSE streaming support
- Pepper branding

## Architecture

### Backend: Clean Architecture

```
┌─────────────────────────────────────────────────┐
│         Presentation Layer                      │
│  (FastAPI Routes, SSE Streaming)                │
├─────────────────────────────────────────────────┤
│         Application Layer                       │
│  (Use Cases, Business Orchestration)            │
├─────────────────────────────────────────────────┤
│         Domain Layer                            │
│  (Entities, Value Objects, Services)            │
├─────────────────────────────────────────────────┤
│         Infrastructure Layer                    │
│  (Database, OAuth, Claude API, Calendar APIs)   │
└─────────────────────────────────────────────────┘
```

## Project Structure

```
pai-server/
├── app/
│   ├── main.py                          # FastAPI application
│   ├── core/
│   │   ├── config.py                    # Settings & environment
│   │   └── dependencies.py              # DI providers, auth
│   ├── domain/
│   │   ├── entities/                    # Domain entities
│   │   └── services/                    # Domain services
│   ├── application/
│   │   └── use_cases/                   # Business logic
│   ├── infrastructure/
│   │   ├── database/                    # SQLAlchemy models & session
│   │   ├── repositories/                # Data access
│   │   └── services/                    # External integrations
│   └── presentation/
│       └── routers/                     # API endpoints
├── alembic/                             # Database migrations
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- PostgreSQL 15
- Python 3.11+ (for local development)
- Anthropic API key (for Claude AI)

### 1. Clone Repository

```bash
git clone https://github.com/Frank19661129/pai-server.git
cd pai-server
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```bash
# Database
DATABASE_URL=postgresql://pai:password@pai-postgres:5432/pai

# Security
SECRET_KEY=your-secret-key-here

# OAuth - Google Calendar
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# OAuth - Microsoft Calendar
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_TENANT_ID=common

# Claude AI
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### 3. Start Server

```bash
docker-compose up -d
```

### 4. Verify Health

```bash
curl http://localhost:8003/api/v1/health
# {"status":"healthy","service":"Pepper","version":"0.5"}
```

### 5. Access API Documentation

- **Swagger UI:** http://localhost:8003/docs
- **ReDoc:** http://localhost:8003/redoc

## API Endpoints

### Health
- `GET /api/v1/health` - Service health check

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with email/password
- `GET /api/v1/auth/me` - Get current user info

### Calendar OAuth
- `POST /api/v1/calendar/oauth/google/start` - Start Google device flow
- `POST /api/v1/calendar/oauth/google/poll` - Poll for Google token
- `POST /api/v1/calendar/oauth/microsoft/start` - Start Microsoft device flow
- `POST /api/v1/calendar/oauth/microsoft/poll` - Poll for Microsoft token
- `DELETE /api/v1/calendar/oauth/{provider}` - Disconnect provider
- `GET /api/v1/calendar/oauth/connected` - List connected providers

### Calendar Operations
- `GET /api/v1/calendar/calendars` - List calendars
- `GET /api/v1/calendar/events` - List events
- `POST /api/v1/calendar/events` - Create event
- `PUT /api/v1/calendar/events/{id}` - Update event
- `DELETE /api/v1/calendar/events/{id}` - Delete event

### Conversations (Chat & AI)
- `POST /api/v1/conversations` - Create conversation
- `GET /api/v1/conversations` - List conversations
- `GET /api/v1/conversations/{id}` - Get conversation with messages
- `POST /api/v1/conversations/{id}/messages` - Send message
- `POST /api/v1/conversations/{id}/messages/stream` - Send message (SSE stream)
- `DELETE /api/v1/conversations/{id}` - Delete conversation

## Technology Stack

### Backend
- **Framework:** FastAPI 0.109+
- **Language:** Python 3.11+
- **Database:** PostgreSQL 15
- **ORM:** SQLAlchemy 2.0+
- **Migrations:** Alembic
- **AI:** Claude 3.5 Sonnet (Anthropic API)
- **OAuth:** Google + Microsoft device flow

### DevOps
- **Containerization:** Docker & Docker Compose
- **Container Names:** pai-server, pai-postgres, pai-gateway, etc.

## Port Configuration

- **Server:** Port 8003 (external) → 8000 (internal)
- **PostgreSQL:** Port 5432
- **Client:** Port 5173

## Security

- JWT authentication with bcrypt password hashing
- OAuth 2.0 device flow (no client secrets exposed)
- Token refresh handling
- CORS configuration
- Environment-based secrets

## Related Repositories

- **Client:** [pai-client](https://github.com/Frank19661129/pai-client)

## License

Private project - All rights reserved

---

**Version:** 0.5 (Pepper Kerst 2025)
**Maintainer:** [Franklab](https://www.franklab.nl)
