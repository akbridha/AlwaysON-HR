# AlwaysON-HR — Asisten Kebijakan HR dan Manajemen Cuti Berbasis AI Agent

> **AI Agent enterprise semi-otonom**   (*guarded agentic workflow*) untuk menjawab pertanyaan kebijakan operasional HR, pengecekan saldo cuti pribadi, serta pengajuan cuti pegawai dengan arsitektur *Human-in-the-Loop* dan keamanan *Zero-Trust*.

---

## 1. Ringkasan Eksekutif & Skenario Proyek

**Nusantara Digital** adalah perusahaan fiktif yang membutuhkan asisten HR cerdas (*AlwaysON-HR*) untuk melayani ribuan karyawan secara 24/7. Selama ini, tim HR kewalahan menjawab pertanyaan kebijakan berulang, mengecek saldo cuti manual, dan memverifikasi prasyarat pengajuan cuti.

Sistem ini dibangun dengan pendekatan **Enterprise Generative AI & Agentic System** yang mengutamakan:
1. **Grounded Retrieval (RAG)**: Setiap klaim kebijakan HR wajib menyertakan sitasi resmi (`[DOCUMENT-ID]`) dari dokumen Markdown kebijakan yang benar-benar relevan dan ditemukan pada sesi tersebut.
2. **Keamanan & Isolasi Identitas (*Zero-Trust Identity*)**: Identitas pegawai (`employee_id`) diisolasi murni dari verifikasi Bearer Token di sisi backend. Model atau input percakapan pengguna tidak memiliki otoritas menentukan identitas diri maupun mengakses data pengguna lain.
3. **Prinsip *Human-in-the-Loop* (Persetujuan Terkendali)**: Agent AI **TIDAK PERNAH** memiliki wewenang menyetujui (*approve*) permohonan cuti secara sepihak. Agent hanya menyusun *Action Proposal* cuti (`requires_confirmation: true`), dan setelah dikonfirmasi pengguna melalui *idempotency key*, statusnya tetaplah `pending_manager_review` (persetujuan mutlak berada di tangan manajer/atasan).
4. **Redaksi & Privasi PII Medis**: Informasi kesehatan sensitif (misal: diagnosis medis atau PII) otomatis diredaksi oleh sistem sebelum jawaban dikirim ke pengguna atau disimpan ke trace telemetry.
5. **Resiliensi & Graceful Fallback**: Sistem tetap dapat beroperasi dalam mode terdegradasi secara aman saat Redis atau komponen eksternal mengalami kendala (*safe degradation*).

---

## 2. Panduan Menjalankan Sistem

### A. Menjalankan via Docker Compose (Standar Pengiriman / Evaluasi Resmi)

Pengujian dan penilaian akhir dilakukan di lingkungan Docker murni tanpa instalasi Python pada host grader.

1. **Persiapkan Environment**:
   Salin file konfigurasi environment dan sesuaikan kredensial model OpenAI:
   ```powershell
   Copy-Item .env.example .env
   # Di Linux/macOS: cp .env.example .env
   ```
   *Pastikan nilai `OPENAI_API_KEY`, `AGENT_MODEL`, dan `EMBEDDING_MODEL` sudah terisi.*

2. **Build dan Jalankan Service Penunjang**:
   ```powershell
   docker compose -p p2m2_demo build api streamlit
   docker compose -p p2m2_demo up -d postgres redis
   ```

3. **Inisialisasi Database & Seeding Kebijakan (Setup Lab)**:
   ```powershell
   docker compose -p p2m2_demo run --rm api python -m src.setup_lab
   ```

4. **Jalankan API dan Frontend Streamlit**:
   ```powershell
   docker compose -p p2m2_demo up -d api streamlit
   ```

5. **Akses Layanan**:
   - **Streamlit UI**: [http://localhost:8501](http://localhost:8501)
   - **FastAPI Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Healthcheck**: [http://localhost:8000/healthz](http://localhost:8000/healthz)
   - **Readiness Check**: [http://localhost:8000/readyz](http://localhost:8000/readyz)

---

### B. Menjalankan untuk Pengembangan Lokal (Local Development)

Jika ingin mengembangkan atau men-debug kode secara langsung pada host Python lokal:

1. **Buat dan Aktifkan Virtual Environment**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   # Di Linux/macOS: source .venv/bin/activate
   ```

2. **Install Dependensi**:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. **Jalankan Database & Redis di Background**:
   ```powershell
   docker compose up -d postgres redis
   ```

4. **Inisialisasi Skema & Data**:
   ```powershell
   python -m src.setup_lab --reset
   ```

5. **Jalankan Server Backend (Terminal 1)**:
   ```powershell
   python -m uvicorn src.api:create_app --factory --reload --port 8000
   ```

6. **Jalankan Frontend Streamlit (Terminal 2)**:
   ```powershell
   python -m streamlit run app.py
   ```

---

## 3. Hal yang perlu diperhatikan ketika clone

Troubleshooting setelah clone GitHub menunjukkan bahwa beberapa kondisi dapat tampak sehat meskipun aliran aplikasi belum siap sepenuhnya. Gunakan urutan pemeriksaan berikut:

### 3.1. Konfigurasi environment harus lengkap

Jangan menganggap `.env.example` langsung cukup untuk mode live. Masalah autentikasi atau retrieval dapat berasal dari variabel yang kosong. Nilai minimum yang perlu diperiksa adalah:

```env
MODEL_MODE=live
OPENAI_API_KEY=<key-yang-valid>
OPENAI_BASE_URL=<base-url-provider>
AGENT_MODEL=<nama-model-chat>
EMBEDDING_MODEL=<nama-model-embedding>
EMBEDDING_DIMENSIONS=1536
DATABASE_URL=postgresql://hr_app:hr_app@postgres:5432/hr_assistant
REDIS_URL=redis://redis:6379/0
```

Dalam Docker Compose, nama host `postgres`, `redis`, dan `api` adalah alamat antar-container. Gunakan `localhost` hanya untuk koneksi dari host, bukan dari service API.

Periksa konfigurasi yang terbaca container:

```powershell
docker compose exec api env | findstr /I "MODEL_MODE DATABASE_URL AGENT_MODEL EMBEDDING_MODEL EMBEDDING_DIMENSIONS OPENAI_BASE_URL"

docker compose exec api python -c "from src.config import get_settings; s=get_settings(); print({'model_mode': s.model_mode, 'live_model_ready': s.live_model_ready, 'embedding_model': s.embedding_model, 'embedding_dimensions': s.embedding_dimensions})"
```

`live_model_ready` harus bernilai `True` agar seeding membuat embedding kebijakan.

### 3.2. `/healthz` dan `/readyz` memiliki arti berbeda

- `/healthz` hanya memastikan proses API masih hidup.
- `/readyz` pada implementasi saat ini memeriksa database melalui `repository.health()`.
- Keduanya tidak otomatis membuktikan bahwa data pegawai, chunk kebijakan, atau embedding sudah tersedia.

Verifikasi harus dilakukan terpisah untuk tabel data, data identity, dan index kebijakan.

### 3.3. Seeding database adalah langkah wajib setelah clone

Menjalankan PostgreSQL atau melihat container `healthy` tidak membuat tabel dan data sintetis. Setelah PostgreSQL aktif, jalankan:

```powershell
docker compose run --rm api python -m src.setup_lab
docker compose restart api
```

Untuk reset penuh dari volume baru atau database lama yang tidak lagi valid:

```powershell
docker compose down -v
docker compose up -d postgres redis
docker compose run --rm api python -m src.setup_lab
docker compose up -d api streamlit
```

Hati-hati: `docker compose down -v` menghapus seluruh volume PostgreSQL lokal.

### 3.4. Autentikasi Swagger memakai token mentah

Pada Swagger, klik **Authorize** dan masukkan:

```text
token-alya
```

Jangan memasukkan `Bearer token-alya` pada kolom Swagger, karena Swagger menambahkan prefix `Bearer` secara otomatis.

Untuk pengujian API langsung:

```http
Authorization: Bearer token-alya
```

Token demo di [demo_personas.json](demo_personas.json) dipetakan ke `employee_id`:

- `token-alya` -> `EMP-001`
- `token-bima` -> `EMP-002`
- `token-admin` -> `ADM-001`

Sistem menyimpan SHA-256 token, bukan token mentah. Jika Swagger menghasilkan `401 Invalid token`, periksa tabel berikut:

```powershell
docker compose exec postgres psql -U hr_app -d hr_assistant -c `
  "SELECT employee_id, display_name, role, token_hash FROM employee;"
```

### 3.5. Chunk kebijakan dan embedding harus diverifikasi terpisah

Seeding 15 section harus menghasilkan 15 baris pada tabel `policy_chunk`.

```powershell
docker compose exec postgres psql -U hr_app -d hr_assistant -c `
  "SELECT count(*) AS policy_chunk_count FROM policy_chunk;"

docker compose exec postgres psql -U hr_app -d hr_assistant -c `
  "SELECT count(*) AS chunk_count,
          count(embedding) AS embedded_chunk_count
   FROM policy_chunk;"
```

Untuk seeding lengkap:

```text
policy_chunk_count  = 15
embedded_chunk_count = 15
```

Tinjau daftar chunk bila perlu:

```powershell
docker compose exec postgres psql -U hr_app -d hr_assistant -c `
  "SELECT chunk_id, document_id, section, version
   FROM policy_chunk
   ORDER BY document_id, section;"
```

Jika jumlah chunk `15` tetapi jumlah embedding `0`, penyebab umumnya `EMBEDDING_MODEL` kosong atau konfigurasi tidak terbaca saat seeding. Perbaiki `.env`, recreate container API, lalu jalankan seeding lagi.

### 3.6. Retrieval dapat mempunyai dua jalur pencarian

[src/retrieval.py](src/retrieval.py) menggabungkan:

- pencarian leksikal PostgreSQL/TSVector;
- pencarian vektor pgvector jika embedding tersedia;
- Reciprocal Rank Fusion;
- keyword reranking.

Periksa pencarian leksikal secara langsung:

```powershell
docker compose exec postgres psql -U hr_app -d hr_assistant -c `
  "SELECT chunk_id, document_id, section,
          ts_rank(search_tsv, to_tsquery('simple', 'cuti | tahunan')) AS rank
   FROM policy_chunk
   WHERE search_tsv @@ to_tsquery('simple', 'cuti | tahunan')
   ORDER BY rank DESC
   LIMIT 5;"
```

Jika hasil pencarian kosong, perlu diperiksa kembali chunk atau bentuk query. Jika jumlah embedding `0`, cache atau service tidak boleh dianggap gagal; jalankan seeding ulang dengan model embedding aktif.

### 3.7. Urutan troubleshooting yang disarankan

1. Periksa environment yang terbaca oleh API.
2. Periksa `/healthz` dan `/readyz`.
3. Pastikan tabel `employee` berisi tiga persona demo.
4. Pastikan tabel `policy_chunk` berisi 15 chunk.
5. Pastikan jumlah `embedding IS NOT NULL` sama dengan jumlah chunk.
6. Uji pencarian leksikal secara langsung pada PostgreSQL.
7. Bersihkan cache Redis bila hasil pencarian lama tersimpan.
8. Uji endpoint `/api/v1/chat` melalui Swagger dengan token yang benar.

Urutan ini memisahkan kegagalan infrastruktur, database, konfigurasi LLM, seeding, retrieval, dan autentikasi sehingga akar masalah dapat ditentukan tanpa menebak.

---

## 4. Arsitektur Sistem & Alur Kerja

Sistem mengadopsi arsitektur *layered service* yang memisahkan presentasi, orkestrasi agent, layer domain bisnis, integrasi AI provider, dan persistence layer.

```text
               +-------------------------------------------+
               |        Frontend (Streamlit / app.py)      |
               +-------------------------------------------+
                                     |  HTTP (Bearer Token)
                                     v
               +-------------------------------------------+
               |         FastAPI REST API (src/api.py)     |
               +-------------------------------------------+
                                     |
               +-------------------------------------------+
               |       Orchestrator (src/agent.py)         |
               |  - Multi-Turn Loop   - Post-Processing    |
               |  - System Guardrails - Citation Validator |
               |  - Outcome Resolver  - PII Sanitization   |
               +-------------------------------------------+
                   /             |              \
                  v              v               v
       +-----------------+ +------------+ +--------------------+
       | Provider Layer  | | Tool Layer | | Security & Redact  |
       | (OpenAI / Mock) | | (4 Tools)  | | (Token, PII Mask)  |
       +-----------------+ +------------+ +--------------------+
                                 |
            +--------------------+--------------------+
            |                    |                    |
            v                    v                    v
     +--------------+     +--------------+     +---------------+
     |  retrieval   |     |    domain    |     |  repository   |
     | (Hybrid RAG) |     | (Leave Rule) |     |  (DB / State) |
     +--------------+     +--------------+     +---------------+
            |                    |                    |
            +---------+          |          +---------+
                      |          |          |
                      v          v          v
              +-----------------------------------+
              |      PostgreSQL / pgvector        |
              |   (Vector Embeddings & RDBMS)     |
              +-----------------------------------+
                                ^
                                | (Cache / Fallback)
              +-----------------------------------+
              |        Redis 7 (Alpine)           |
              +-----------------------------------+
```

### Komponen Utama

| Komponen | File Utama | Deskripsi Peran |
|---|---|---|
| **API Layer** | `src/api.py` | FastAPI server yang mengelola endpoint `/healthz`, `/readyz`, `/api/v1/chat`, proposal confirmation, dan monitoring. |
| **Agent Orchestrator** | `src/agent.py` | Mengelola *reasoning loop*, pemanggilan tools, validasi sitasi, klasifikasi outcome, serta pembatasan turn & token. |
| **Tool Execution** | `src/tools.py` | Mendefinisikan 4 tools: `search_hr_policy`, `get_my_leave_balance`, `prepare_leave_request`, dan `create_hr_ticket`. |
| **Domain Logic** | `src/domain.py` | Aturan bisnis cuti: kalkulasi hari kerja (*exclude weekend*), validasi tanggal masa lalu, overlap pengajuan, dan batas saldo. |
| **Hybrid Retrieval** | `src/retrieval.py` | Pencarian kebijakan kombinasi vektor embedding (`pgvector`) dan lexical matching untuk presisi tinggi. |
| **Security & Privacy** | `src/security.py` | Hashing bearer token (SHA-256), redaksi pola sensitif (PII/medis/API key), serta deteksi prompt injection. |
| **Storage & Repo** | `src/repository.py` | Abstraksi PostgreSQL untuk penyimpanan data pegawai, saldo, histori permohonan, proposal, tiket, dan audit trace. |
| **Cache Layer** | `src/cache.py` | *Resilient cache* Redis untuk mempercepat retrieval query kebijakan dengan mekanisme fallback aman (*fail-open*). |
| **Evaluasi Benchmark** | `src/run_evaluation.py` | Runner otomatis untuk 15 skenario benchmark evaluasi kualitas jawaban, kepatuhan batas keamanan, dan hard gate. |

---

## 5. Batasan Sistem & Kebijakan Keamanan (Security Boundaries)

1. **Zero-Trust & Identity Isolation**:
   - `employee_id` didapatkan secara deterministik dari database berdasarkan hash Bearer Token yang lolos autentikasi.
   - Tidak ada parameter `employee_id` pada payload percakapan pengguna maupun argumen tool model. Upaya pengguna meminta data atau saldo karyawan lain (`EMP-002`, dsb.) akan ditolak secara mutlak.
2. **Human-in-the-Loop & Status Cuti**:
   - Tidak ada tool atau endpoint yang dapat memberikan status `approved`.
   - Tool `prepare_leave_request` hanya menghasilkan proposal dengan masa berlaku (*expiry time*).
   - Pengajuan cuti resmi baru dibuat saat pengguna mengirimkan konfirmasi via endpoint `/api/v1/action-proposals/{id}/confirm` dengan *idempotency key*, dan statusnya selalu `pending_manager_review`.
3. **Grounded Retrieval & Sitasi Wajib**:
   - Jawaban atas pertanyaan kebijakan wajib menyertakan sitasi formal dalam format `[DOCUMENT-ID]` (misal: `[HR-LEAVE-001]`).
   - Agent memvalidasi apakah sitasi tersebut benar-benar ada dalam daftar potongan dokumen yang terambil (*retrieved chunks*) pada sesi tersebut. Jika sitasi palsu/halusinasi terdeteksi, jawaban otomatis diubah menjadi `abstained`.
4. **Perlindungan Data Medis & PII**:
   - Riwayat medis dan diagnosis sensitif (misal: diabetes, rekam medis) otomatis diredaksi sebelum jawaban dikirim ke pengguna.
5. **Trace & Monitoring RBAC**:
   - Trace percakapan disamarkan dan hanya dapat diakses oleh pemiliknya sendiri.
   - Endpoint monitoring (`/api/v1/monitoring/*`) hanya dapat diakses oleh pengguna dengan role `admin`.

---

## 6. Empat Outcome Status Percakapan

Setiap respons dari `POST /api/v1/chat` memuat status `outcome` yang terikat kontrak Pydantic:

| Status Outcome | Makna Teknis | Contoh Kasus Penggunaan |
|---|---|---|
| `answered` | Pertanyaan berhasil dijawab secara faktual dengan bukti sitasi dokumen yang valid. | Menjelaskan hak cuti tahunan (12 hari kerja) berdasarkan dokumen `[HR-LEAVE-001]`. |
| `action_proposed` | Permintaan aksi cuti valid; proposal berhasil dibuat dan menunggu konfirmasi pengguna. | Mengajukan cuti 3 hari di masa depan dengan saldo mencukupi (`requires_confirmation: true`). |
| `abstained` | Sistem menolak menjawab atau memproses aksi karena pelanggaran aturan, tanggal tidak valid, atau bukti tidak cukup. | Pengajuan cuti di masa lalu, saldo tidak cukup, dokumen kebijakan tidak ditemukan, atau sitasi palsu. |
| `escalated` | Pertanyaan/masalah tidak dapat diselesaikan secara otomatis dan diteruskan ke tim HR via tiket bantuan. | Terdapat pertentangan/konflik antar kebijakan yang memerlukan klarifikasi tim HR manusia. |

---

## 7. Kontrak Endpoint API

| Method | Path | Autentikasi | Deskripsi & Hasil |
|---|---|---|---|
| `GET` | `/healthz` | Publik | Liveness check; memastikan container/proses API aktif. |
| `GET` | `/readyz` | Publik | Readiness check; memverifikasi koneksi PostgreSQL, Redis, dan kesiapan index. |
| `POST` | `/api/v1/chat` | Bearer Token | Endpoint utama chat; mengembalikan `ChatResponse` (jawaban, sitasi, outcome, proposal, trace, token usage). |
| `POST` | `/api/v1/action-proposals/{proposal_id}/confirm` | Bearer Token | Konfirmasi proposal cuti menjadi permohonan `pending_manager_review` dengan idempotency key. |
| `GET` | `/api/v1/leave-requests/me` | Bearer Token | Mengambil daftar riwayat dan status permohonan cuti milik pegawai yang sedang login. |
| `GET` | `/api/v1/traces/{trace_id}` | Bearer Token | Mengambil detail audit trace tersamarkan (hanya milik sendiri atau admin). |
| `GET` | `/api/v1/monitoring/summary` | Bearer Token (Admin) | Statistik penggunaan token, total chat, distribusi outcome, dan error rate. |
| `GET` | `/api/v1/monitoring/alerts` | Bearer Token (Admin) | Mendeteksi kondisi darurat/anomali sistem (misal: error rate > 10%). |

---

## 8. Referensi Dokumentasi Teknis

Dokumentasi detail mengenai keputusan teknis, arsitektur, dan mitigasi risiko tersimpan di direktori `docs/`:


- [003-PENJELASAN_TECH_STACK_HR_AGENT_AWAM.md](docs/003-PENJELASAN_TECH_STACK_HR_AGENT_AWAM.md) — Panduan konseptual stack teknologi.
- [006-rancangan_table.md](docs/006-rancangan_table.md) — Desain skema basis data PostgreSQL.
- [008-checkpoint-penjelasan-fungsi-file.md](docs/008-checkpoint-penjelasan-fungsi-file.md) — Penjelasan detail fungsi setiap file backend.
- [015-GUARDRAIL-PROJECT-HR-AGENT.md](docs/015-GUARDRAIL-PROJECT-HR-AGENT.md) — Implementasi guardrail keamanan dan anti-injeksi.
- [017-PENJELASAN_PERAN_DAN_IMPLEMENTASI_REDIS.md](docs/017-PENJELASAN_PERAN_DAN_IMPLEMENTASI_REDIS.md) — Arsitektur caching dan degradasi Redis.
- [020-upaya-fix-NO-GO-CRITERIA.md](docs/020-upaya-fix-NO-GO-CRITERIA.md) & [021-coba-fix-outcome-miss.md](docs/021-coba-fix-outcome-miss.md) — Analisis akar masalah perbaikan kriteria evaluasi menuju status GO.
- [docker-delivery.md](docker-delivery.md) — Kontrak standar pengujian dan grading Docker.

---
