# 017 - Penjelasan Peran, Arsitektur, dan Implementasi Redis pada Proyek HR-Agent

Dokumen ini merangkum secara komprehensif mengenai **tujuan keberadaan Redis**, **status implementasi di kode sumber proyek saat ini**, serta **analisis mendalam mengenai peran Redis sebagai *temporary conversation store***.

---

## 1. Pendahuluan: Apa itu Redis dan Mengapa Ada di Sini?

Dalam arsitektur sistem berbasis *microservices* dan *AI Agent*, **Redis** (*Remote Dictionary Server*) bertindak sebagai *in-memory key-value data store* yang beroperasi langsung di RAM (Random Access Memory). Karakteristik utamanya adalah latensi baca/tulis yang sangat rendah (*sub-millisecond*), dukungan struktur data kaya (string, hash, list, set), serta mekanisme kedaluwarsa data otomatis (*Time-To-Live* / TTL).

Pada berkas orkestrasi [`docker-compose.yml`](../HR-Agent/docker-compose.yml), service `redis` didefinisikan sebagai salah satu fondasi utama di samping `postgres`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["${REDIS_PORT:-6379}:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
```

Container `api` (FastAPI) terhubung ke Redis melalui *environment variable* `REDIS_URL=redis://redis:6379/0` dan bergantung pada kondisi kesehatan (`condition: service_healthy`) Redis sebelum mulai melayani request.

---

## 2. Peran Redis dalam Arsitektur Sistem HR-Agent

Berdasarkan rancangan teknis ([`architecture-percontainer.md`](../HR-Agent/templates/architecture-percontainer.md)), Redis dirancang untuk mengisi tiga fungsi utama:

```
                               ┌────────────────────────────────────────────────┐
                               │                 FastAPI (api)                  │
                               └─────────┬────────────────────────────┬─────────┘
                                         │                            │
                     (1) Cache Policy    │                            │ (2) Temporary Context
                         Hybrid Search   │                            │     & Session TTL
                                         ▼                            ▼
                               ┌───────────────────┐        ┌───────────────────┐
                               │   Redis (RAM)     │        │  PostgreSQL (Disk)│
                               │  - Retrieval Chunks│       │  - Relational Data│
                               │  - Session Hot Store│      │  - Vector pgvector│
                               │  - Fast Idempotency│       │  - Audit Traces   │
                               └───────────────────┘        └───────────────────┘
```

1. **RAG Retrieval Cache (Caching Pencarian Dokumen Kebijakan):**  
   Meringankan beban komputasi *embedding* dan kueri vektor ke database dengan menyimpan hasil hybrid search (dense vector + lexical BM25/FTS) untuk kueri-kueri kebijakan yang berulang.
2. **Temporary Conversation & Session Store (Penyimpanan Sesi Chat Sementara):**  
   Menyimpan riwayat putaran percakapan (*multi-turn turns*) yang sedang aktif dengan waktu kedaluwarsa otomatis (TTL) tanpa membebani tabel relasional database utama.
3. **Resilience & Rate Limiting / Idempotency Window:**  
   Menyediakan lapisan penyangga kilat untuk validasi *idempotency key* dan *action proposal draft* (verifikasi 2-langkah) sebelum commit permanen dilakukan ke database.

---

## 3. Status Implementasi Saat Ini di Kode Sumber

Secara faktual, bagaimana status implementasi Redis di kode proyek saat ini?

> **Kesimpulan:** Redis **sudah diimplementasikan dan aktif untuk RAG Retrieval Cache**, namun **belum difungsikan untuk Conversation Store**.

### A. Bagian yang SUDAH Menggunakan Redis: **RAG Retrieval Caching**

Implementasi caching retrieval kebijakan sudah berjalan penuh secara modular:

1. **Komponen Pembungkus Resilien ([`src/cache.py`](../HR-Agent/src/cache.py)):**  
   Dibuat kelas `ResilientCache` yang membungkus pustaka `redis`:
   * Dilengkapi penanganan kesalahan (*graceful error handling*): jika Redis mati atau koneksi putus, fungsi `get` mengembalikan `None` dan `set` mengabaikan error tanpa memutus alur kerja pengguna (*zero-crash policy*).
   * Disediakan `NullCache` sebagai *mock no-op* untuk keperluan *unit testing* cepat tanpa dependensi server Redis eksternal.
2. **Konfigurasi Lingkungan ([`src/config.py`](../HR-Agent/src/config.py)):**  
   * `redis_url: str = "redis://redis:6379/0"`
   * `retrieval_cache_ttl_seconds: int = 900` (Cache bertahan selama 15 menit).
3. **Eksekusi di Layanan Penelusuran ([`src/retrieval.py`](../HR-Agent/src/retrieval.py)):**  
   Pada metode `RetrievalService.search(...)`:
   ```python
   # Cek apakah query kebijakan sudah pernah dicari sebelumnya
   cache_key = f"retrieval:{query}:{top_k}"
   if self.cache_ttl_seconds > 0:
       cached = self.cache.get(cache_key)
       if cached:
           return [PolicyChunk(**item) for item in cached]

   # Jika cache-miss, jalankan hybrid search & reciprocal rank fusion
   ...

   # Simpan hasil pencarian ke Redis dengan TTL 15 menit
   if self.cache_ttl_seconds > 0 and results:
       self.cache.set(
           cache_key,
           [c.model_dump(mode="json") for c in results],
           ttl_seconds=self.cache_ttl_seconds
       )
   ```

---

### B. Bagian yang BELUM Menggunakan Redis: **Conversation & Session Store**

Pada implementasi saat ini, riwayat percakapan tidak disimpan di Redis, melainkan dialirkan melalui dua layer lain:

1. **Penyimpanan Permanen di PostgreSQL ([`data/init.sql`](../HR-Agent/data/init.sql) & [`src/repository.py`](../HR-Agent/src/repository.py)):**  
   Setiap putaran obrolan disimpan ke tabel `conversation_turn` di PostgreSQL:
   ```sql
   CREATE TABLE IF NOT EXISTS conversation_turn (
       id BIGSERIAL PRIMARY KEY,
       conversation_id TEXT NOT NULL,
       employee_id TEXT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
       role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
       content TEXT NOT NULL,
       created_at TIMESTAMPTZ NOT NULL DEFAULT now()
   );
   ```
   Metode `save_conversation_turn` dan `load_conversation` di `PostgresRepository` mengeksekusi `INSERT` dan `SELECT` SQL secara langsung.
2. **State Sesi di Frontend Streamlit ([`app.py`](../HR-Agent/app.py)):**  
   Frontend Streamlit menyimpan riwayat chat di memori lokal per sesi browser menggunakan `st.session_state["chat_history"]` dan `st.session_state["conversation_id"]`.

---

## 4. Keterangan Mendalam: Redis sebagai "Temporary Conversation Store"

Mengapa konsep **Temporary Conversation Store** menggunakan Redis sangat disarankan dalam arsitektur AI Agent modern?

### 1. Karakteristik Beban Kerja Chat LLM
LLM bersifat *stateless* (tidak memiliki ingatan antar panggilan API). Agar asisten bisa merespons pertanyaan lanjutan (*multi-turn follow up*), aplikasi backend harus menyuntikkan $N$ pesan terakhir ke dalam prompt LLM pada setiap request.
* **Tantangan jika hanya memakai SQL (PostgreSQL):**  
  Setiap pengguna mengetik satu pesan, server harus melakukan kueri disk/indeks SQL (`SELECT ... ORDER BY created_at DESC LIMIT N`). Jika terdapat ribuan pengguna simultan, ini menciptakan beban I/O yang tidak perlu pada database relasional.
* **Keunggulan Redis:**  
  Redis menyimpan objek obrolan langsung di RAM. Pembacaan pesan sebelumnya berlangsung dalam hitungan mikrodetik (*sub-millisecond*), meminimalkan latensi respons agen secara drastis.

### 2. Manajemen Siklus Hidup Otomatis dengan TTL (Time-To-Live)
Percakapan pengguna umumnya hanya relevan selama sesi berlangsung (misalnya aktif 30 sampai 60 menit):
* **Tanpa Redis (Tabel SQL Biasa):** Baris data percakapan akan terus menumpuk hingga jutaan baris, memerlukan proses cron *database cleanup* / *vacuuming* berkala.
* **Dengan Redis:** Cukup tetapkan TTL saat menyimpan:
  ```text
  SETEX conversation:EMP-001:CV-ABCD 3600 "<json_array_messages>"
  ```
  Jika pengguna tidak melanjutkan percakapan setelah 1 jam, memori sesi tersebut akan **dihapus secara otomatis oleh Redis** (*self-cleaning*).

### 3. Pola Arsitektur Ideal: *Hybrid Hot vs Cold Storage*

Pola terbaik untuk sistem enterprise seperti HR-Agent adalah membagi penyimpanan percakapan menjadi dua lapisan:

| Layer | Media | Tipe Data | Peran & Tujuan |
|---|---|---|---|
| **Hot Storage** | **Redis** | Objek Sesi Aktif + TTL (misal 1 Jam) | Cepat disuntikkan ke payload LLM di setiap putaran turn tanpa query disk. |
| **Cold Storage** | **PostgreSQL** | Tabel Audit & Trace Permanen (`agent_trace`) | Kepatuhan hukum, audit trail HR, deteksi anomali, dan evaluasi performa model. |

---

## 5. Contoh Konsep Integrasi Redis ke Sesi Percakapan

Jika Anda ingin meningkatkan efisiensi sistem dengan memfungsikan Redis sebagai *temporary conversation store*, modifikasi dapat dilakukan dengan menambahkan helper di `src/cache.py` atau `src/repository.py`:

```python
# Contoh alur Redis Temporary Conversation Store
class ConversationCache:
    def __init__(self, redis_client, ttl_seconds: int = 3600):
        self.client = redis_client
        self.ttl = ttl_seconds

    def save_turn(self, conversation_id: str, role: str, content: str):
        key = f"chat_session:{conversation_id}"
        # Simpan turn baru ke dalam list Redis
        turn_data = json.dumps({"role": role, "content": content})
        self.client.rpush(key, turn_data)
        # Perbarui batas waktu sesi setiap ada pesan baru
        self.client.expire(key, self.ttl)

    def load_history(self, conversation_id: str, max_turns: int = 6) -> list[dict]:
        key = f"chat_session:{conversation_id}"
        # Ambil N putaran pesan terakhir
        raw_items = self.client.lrange(key, -max_turns, -1)
        return [json.loads(item) for item in raw_items]
```

Dengan pola di atas:
1. `AgentService.run` pertama kali memeriksa sesi obrolan langsung dari Redis.
2. Jika sesi sudah kedaluwarsa dari Redis, sistem dapat melakukan *fallback* memuat dari PostgreSQL atau memulai percakapan baru.

---

## 6. Ringkasan Matriks Status Komponen

| Komponen / Fitur | Media Penyimpanan Saat Ini | Menggunakan Redis? | Catatan / Rekomendasi Selanjutnya |
|---|---|:---:|---|
| **Policy Hybrid Search Cache** | **Redis** (via `ResilientCache`) | ✅ **YA** | Berfungsi aktif dengan TTL 900 detik di `src/retrieval.py`. |
| **Penyimpanan Turn Obrolan** | **PostgreSQL** (`conversation_turn`) | ❌ *Belum* | Disimpan permanen di database SQL + Streamlit state. Cocok ditingkatkan ke Redis Hot Storage. |
| **Audit Trail & Token Trace** | **PostgreSQL** (`agent_trace`) | ❌ *Tidak* | Tepat tetap berada di PostgreSQL untuk keperluan kepatuhan dan audit jangka panjang. |
| **Draft Action Proposal** | **PostgreSQL** (`action_proposal`) | ❌ *Tidak* | Menggunakan kolom SQL `expires_at` (15 menit). Dapat dipindahkan ke Redis jika butuh auto-expire instan. |
