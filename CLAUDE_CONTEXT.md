# Context File for Synopsis Generation - Creator AI Assistant (ContentAI)

## Project Information

**Project Title:** Creator AI Assistant (ContentAI)

**Institution:** College of Agricultural Information Technology, Anand Agricultural University, Anand

**Student Details:**
- Name: [YOUR NAME]
- Enrollment No.: [YOUR ENROLLMENT]
- Semester: 7th
- Course Code: PRJT311

**Guide Details:**
- Name: [GUIDE NAME]
- Designation: [DESIGNATION]
- University: [UNIVERSITY]

## Synopsis Contents Structure

| No. | Contents | Page No. |
|-----|----------|----------|
| 1 | Project Title | 3 |
| 2 | Introduction | 3 |
| 3 | Purpose | 3 |
| 4 | Objectives | 3 |
| 5 | Platform/Hardware and Software | 4 |
| 6 | Functionality | 4 |
| 7 | Data Flow Diagram | 5 |
| 8 | E-R Diagram | 6 |
| 9 | Data Dictionary | 7 |

---

## 1. Project Title

**"Creator AI Assistant (ContentAI)"**

---

## 2. Introduction

ContentAI is a full-stack AI-powered social media content assistant web application built with Python, FastAPI, and PostgreSQL. The system enables users to upload various media types — images, videos, audio files, documents, and plain text — and automatically generates optimized social media content including captions, hashtags, keywords, emojis, hooks, CTAs, SEO tags, summaries, viral scoring, and translations in 20+ languages.

### Key Technologies Used:
- **Frontend:** HTML5, CSS3, Bootstrap 5, Vanilla JavaScript, Jinja2 Templating
- **Backend:** Python 3.11+, FastAPI (Async Web Framework), Uvicorn (ASGI Server)
- **Database:** PostgreSQL 14+ (Production), SQLite (Development)
- **ORM:** SQLAlchemy with Alembic migrations
- **Authentication:** JWT tokens + bcrypt password hashing
- **AI Models:**
  - Gemma 3 4B (via Ollama) - Text Generation
  - YOLOv8 (Ultralytics) - Object Detection
  - CLIP (OpenAI) - Image Classification
  - BLIP-2 (HuggingFace) - Image Captioning
  - Whisper (faster-whisper) - Speech-to-Text
  - EasyOCR - Optical Character Recognition
  - PyTorch & TorchVision - Deep Learning Framework
- **Social Media Integration:** Instagram Graph API, Facebook, LinkedIn, Twitter/X, Threads, YouTube

### System Capabilities:
1. Multi-media upload and analysis (images, videos, audio, documents)
2. AI-powered content generation with 9 caption styles
3. Hashtag, keyword, emoji, hook, and CTA generation
4. SEO tag generation and content summaries
5. Viral score prediction (1-100)
6. Content translation to 20+ languages
7. Content rewriting with 8 tones × 4 lengths
8. Direct social media publishing via OAuth 2.0
9. Post scheduling with background scheduler
10. Analytics dashboard and engagement tracking
11. Multi-format content export (TXT, CSV, DOCX, PDF, JSON)

---

## 3. Purpose

The purpose of ContentAI is to:

1. **Centralize Content Creation:** Provide a single platform for content creators to generate, optimize, manage, and publish social media content from one dashboard.

2. **Automate Manual Work:** Reduce manual content creation effort by automating caption generation, hashtag research, SEO optimization, and multi-language translation.

3. **Enable Direct Publishing:** Offer seamless social media integration for direct publishing to Instagram, Facebook, LinkedIn, Twitter, Threads, and YouTube.

4. **Provide Analytics:** Offer analytics and engagement tracking to help creators measure content performance and improve their social media strategy.

5. **Support Multiple Formats:** Support multiple media types (image, video, audio, document, text) so creators can work with any content format they have.

6. **Scale Content Production:** Enable content creators to produce more content in less time through AI-assisted workflows.

7. **Improve Content Quality:** Use AI models to analyze content quality and suggest improvements for better engagement.

---

## 4. Objectives

The main objectives of this project are:

1. **Secure Authentication System:**
   - Implement JWT-based authentication with access and refresh tokens
   - Use bcrypt password hashing with salt rounds
   - Support role-based admin access control

2. **Multi-Media Upload Pipeline:**
   - Support images: JPG, PNG, WEBP, GIF, BMP, HEIC
   - Support videos: MP4, MOV, AVI, WEBM, MKV (max 2 min)
   - Support audio: MP3, WAV, OGG, M4A, AAC
   - Support documents: PDF, DOCX, TXT

3. **AI Model Integration:**
   - YOLOv8 for object detection in images
   - CLIP for image classification
   - BLIP-2 for image captioning
   - Whisper for audio transcription
   - EasyOCR for text extraction from images

4. **Content Generation:**
   - Generate 9 caption styles (default, long, short, funny, professional, travel, business, food, luxury)
   - Generate hashtags, keywords, emojis, hooks, CTAs, SEO tags
   - Generate content summaries and viral scores

5. **Translation and Rewriting:**
   - Translate content to 20+ languages using Ollama LLM with MyMemory API fallback
   - Support content rewriting with 8 tones and 4 length options

6. **Social Media Integration:**
   - Instagram Graph API with OAuth 2.0 for direct publishing
   - Modular provider framework for Facebook, LinkedIn, Twitter/X, Threads, YouTube

7. **Post Management:**
   - Implement post scheduling with background scheduler
   - Support content drafts with full CRUD operations
   - Track posting history with engagement metrics

8. **Analytics and Export:**
   - Build analytics dashboard with engagement metrics
   - Support multi-format content export (TXT, CSV, DOCX, PDF, JSON)

9. **Security and Performance:**
   - Implement rate limiting (60 requests/min per IP)
   - Use in-memory caching for performance
   - Admin panel with user management and system monitoring

---

## 5. Platform/Hardware and Software

### Platform (Development Tools):
- **IDE:** Visual Studio Code / PyCharm
- **Language:** Python 3.11+
- **Framework:** FastAPI

### Frontend Technologies:
- HTML5, CSS3, Bootstrap 5
- Vanilla JavaScript
- Jinja2 Templating Engine

### Backend Technologies:
- Python 3.11+
- FastAPI (Async Web Framework)
- Uvicorn (ASGI Server)
- SQLAlchemy (ORM)
- Alembic (Database Migrations)

### AI Models & Libraries:
| Model/Library | Purpose |
|---------------|---------|
| Gemma 3 4B (Ollama) | Text Generation |
| YOLOv8 (Ultralytics) | Object Detection |
| CLIP (OpenAI) | Image Classification |
| BLIP-2 (HuggingFace) | Image Captioning |
| Whisper (faster-whisper) | Speech-to-Text |
| EasyOCR | Optical Character Recognition |
| PyTorch & TorchVision | Deep Learning Framework |
| Transformers (HuggingFace) | AI Model Pipeline |
| OpenCV | Image/Video Processing |

### Social Media Integration:
- Instagram Graph API (OAuth 2.0)
- Facebook Graph API
- LinkedIn API
- Twitter/X API
- Threads API
- YouTube Data API

### Database:
- PostgreSQL 14+ (Production)
- SQLite (Development)

### Hardware Requirements:
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Processor | Intel i5 / AMD Ryzen 5 | Intel i7 / AMD Ryzen 7 |
| Disk Space | 50 GB | 100 GB |
| GPU | Not required | NVIDIA with CUDA support |

### Software Requirements:
- Windows 10/11, macOS, or Linux
- Python 3.11+
- PostgreSQL 14+
- Ollama (for AI features)
- FFmpeg (for video/audio processing)

---

## 6. Functionality

### Public Features:
- Landing page with project overview and features
- User registration with email and password
- User login with JWT access and refresh tokens
- Health check endpoint for system monitoring

### Authenticated User Features:

#### Dashboard:
- Overview of posts, drafts, scheduled content, and connected accounts

#### Media Upload & Analysis:
- **Images:** JPG, PNG, WEBP, GIF, BMP, HEIC with preview
- **Videos:** MP4, MOV, AVI, WEBM, MKV (max 2 min) with frame extraction
- **Audio:** MP3, WAV, OGG, M4A, AAC with Whisper transcription
- **Documents:** PDF, DOCX, TXT with text extraction

#### AI Content Generation Pipeline:
- Image analysis: YOLOv8 object detection, CLIP classification, BLIP-2 captioning
- Video processing: Frame extraction with OpenCV, quality assessment
- Audio transcription: Whisper speech-to-text conversion
- Document extraction: PDF and DOCX text extraction
- OCR: EasyOCR text extraction from images

#### Content Generation:
- 9 caption styles (default, long, short, funny, professional, travel, business, food, luxury)
- Hashtags, keywords, emojis, hooks, CTAs, SEO tags
- Content summaries and viral scoring (1-100)

#### Content Management:
- Content translation to 20+ languages
- Content rewriting with 8 tones × 4 lengths
- Regenerate individual content fields
- Edit and update generated content
- Content quality checks (image & video)

#### Export:
- Multi-format export: TXT, CSV, DOCX, PDF, JSON

#### Social Media Integration:
- OAuth connection for Instagram, Facebook, LinkedIn, Twitter, Threads, YouTube
- Direct publishing to connected social accounts
- Post scheduling with date/time picker
- Content drafts management (CRUD)
- Posting history with engagement metrics
- In-app notifications

#### Analytics:
- Analytics dashboard with engagement metrics
- Content breakdown and viral score tracking

### Admin Features:
- Admin dashboard with system statistics
- User management: list, ban/unban, delete users
- Role-based access control
- Media type distribution analytics
- Recent posts monitoring

### Security Features:
- JWT-based authentication with access and refresh tokens
- bcrypt password hashing
- OAuth 2.0 for social media connections
- Fernet encryption for stored social media tokens
- Rate limiting: 10 requests/min for login/register
- CORS middleware
- Admin role verification
- Banned user prevention

### Automation Features (Optional):
- n8n workflow automation integration
- Background job scheduling for post publishing
- Webhook-based job dispatching
- Workflow job tracking

---

## 7. Data Flow Diagram

### Context Level DFD (Level 0 DFD):

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│                    ┌─────────────────┐                      │
│                    │                 │                      │
│    User ──────────►│  ContentAI      │──────────► Social    │
│    (Content        │  System         │          Media       │
│     Creator)       │                 │          Platforms   │
│    ◄──────────────│                 │                      │
│                    └─────────────────┘                      │
│                           │                                 │
│                           ▼                                 │
│                    AI Models                                │
│                    (YOLOv8, CLIP, BLIP-2,                   │
│                     Whisper, EasyOCR, Gemma 3)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Steps:

1. **User uploads media/text** → ContentAI System
2. **ContentAI System** → AI Models (Analysis)
3. **AI Models** → Generated Content (captions, hashtags, etc.)
4. **Generated Content** → Social Media Platforms (publishing)
5. **Generated Content** → Export Formats (TXT, CSV, DOCX, PDF, JSON)

---

## 8. Entity-Relationship Diagram

### Entities and Relationships:

```
┌──────────────┐
│    Users     │
│──────────────│
│ id (PK)      │──────┐
│ email        │      │
│ password_hash│      │
│ is_admin     │      │
│ is_banned    │      │
│ created_at   │      │
└──────────────┘      │
        │             │
        │ 1:N         │
        ▼             │
┌──────────────┐      │
│    Posts     │◄─────┘
│──────────────│
│ id (PK)      │──────┐
│ user_id (FK) │      │
│ media_type   │      │
│ media_path   │      │
│ original_text│      │
│ created_at   │      │
└──────────────┘      │
        │             │
        │ 1:1         │
        ▼             │
┌──────────────────┐  │
│GeneratedContent  │◄─┘
│──────────────────│
│ id (PK)          │
│ post_id (FK)     │
│ caption          │
│ hashtags         │
│ keywords         │
│ emojis           │
│ cta              │
│ hook             │
│ seo_tags         │
│ summary          │
│ viral_score      │
│ created_at       │
└──────────────────┘

┌──────────────┐
│SocialAccounts│
│──────────────│
│ id (PK)      │──────┐
│ user_id (FK) │      │
│ platform     │      │
│ username     │      │
│ access_token │      │
│ is_active    │      │
└──────────────┘      │
        │             │
        │ 1:N         │
        ▼             │
┌──────────────────┐  │
│ ScheduledPosts   │◄─┘
│──────────────────│
│ id (PK)          │
│ user_id (FK)     │
│ account_id (FK)  │
│ caption          │
│ scheduled_at     │
│ status           │
└──────────────────┘

┌──────────────────┐
│ PostingHistory   │
│──────────────────│
│ id (PK)          │
│ user_id (FK)     │
│ account_id (FK)  │
│ platform_post_id │
│ likes            │
│ comments         │
│ shares           │
│ impressions      │
│ reach            │
└──────────────────┘

┌──────────────────┐
│   Notifications  │
│──────────────────│
│ id (PK)          │
│ user_id (FK)     │
│ title            │
│ message          │
│ notification_type│
│ is_read          │
└──────────────────┘

┌──────────────────┐
│  WorkflowJobs    │
│──────────────────│
│ id (PK)          │
│ job_id (UK)      │
│ user_id (FK)     │
│ workflow_type    │
│ status           │
│ payload          │
│ result           │
└──────────────────┘
```

### Relationships Summary:
- Users (1) ---- (N) Posts
- Users (1) ---- (N) SocialAccounts
- Users (1) ---- (N) Drafts
- Users (1) ---- (N) ScheduledPosts
- Users (1) ---- (N) PostingHistory
- Users (1) ---- (N) Notifications
- Users (1) ---- (N) WorkflowJobs
- Posts (1) ---- (1) GeneratedContent
- SocialAccounts (1) ---- (N) ScheduledPosts
- SocialAccounts (1) ---- (N) PostingHistory

---

## 9. Data Dictionary

### 1. Users Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | email | VARCHAR(255) | NOT NULL, UNIQUE, INDEX |
| 3 | password_hash | VARCHAR(255) | NOT NULL |
| 4 | is_admin | BOOLEAN | DEFAULT = FALSE |
| 5 | is_banned | BOOLEAN | DEFAULT = FALSE |
| 6 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |

### 2. Posts Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL |
| 3 | media_type | VARCHAR(50) | NOT NULL (image/video/audio/document/text) |
| 4 | media_path | VARCHAR(500) | NULL |
| 5 | original_text | TEXT | NULL |
| 6 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |

### 3. GeneratedContent Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | post_id | INT | FOREIGN KEY → Posts(id), NOT NULL |
| 3 | caption | TEXT | NULL |
| 4 | long_caption | TEXT | NULL |
| 5 | short_caption | TEXT | NULL |
| 6 | funny_caption | TEXT | NULL |
| 7 | professional_caption | TEXT | NULL |
| 8 | travel_caption | TEXT | NULL |
| 9 | business_caption | TEXT | NULL |
| 10 | food_caption | TEXT | NULL |
| 11 | luxury_caption | TEXT | NULL |
| 12 | carousel_text | TEXT | NULL |
| 13 | thumbnail_text | VARCHAR(200) | NULL |
| 14 | alt_text | TEXT | NULL |
| 15 | hashtags | TEXT | NULL |
| 16 | keywords | TEXT | NULL |
| 17 | emojis | TEXT | NULL |
| 18 | cta | TEXT | NULL |
| 19 | hook | TEXT | NULL |
| 20 | reel_title | TEXT | NULL |
| 21 | seo_tags | TEXT | NULL |
| 22 | summary | TEXT | NULL |
| 23 | translation | TEXT | NULL |
| 24 | viral_score | INT | NULL |
| 25 | viral_score_reason | TEXT | NULL |
| 26 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |

### 4. SocialAccounts Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL, INDEX |
| 3 | platform | VARCHAR(50) | NOT NULL (instagram/facebook/linkedin/twitter/threads/youtube) |
| 4 | account_type | VARCHAR(50) | DEFAULT = 'personal' (personal/business/creator) |
| 5 | platform_user_id | VARCHAR(255) | NOT NULL |
| 6 | username | VARCHAR(255) | NOT NULL |
| 7 | display_name | VARCHAR(255) | DEFAULT = '' |
| 8 | profile_picture_url | VARCHAR(500) | DEFAULT = '' |
| 9 | followers_count | INT | DEFAULT = 0 |
| 10 | access_token | TEXT | NULL (encrypted with Fernet) |
| 11 | refresh_token | TEXT | NULL (encrypted with Fernet) |
| 12 | token_expires_at | DATETIME(timezone) | NULL |
| 13 | is_active | BOOLEAN | DEFAULT = TRUE, INDEX |
| 14 | raw_data | JSON | NULL |
| 15 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |
| 16 | updated_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP, ON UPDATE |

### 5. Drafts Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL, INDEX |
| 3 | post_id | INT | FOREIGN KEY → Posts(id), NULL |
| 4 | title | VARCHAR(255) | DEFAULT = '' |
| 5 | caption | TEXT | DEFAULT = '' |
| 6 | long_caption | TEXT | DEFAULT = '' |
| 7 | short_caption | TEXT | DEFAULT = '' |
| 8 | hashtags | TEXT | DEFAULT = '' |
| 9 | emojis | TEXT | DEFAULT = '' |
| 10 | media_path | VARCHAR(500) | DEFAULT = '' |
| 11 | media_type | VARCHAR(50) | DEFAULT = 'image' |
| 12 | target_platforms | JSON | DEFAULT = [] |
| 13 | notes | TEXT | DEFAULT = '' |
| 14 | status | VARCHAR(50) | DEFAULT = 'draft' (draft/ready) |
| 15 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |
| 16 | updated_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP, ON UPDATE |

### 6. ScheduledPosts Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL, INDEX |
| 3 | account_id | INT | FOREIGN KEY → SocialAccounts(id), NOT NULL, INDEX |
| 4 | draft_id | INT | FOREIGN KEY → Drafts(id), NULL |
| 5 | caption | TEXT | DEFAULT = '' |
| 6 | hashtags | TEXT | DEFAULT = '' |
| 7 | media_path | VARCHAR(500) | DEFAULT = '' |
| 8 | media_type | VARCHAR(50) | DEFAULT = 'image' |
| 9 | scheduled_at | DATETIME(timezone) | NOT NULL, INDEX |
| 10 | status | VARCHAR(50) | DEFAULT = 'scheduled', INDEX (scheduled/publishing/published/failed/cancelled) |
| 11 | platform_post_id | VARCHAR(255) | NULL |
| 12 | platform_url | VARCHAR(500) | NULL |
| 13 | error_message | TEXT | NULL |
| 14 | is_recurring | BOOLEAN | DEFAULT = FALSE |
| 15 | recur_frequency | VARCHAR(50) | NULL (daily/weekly/monthly) |
| 16 | recur_interval | INT | DEFAULT = 1 |
| 17 | recur_end_date | DATETIME(timezone) | NULL |
| 18 | recur_count | INT | NULL |
| 19 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |

### 7. PostingHistory Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL, INDEX |
| 3 | account_id | INT | FOREIGN KEY → SocialAccounts(id), NOT NULL, INDEX |
| 4 | platform_post_id | VARCHAR(255) | NOT NULL |
| 5 | platform_url | VARCHAR(500) | DEFAULT = '' |
| 6 | caption | TEXT | DEFAULT = '' |
| 7 | hashtags | TEXT | DEFAULT = '' |
| 8 | media_path | VARCHAR(500) | DEFAULT = '' |
| 9 | media_type | VARCHAR(50) | DEFAULT = 'image' |
| 10 | posted_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |
| 11 | likes | INT | DEFAULT = 0 |
| 12 | comments | INT | DEFAULT = 0 |
| 13 | shares | INT | DEFAULT = 0 |
| 14 | impressions | INT | DEFAULT = 0 |
| 15 | reach | INT | DEFAULT = 0 |
| 16 | last_metrics_at | DATETIME(timezone) | NULL |
| 17 | status | VARCHAR(50) | DEFAULT = 'published' (published/failed/deleted) |
| 18 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |

### 8. Notifications Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL, INDEX |
| 3 | title | VARCHAR(255) | NOT NULL |
| 4 | message | TEXT | NOT NULL |
| 5 | notification_type | VARCHAR(50) | DEFAULT = 'info' (info/success/warning/error) |
| 6 | is_read | BOOLEAN | DEFAULT = FALSE, INDEX |
| 7 | link | VARCHAR(500) | NULL |
| 8 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |

### 9. WorkflowJobs Table

| S.no | Attribute | Data Type | Constraint |
|------|-----------|-----------|------------|
| 1 | id | INT | PRIMARY KEY, INDEX |
| 2 | job_id | VARCHAR(64) | UNIQUE, INDEX, NOT NULL |
| 3 | user_id | INT | FOREIGN KEY → Users(id), NOT NULL, INDEX |
| 4 | content_id | INT | FOREIGN KEY → Posts(id), NULL, INDEX |
| 5 | scheduled_post_id | INT | FOREIGN KEY → ScheduledPosts(id), NULL, INDEX |
| 6 | workflow_type | VARCHAR(50) | NOT NULL (content_generation/publish/schedule) |
| 7 | status | VARCHAR(50) | DEFAULT = 'pending', INDEX (pending/dispatched/processing/completed/failed/cancelled) |
| 8 | payload | JSON | NULL |
| 9 | result | JSON | NULL |
| 10 | error_message | TEXT | NULL |
| 11 | created_at | DATETIME(timezone) | DEFAULT = CURRENT_UTC_TIMESTAMP |
| 12 | started_at | DATETIME(timezone) | NULL |
| 13 | completed_at | DATETIME(timezone) | NULL |

---

## API Endpoints Reference

### Auth Endpoints:
- POST /api/auth/register - User registration
- POST /api/auth/login - User login (returns JWT tokens)
- POST /api/auth/refresh - Refresh access token
- GET /api/auth/me - Get current user info

### Posts Endpoints:
- POST /api/posts/upload - Upload media and generate content
- POST /api/posts/{id}/regenerate - Regenerate a specific field
- POST /api/posts/{id}/update - Update generated content
- POST /api/posts/{id}/translate - Translate content to target language
- POST /api/posts/rewrite - Rewrite text with tone and length
- GET /api/posts/history - Get post history with pagination
- GET /api/posts/{id}/export/{fmt} - Export post (txt/csv/docx/pdf/json)
- GET /api/posts/export-all/csv - Export all posts as CSV
- GET /api/posts/{id}/quality - Get quality report for media

### Social Endpoints:
- GET /api/social/platforms - List supported platforms
- GET /api/social/connect/{platform} - Start OAuth connection
- GET /api/social/{platform}/callback - OAuth callback handler
- GET /api/social/accounts - List connected accounts
- DELETE /api/social/accounts/{id} - Disconnect account
- POST /api/social/accounts/{id}/refresh-token - Refresh OAuth token
- GET /api/social/accounts/{id}/status - Get account status
- POST /api/social/drafts - Create draft
- GET /api/social/drafts - List drafts
- GET /api/social/drafts/{id} - Get draft details
- PUT /api/social/drafts/{id} - Update draft
- DELETE /api/social/drafts/{id} - Delete draft
- POST /api/social/schedule - Schedule a post
- GET /api/social/schedule - List scheduled posts
- DELETE /api/social/schedule/{id} - Cancel scheduled post
- POST /api/social/schedule/{id}/publish-now - Publish immediately
- POST /api/social/post-now - Publish content now
- GET /api/social/history - List posting history
- GET /api/social/history/{id}/metrics - Fetch engagement metrics
- GET /api/social/notifications - List notifications
- POST /api/social/notifications/read-all - Mark all as read
- GET /api/social/preview/{post_id} - Get post preview data
- POST /api/social/preview/drafts - Save preview as draft
- PUT /api/social/preview/drafts/{id} - Update preview draft

### Admin Endpoints:
- GET /api/admin/users - List all users
- GET /api/admin/stats - Get system statistics
- POST /api/admin/users/{id}/ban - Ban user
- POST /api/admin/users/{id}/unban - Unban user
- DELETE /api/admin/users/{id} - Delete user
- POST /api/admin/make-admin/{id} - Make user admin

### Analytics Endpoints:
- GET /api/analytics/overview - Get analytics overview
- GET /api/analytics/engagement - Get engagement analytics
- GET /api/analytics/content-breakdown - Get content breakdown

### Workflow Endpoints:
- POST /api/workflows/trigger - Trigger n8n workflow
- GET /api/workflows/{job_id}/status - Get job status
- POST /api/workflows/{job_id}/callback - Receive n8n callback

### Page Endpoints:
- GET / - Landing page
- GET /login - Login page
- GET /register - Registration page
- GET /dashboard - Dashboard page
- GET /admin - Admin panel
- GET /preview/{post_id} - Post preview page
- GET /connect - Social accounts connection page

---

## Instructions for Claude

When generating the synopsis content:

1. **Maintain Academic Tone:** Use formal, academic language appropriate for a university project synopsis.

2. **Follow the Structure:** Adhere strictly to the 9-section structure provided above.

3. **Be Detailed but Concise:** Provide enough detail to explain each section without being overly verbose.

4. **Use Technical Terms:** Include technical terminology related to AI, web development, and database systems.

5. **Cite Technologies:** Mention specific technologies, libraries, and frameworks used in the project.

6. **Explain Relationships:** Clearly explain how different components of the system interact.

7. **Include Diagrams:** Describe the DFD and ER diagrams in text format (or suggest using diagramming tools).

8. **Data Dictionary Format:** Present the data dictionary in tabular format with clear constraints.

9. **Page Numbers:** Maintain the page number references as specified in the contents.

10. **Formatting:** Use proper headings, subheadings, bullet points, and tables for clarity.

---

## Additional Notes

- The project uses a modular architecture with clear separation of concerns
- AI models are integrated via Ollama for local deployment
- Social media integration follows OAuth 2.0 standards
- The system supports both personal and business/creator accounts
- Background schedulers handle post publishing automation
- Rate limiting and encryption ensure security compliance
