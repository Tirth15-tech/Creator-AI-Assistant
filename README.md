# ContentAI — AI-Powered Social Media Content Assistant

Full-stack web application that analyzes uploaded images, video, audio, documents, and text,
then generates optimized social media content: captions, hashtags, keywords, emojis, hooks,
CTAs, SEO tags, summaries, and translations.

## Tech Stack of project

- **Frontend:** HTML5, CSS3, Bootstrap 5, vanilla JavaScript
- **Backend:** Python, FastAPI, Uvicorn
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Auth:** JWT + bcrypt
- **AI Models:** Gemma 3 (Ollama), YOLOv8, CLIP, BLIP-2, Whisper, EasyOCR

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Ollama (for AI features)

### 1. Database Setup

```sql
-- Connect to PostgreSQL and create the database + user
CREATE USER contentai WITH PASSWORD 'contentai';
CREATE DATABASE contentai OWNER contentai;
```

### 2. Python Environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. Environment Variables

Copy `.env.example` to `.env` and update values as needed.
At minimum, set a strong `JWT_SECRET_KEY`.

### 4. Run Migrations

```bash
alembic upgrade head
```

### 5. Start the Dev Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit: http://localhost:8000

### 6. Ollama Setup (for AI features)

```bash
# Install Ollama: https://ollama.ai
ollama pull gemma3:4b
ollama serve
```

The server must be running at `http://localhost:11434` (default).

## Key Features

| Feature | Status | Description |
|---------|--------|-------------|
| User Auth | ✅ | JWT + bcrypt, register, login, refresh tokens |
| Image Upload | ✅ | JPG, PNG, WEBP, GIF, BMP, HEIC with preview |
| Video Upload | ✅ | MP4, MOV, AVI, WEBM, MKV (max 2 min) with frame extraction |
| Audio Upload | ✅ | MP3, WAV, OGG, M4A, AAC with Whisper transcription |
| Document Upload | ✅ | PDF, DOCX, TXT with text extraction |
| Caption Generator | ✅ | 9 caption styles: default, long, short, funny, professional, travel, business, food, luxury |
| Hashtag Generator | ✅ | Trend-aware hashtag suggestions |
| Keyword Generator | ✅ | Content-aware keyword extraction |
| Emoji Generator | ✅ | Context-relevant emoji suggestions |
| CTA Generator | ✅ | Platform-optimized call-to-action |
| Hook Generator | ✅ | Attention-grabbing hooks |
| SEO Tags | ✅ | Discoverability-optimized tags |
| Summaries | ✅ | AI-powered content summaries |
| Viral Scoring | ✅ | 1-100 viral potential with reasoning |
| Translation | ✅ | 20+ languages via Ollama + MyMemory fallback |
| Rewrite | ✅ | 8 tones × 4 lengths |
| Export | ✅ | TXT, CSV, DOCX, PDF, JSON |
| Quality Check | ✅ | Image (blur, brightness, resolution) & Video (duration, codec, bitrate) |
| Social Accounts | ✅ | Instagram OAuth connect/disconnect |
| Publishing | ✅ | Instagram Graph API (Business/Creator accounts) |
| Scheduling | ✅ | Date/time scheduling with background scheduler |
| Drafts | ✅ | Full CRUD for content drafts |
| Posting History | ✅ | Track published posts with engagement metrics |
| Notifications | ✅ | In-app notifications for posts, schedules, errors |
| Analytics | ✅ | Post stats, engagement metrics, content breakdown |
| Rate Limiting | ✅ | 60 req/min per IP to prevent abuse |
| Recurring Posts | ✅ | Design support for recurring schedules |
| Modular Providers | ✅ | Interface for Facebook, LinkedIn, X, Threads, YouTube |

## Project Structure

```
contentai/
├── app/
│   ├── api/            # Route handlers
│   │   ├── auth.py     # Auth endpoints
│   │   ├── pages.py    # Page routes
│   │   ├── posts.py    # Upload, generate, regenerate, translate, rewrite
│   │   ├── social.py   # Social media accounts, drafts, scheduling, publishing
│   │   ├── admin.py    # Admin panel (users, stats, ban)
│   │   ├── export.py   # Export post content (txt, csv, docx, pdf, json)
│   │   └── analytics.py # Analytics dashboard data
│   ├── core/
│   │   ├── config.py   # Settings from .env
│   │   ├── database.py # SQLAlchemy engine/session
│   │   ├── security.py # JWT + password hashing
│   │   └── rate_limit.py # In-memory rate limiter middleware
│   ├── models/         # SQLAlchemy models
│   │   ├── user.py
│   │   ├── post.py
│   │   └── social.py   # SocialAccount, Draft, ScheduledPost, PostingHistory, Notification
│   ├── schemas/        # Pydantic schemas
│   │   └── auth.py
│   ├── services/       # Business logic
│   │   ├── ai_provider.py        # Ollama LLM + fallback generators
│   │   ├── content_pipeline.py   # Orchestrates generation from all media types
│   │   ├── image_analyzer.py     # YOLOv8, CLIP, BLIP-2 analysis
│   │   ├── video_processor.py    # OpenCV/FFmpeg video processing
│   │   ├── audio_transcriber.py  # Whisper speech-to-text
│   │   ├── document_extractor.py # PDF/DOCX text extraction
│   │   ├── ocr_service.py        # EasyOCR text extraction
│   │   ├── quality_checker.py    # Image/video quality assessment
│   │   ├── exporter.py           # Export to txt, csv, docx, pdf, json
│   │   └── scheduler.py          # Background post scheduler
│   ├── social/         # Social media provider framework
│   │   ├── base.py     # Abstract SocialProvider interface
│   │   ├── registry.py # Provider registration & lookup
│   │   └── providers/
│   │       └── instagram.py # Instagram Graph API implementation
│   └── main.py         # FastAPI app entry
├── templates/          # Jinja2 HTML templates
├── static/             # CSS, JS, images
├── uploads/            # User uploaded files
├── alembic/            # DB migrations
├── alembic.ini
├── requirements.txt
├── .env
└── README.md
```

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Done | Foundation: Auth, DB, Templates |
| 2 | ✅ Done | Text & Image Pipeline: YOLOv8, CLIP, BLIP-2, LLM (Ollama), all caption types, hashtags, keywords, SEO, hooks, CTA, emojis, summaries, viral scoring |
| 3 | ✅ Done | Documents, OCR (EasyOCR), Translation (Ollama + MyMemory), Rewrite (8 tones, 4 lengths) |
| 4 | ✅ Done | Video & Audio: Whisper transcription, OpenCV frame extraction, FFmpeg processing, quality checks |
| 5 | ✅ Done | Social Media Integration: Instagram Graph API (OAuth, publishing, scheduling, drafts, history, notifications), fallback for personal accounts, modular provider architecture |

## License

MIT
