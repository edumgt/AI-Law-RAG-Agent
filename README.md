# law-rag-agent (Ollama + RAG + Legal 상담 에이전트)

> ⚠️ **면책 고지(중요)**  
> 이 프로젝트는 **법률 자문이 아닌 정보 제공/학습 목적**의 RAG 데모입니다.  
> 실제 사건 적용 전에는 **관할/시점(최신성)/사실관계**를 확인하고, 필요 시 **변호사 자문**을 받으세요.

## 구성 요약
- **LLM/Embeddings**: Ollama (로컬)
- **Backend**: Node.js + Express (CommonJS)
- **Auth/Session**: `express-session` + SQLite (세션 쿠키 기반)
- **Client ID**: 회원가입 시 유저별 `client_id` 부여 → 로그인 시 세션에 유지
- **RAG**: 문서 chunking → Ollama embeddings → SQLite에 저장 → cosine similarity 검색
- **Frontend**: Tailwind CDN + Offcanvas(좌측 슬라이딩) + 로그인/회원가입 + Chat UI
- **데모 문서**: `data/raw/` (법령/판례 "예시" 문서 다수 포함)

---

## 0) 요구사항
- Docker (Ollama 컨테이너 구동)
- Node.js 18+ (권장 20+)

---

## 1) 빠른 시작

### 1-1. Ollama 실행 (Docker)
```bash
docker compose up -d ollama
```

### 1-2. 모델 준비 (호스트에서 1회)
Ollama 컨테이너가 떠 있으면 아래로 pull 가능합니다.

```bash
# LLM (답변용)
docker exec -it ollama ollama pull llama3.1

# Embedding (검색용)
docker exec -it ollama ollama pull nomic-embed-text
```

> 기본값:  
> - LLM_MODEL = `llama3.1`  
> - EMBED_MODEL = `nomic-embed-text`

### 1-3. API 서버 실행
```bash
cp .env.example .env
npm install
npm run dev
```

- 웹: http://localhost:8000
- API health: http://localhost:8000/api/health

---

## 2) 사용 흐름
1) 브라우저 접속 → 회원가입 → 로그인  
2) (앱 화면) **Ingest** 메뉴에서 `데모 문서 인덱싱` 실행  
3) **Chat** 메뉴에서 질문 → 근거 인용된 답변 확인  
4) Settings 메뉴에서 **Client ID / 세션 정보** 확인

---

## 3) RAG 인덱싱(서버에서 실행)

### 방법 A) UI에서 실행
- 좌측 메뉴 Ingest → "데모 문서 인덱싱" 버튼 클릭

### 방법 B) CLI로 실행
```bash
npm run ingest
```

---

## 4) 환경변수 (.env)
`.env.example` 참고

- `OLLAMA_BASE_URL` : 기본 `http://127.0.0.1:11434`
- `LLM_MODEL` : 답변 모델
- `EMBED_MODEL` : 임베딩 모델
- `SESSION_SECRET` : 세션 암호화 키
- `SQLITE_PATH` : `./data/app.db`

---

## 5) 문서 추가 방법
- `data/raw/law/` : 법령 발췌/요약/체크리스트
- `data/raw/cases/` : 판례 요약(사실관계/쟁점/판단/시사점)

실무에서는 사내 검증된 문서를 넣고, 문서의 **기준일/버전/관할** 메타데이터를 반드시 관리하세요.

---

## 6) API 요약
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/me`
- `POST /api/ingest/demo` (로그인 필요)
- `POST /api/chat` (로그인 필요)
- `GET /api/library/search?q=...` (로그인 필요)

---

## 7) 보안/가드레일
- 불법행위 조장/증거조작/위법 회피/타인 권리 침해 등 요청은 거절합니다.
- 최신성/관할 불확실 시 추가 질문을 우선합니다.
- 답변에는 항상 **근거 인용** 블록이 포함됩니다.

---

## 8) 개발 팁
- 임베딩/검색은 데모용으로 SQLite + 메모리 cosine 계산을 사용합니다.
  - 문서가 매우 많아지면 벡터DB(Chroma/Qdrant 등)로 교체하세요.
- Tailwind는 CDN 방식이라 빌드 없이 즉시 동작합니다.

---

## 라이선스
MIT

---

## 문서 버전업(충돌 방지) 설계 (최종)
이 레포는 실무에서 자주 발생하는 **문서 버전 충돌**을 피하기 위해 아래 원칙으로 동작합니다.

### 1) `data/manifest.json` 기반 문서 관리
- 문서는 `doc_id` + `version` + `effective_date` + `jurisdiction` 메타를 가집니다.
- 같은 `doc_id`를 가진 v1, v2… 문서가 공존할 수 있습니다.

### 2) 인덱싱은 **업서트(upsert)** 방식
- 동일 문서/버전(`doc_id`,`version`)을 다시 인덱싱하면:
  - 기존 해당 버전 chunk를 삭제 후 재삽입 → **중복/충돌 없음**

### 3) 검색은 기본적으로 **최신 버전 우선**
- 기본값: `DOC_VERSION_STRATEGY=latest`
- 필요 시 `DOC_VERSION_STRATEGY=all`로 바꾸면 모든 버전을 함께 검색합니다.

### 4) DB 마이그레이션
- `src/services/db.js`가 구동 시점에 필요한 컬럼을 **idempotent**하게 추가합니다.
- 그래서 기존 DB(`data/app.db`)가 있어도 버전업 후 바로 실행 가능합니다.



---

## RBAC(문서 접근권한) - 최종
- 각 문서는 `data/manifest.json`에서 `allowed_roles`로 접근 권한을 정의합니다.
- 로그인 유저의 role이 허용 목록에 없으면 해당 문서 chunk는 **검색/인용 대상에서 제외**됩니다.

### Admin 계정 만들기
`.env`에서 `ADMIN_EMAILS`에 이메일을 넣고 그 이메일로 회원가입하면 자동으로 admin role이 부여됩니다.
예:
```
ADMIN_EMAILS=admin@example.com
```

---

## 감사로그(Audit) - 최종
- 다음 이벤트들이 `audit_events` 테이블에 기록됩니다:
  - `chat_request`, `retrieve`, `chat_response`, `chat_blocked`, `ingest_demo`
- Admin은 API로 최근 로그를 확인할 수 있습니다:
  - `GET /api/audit/recent?limit=50` (admin only)

---

## 법령/판례 메타 파싱(데모)
- 법령(law) 문서: `제 n 조` 패턴을 간단 추출하여 docs.meta에 저장
- 판례(case) 문서: `사건번호`, `선고일` 패턴을 (있으면) 추출하여 meta에 저장

> 실무에선 정규식/전용 파서를 강화하고, doc 구조(조/항/호, 판결 요지 등)를 표준화하세요.


---

## 수집기(Collector) — 법령/판례 RAG 데이터 수집(공식 API 우선)

이 레포는 **크롤링(스크래핑)** 보다 안정적인 **공식 Open API 기반 수집기**를 먼저 제공합니다.
(필요 시 HTML/PDF 스크래핑 수집기는 별도 provider로 추가 가능합니다.)

### 0) 사전 준비
- 발급받은 키를 `.env`에 설정:
  - `LAWGO_API_KEY=...`
- 응답이 JSON이 아닌 XML로 내려오면:
  - `LAWGO_*_ENDPOINT` 또는 `format=json` 옵션을 API 스펙에 맞게 조정하거나
  - XML 파서를 provider에 추가하세요.

### 1) 법령/판례 수집
```bash
npm run collect:law -- --pages 1 --perPage 20 --concurrency 3
npm run collect:cases -- --pages 1 --perPage 20 --concurrency 3
npm run collect:sync-manifest
```

수집 결과:
- `data/collected/index.jsonl` : 수집 인덱스(append-only)
- `data/collected/lawgo/**` : 정규화 JSON/Markdown 저장

### 2) 수집한 데이터 인덱싱(RAG 반영)
```bash
npm run ingest:collected
```

### 3) 버전 충돌 방지(업서트)
- `scripts/update_manifest_from_collected.js`는 `doc_id + effective_date`를 기준으로 버전을 관리합니다.
- 같은 `effective_date`는 같은 version으로 idempotent하게 유지됩니다.
- 다른 `effective_date`가 들어오면 version을 +1로 증가시켜 **문서 버전 충돌을 방지**합니다.

### 4) 안전/준수
- 공식 API가 없는 자료를 스크래핑할 경우:
  - robots.txt/약관/요청 제한 준수
  - 과도한 트래픽 금지(동시성·rate limit 적용)
  - 저작권(전문 제공) 이슈 검토
