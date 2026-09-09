# CourseCompass — REST API Reference

The CourseCompass backend provides a high-performance RESTful API built with **FastAPI**.

- **Default Base URL**: `http://localhost:8000`
- **Interactive Documentation (Swagger UI)**: `http://localhost:8000/docs`
- **Alternative Documentation (ReDoc)**: `http://localhost:8000/redoc`
- **Authentication Scheme**: HTTP Bearer Token (`Authorization: Bearer <access_token>`) using JSON Web Tokens (JWT).

---

## 1. Health & Service Status

### `GET /api/status`
Returns the operational health and version of the assistant service.

#### Request
```bash
curl -X GET "http://localhost:8000/api/status"
```

#### Response (`200 OK`)
```json
{
  "status": "ok",
  "service": "CourseCompass Academic & Benefits Assistant",
  "version": "0.3.0"
}
```

---

## 2. Authentication & Student Profile

### `POST /api/auth/register`
Registers a new student profile. Registration number must be unique.

#### Request Body (`application/json`)
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `registration_number` | `string` | **Yes** | Student ID / registration number (e.g., `12200001`) |
| `password` | `string` | **Yes** | Plain text password (hashed via `bcrypt`) |
| `cgpa` | `number` | No | Current CGPA (e.g., `7.85`) |
| `current_term` | `string` | No | Current semester/term (e.g., `Term 5`) |
| `program` | `string` | No | Academic program (e.g., `B.Tech CSE`) |

#### Example Request
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "registration_number": "12200001",
    "password": "SecurePassword123!",
    "cgpa": 7.85,
    "current_term": "Term 5",
    "program": "B.Tech Computer Science and Engineering"
  }'
```

#### Response (`200 OK`)
```json
{
  "id": 1,
  "registration_number": "12200001",
  "cgpa": 7.85,
  "current_term": "Term 5",
  "program": "B.Tech Computer Science and Engineering"
}
```

#### Errors
- `400 Bad Request`: `{"detail": "Registration number already registered"}`

---

### `POST /api/auth/login`
Authenticates a student and returns a signed JWT access token.

#### Request Body (`application/json`)
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `registration_number` | `string` | **Yes** | Registered student registration number |
| `password` | `string` | **Yes** | Student account password |

#### Example Request
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "registration_number": "12200001",
    "password": "SecurePassword123!"
  }'
```

#### Response (`200 OK`)
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Errors
- `401 Unauthorized`: `{"detail": "Incorrect registration number or password"}`

---

### `GET /api/auth/me`
Fetches the profile of the currently authenticated student.

#### Headers
- `Authorization: Bearer <access_token>`

#### Example Request
```bash
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer <your_jwt_token>"
```

#### Response (`200 OK`)
```json
{
  "id": 1,
  "registration_number": "12200001",
  "cgpa": 7.85,
  "current_term": "Term 5",
  "program": "B.Tech Computer Science and Engineering"
}
```

---

## 3. Conversational AI & Academic Advising

### `POST /api/chat`
Sends a question to the CourseCompass agent. Supports both **Guest Mode** (anonymous) and **Authenticated Mode** (automatically attaches student academic profile, creates/tracks persistent chat sessions).

#### Request Body (`application/json`)
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `messages` | `array` | **Yes** | List of message objects: `[{"role": "user", "content": "..."}]` |
| `session_id` | `string` | No | UUID of an existing session. If omitted for an authenticated user, a new session is generated. |

#### Headers
- `Authorization: Bearer <token>` *(Optional)*: When provided, the agent personalizes advice using the student's CGPA, current term, and program.

#### Example Request (Guest Query)
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is the continuous assessment weightage for CSE205?"}
    ]
  }'
```

#### Example Request (Authenticated Session Query)
```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "messages": [
      {"role": "user", "content": "I did a 3-month startup internship at 12,000 INR/month. What benefits am I eligible for?"}
    ],
    "session_id": "b3e0c7a5-5154-46c9-b7e1-88989bbd8f8a"
  }'
```

#### Response (`200 OK`)
```json
{
  "response": "Congratulations on completing your internship! Based on the LPU EduRevolution policy for **Internship beyond Curriculum**:\n\n- **Stipend Category**: ₹10,000 – ₹20,000 / month\n- **Duration**: 3 Months\n- **Organization**: Local / Startup\n\n### Eligible Academic Benefits:\n- **Course Benefit**: **Full Marks in All CA + MTE** in one mapped course.\n\n### Requirements & Steps:\n1. Ensure your CGPA is $\\ge 6.0$.\n2. Navigate to **UMS >>> Placement Services >>> Special Academic Benefit**.\n3. Submit your Offer Letter, Completion Certificate, and bank statements/stipend slips.",
  "sources": [
    "Benefits/criteria_row: Academic Benefits.pdf",
    "Benefits/policy_overview: Academic Benefits.pdf"
  ],
  "session_id": "b3e0c7a5-5154-46c9-b7e1-88989bbd8f8a"
}
```

---

## 4. Chat Session Management (Authenticated)

### `GET /api/chat/sessions`
Retrieves a list of all historical chat sessions for the logged-in student, ordered from newest to oldest.

#### Headers
- `Authorization: Bearer <access_token>`

#### Example Request
```bash
curl -X GET "http://localhost:8000/api/chat/sessions" \
  -H "Authorization: Bearer <your_jwt_token>"
```

#### Response (`200 OK`)
```json
[
  {
    "id": "b3e0c7a5-5154-46c9-b7e1-88989bbd8f8a",
    "title": "3-month startup internship bene...",
    "created_at": "2026-09-08T10:30:00"
  },
  {
    "id": "993c12f0-df6a-493e-b8cc-0a1262d1193b",
    "title": "Term 5 Core Electives Advic...",
    "created_at": "2026-09-07T16:15:00"
  }
]
```

---

### `GET /api/chat/sessions/{session_id}`
Fetches the full message history for a specific conversation session.

#### Headers
- `Authorization: Bearer <access_token>`

#### Example Request
```bash
curl -X GET "http://localhost:8000/api/chat/sessions/b3e0c7a5-5154-46c9-b7e1-88989bbd8f8a" \
  -H "Authorization: Bearer <your_jwt_token>"
```

#### Response (`200 OK`)
```json
{
  "id": "b3e0c7a5-5154-46c9-b7e1-88989bbd8f8a",
  "title": "3-month startup internship bene...",
  "messages": [
    {
      "role": "user",
      "content": "I did a 3-month startup internship at 12,000 INR/month. What benefits am I eligible for?"
    },
    {
      "role": "assistant",
      "content": "Congratulations on completing your internship! Based on the LPU EduRevolution policy..."
    }
  ]
}
```

---

### `DELETE /api/chat/sessions/{session_id}`
Deletes an entire chat session and all messages contained within it.

#### Headers
- `Authorization: Bearer <access_token>`

#### Example Request
```bash
curl -X DELETE "http://localhost:8000/api/chat/sessions/b3e0c7a5-5154-46c9-b7e1-88989bbd8f8a" \
  -H "Authorization: Bearer <your_jwt_token>"
```

#### Response (`200 OK`)
```json
{
  "status": "success",
  "message": "Session deleted successfully"
}
```

---

## 5. Standard HTTP Status Codes

| Code | Meaning | Typical Occurrence |
| :--- | :--- | :--- |
| `200 OK` | Success | Request succeeded and returned requested data. |
| `400 Bad Request` | Client Error | Registration number already exists or invalid data passed. |
| `401 Unauthorized` | Auth Error | Missing, expired, or invalid JWT token; invalid password. |
| `404 Not Found` | Resource Missing| Requested chat session ID not found or belongs to another user. |
| `422 Unprocessable Entity` | Schema Error | Request body does not conform to Pydantic schema validation. |
| `500 Internal Server Error` | Server Failure | Database connection failure or unhandled LLM invocation error. |
