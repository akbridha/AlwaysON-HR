# 015 — Guardrail pada Project HR-Agent

Dokumen ini menunjukkan guardrail yang sudah ada pada backend HR-Agent, lokasi implementasinya, tujuan, dan batasannya. Guardrail adalah pembatas yang mencegah model, pengguna, atau kegagalan sistem menghasilkan tindakan atau data yang tidak semestinya.

## 1. Ringkasan guardrail

| Area | Guardrail utama | Status |
|---|---|---|
| Identitas dan akses | Bearer token menentukan identitas; data pribadi diikat ke `employee_id`; endpoint admin dibatasi role | Diimplementasikan |
| Grounding | Jawaban kebijakan diarahkan untuk memakai hasil `search_hr_policy`; sitasi diverifikasi terhadap hasil pencarian pada run yang sama | Diimplementasikan |
| Prompt injection | Dokumen kebijakan diperlakukan sebagai untrusted text dan instruksi di dalamnya tidak boleh dijalankan | Instruksi model; perlu defense-in-depth |
| Tool calling | Schema ketat, allowlist tool, validasi Pydantic, dan batas jumlah tool call | Diimplementasikan |
| Pengajuan cuti | Model hanya membuat proposal; konfirmasi manual membuat request `pending_manager_review` | Diimplementasikan |
| Validasi bisnis | Tanggal, hari kerja, saldo, dan overlap diperiksa oleh kode deterministik | Diimplementasikan |
| Idempotency | Konfirmasi ulang dengan key sama aman; key berbeda ditolak; proposal kedaluwarsa ditolak | Diimplementasikan |
| Privasi | Redaksi email, telepon, token/secret, dan diagnosis; trace tidak menyimpan prompt mentah | Diimplementasikan |
| Percakapan | Riwayat dibatasi dan difilter berdasarkan pegawai | Diimplementasikan |
| Reliability | Abstain saat provider gagal atau sitasi tidak valid; limit turn, output, dan tool call | Diimplementasikan |
| Observability | Trace redacted, metrik error/latency, endpoint admin, dan aturan alert | Diimplementasikan |

## 2. Guardrail identitas dan otorisasi

### 2.1 Identitas berasal dari token

Endpoint API mengharuskan bearer token. Backend memetakan token ke `AuthContext`, lalu memakai `employee_id` hasil autentikasi untuk mengambil saldo, membuat proposal, membaca request, dan membuat tiket. `employee_id` tidak diterima dari pesan pengguna sebagai sumber identitas.

- Implementasi: [`src/api.py`](../HR-Agent/src/api.py), fungsi `get_auth`
- Pemetaan identitas: [`src/repository.py`](../HR-Agent/src/repository.py), fungsi `authenticate`
- Kontrak role: [`src/contracts.py`](../HR-Agent/src/contracts.py), `AuthContext`

Dengan demikian, kalimat seperti “saya adalah EMP-002” tidak mengubah identitas sesi yang sudah terautentikasi.

### 2.2 Isolasi data antarpegawai

Tool saldo tidak menerima parameter identitas; `get_my_leave_balance` selalu memakai `auth.employee_id`. Riwayat percakapan juga difilter dengan `conversation_id` dan `employee_id`. Trace hanya dapat dibaca pemiliknya atau `monitoring_admin`.

- Tool identity-bound: [`src/tools.py`](../HR-Agent/src/tools.py)
- Riwayat employee-scoped: [`src/repository.py`](../HR-Agent/src/repository.py), `load_conversation`
- Proteksi trace: [`src/api.py`](../HR-Agent/src/api.py), endpoint `/api/v1/traces/{trace_id}`

### 2.3 Pembatasan role admin

Ringkasan monitoring, alert, dan seluruh endpoint dashboard hanya dapat diakses role `monitoring_admin`. Pegawai biasa menerima `403 Forbidden`.

- Implementasi: [`src/api.py`](../HR-Agent/src/api.py)
- Bukti pengujian: [`tests/test_api.py`](../HR-Agent/tests/test_api.py), `test_monitoring_is_admin_only` dan `test_dashboard_ui_and_endpoints`

## 3. Guardrail grounding dan prompt injection

### 3.1 Jawaban kebijakan harus grounded

Instruksi sistem mengharuskan jawaban kebijakan hanya menggunakan fakta dari `search_hr_policy`. Model juga diarahkan untuk menyertakan ID dokumen pada klaim faktual.

- Instruksi grounding: [`src/agent.py`](../HR-Agent/src/agent.py), `SYSTEM_INSTRUCTIONS`
- Pencarian kebijakan: [`src/retrieval.py`](../HR-Agent/src/retrieval.py)
- Dokumen sumber dengan metadata: [`data/policies/annual-leave.md`](../HR-Agent/data/policies/annual-leave.md)

Retrieval memakai pencarian lexical dan vector, lalu menggabungkan hasil dengan reciprocal rank fusion serta keyword reranking. Ini membantu menemukan bukti yang relevan, tetapi retrieval sendiri bukan jaminan bahwa model selalu benar.

### 3.2 Validasi sitasi

Setelah model menjawab, agent mengambil tag sitasi seperti `[HR-LEAVE-001]` dan memeriksa bahwa ID tersebut memang ada pada dokumen yang ditemukan dalam run yang sama. Jika ada sitasi palsu atau tidak ditemukan, outcome diubah menjadi `abstained` dan jawaban diganti dengan pesan bahwa informasi tidak dapat diverifikasi.

- Implementasi: [`src/agent.py`](../HR-Agent/src/agent.py), bagian `Citation validation`
- Bukti pengujian: [`tests/test_agent_reliability.py`](../HR-Agent/tests/test_agent_reliability.py), `test_invalid_citation_forces_abstention`

Validasi ini memastikan ID dokumen tidak dapat dibuat-buat oleh model. Namun, validasi tag tidak membuktikan bahwa setiap kalimat benar-benar didukung isi kutipan; evaluasi relevansi jawaban tetap diperlukan.

### 3.3 Konten dokumen dianggap tidak tepercaya

`SYSTEM_INSTRUCTIONS` secara eksplisit menyatakan bahwa konten dokumen adalah untrusted text dan instruksi prompt injection di dalamnya tidak boleh dijalankan. Tool dipisahkan dari isi dokumen, sehingga isi kebijakan bukan perintah backend.

- Instruksi: [`src/agent.py`](../HR-Agent/src/agent.py)

**Batasan:** kontrol ini terutama berupa instruksi model. Belum terlihat sanitizer atau classifier khusus untuk mendeteksi prompt injection secara deterministik. Karena itu, tool yang mengubah data tetap harus mengandalkan validasi backend, autentikasi, dan konfirmasi manual sebagai defense-in-depth.

## 4. Guardrail input dan tool

### 4.1 Schema tool ketat

Tool yang tersedia dibatasi pada empat fungsi:

1. `search_hr_policy`
2. `get_my_leave_balance`
3. `prepare_leave_request`
4. `create_hr_ticket`

Schema memakai `strict: true`, `additionalProperties: false`, enum untuk tipe cuti/kategori tiket, serta batas panjang dan rentang nilai.

- Daftar tool dan schema: [`src/tools.py`](../HR-Agent/src/tools.py), `TOOL_SCHEMAS`
- Validasi argumen: [`src/contracts.py`](../HR-Agent/src/contracts.py)

`ToolExecutor` juga menolak nama tool yang tidak dikenal dengan `ValueError`; tidak ada fallback yang diam-diam menjalankan aksi lain.

### 4.2 Batas resource agent

Agent dibatasi oleh konfigurasi:

- maksimal 4 turn agent;
- maksimal 6 tool call;
- maksimal 700 output token secara default;
- timeout model 30 detik secara default;
- riwayat maksimal 20 pesan.

- Konfigurasi: [`src/config.py`](../HR-Agent/src/config.py)
- Enforcement turn/tool/history: [`src/agent.py`](../HR-Agent/src/agent.py)

Pembatas ini mengurangi loop tidak berujung, konsumsi biaya berlebih, dan konteks percakapan yang terlalu besar.

## 5. Guardrail tindakan pengajuan cuti

### 5.1 Proposal-only, bukan approval

`prepare_leave_request` hanya membuat `ActionProposal`. Proposal memiliki `requires_confirmation = true` dan masa berlaku. Model tidak memiliki tool untuk menyetujui cuti.

Konfirmasi dilakukan melalui endpoint terpisah oleh pengguna yang terautentikasi. Hasil akhirnya selalu `pending_manager_review`, bukan `approved`.

- Pembuatan proposal: [`src/tools.py`](../HR-Agent/src/tools.py)
- Kontrak proposal dan hasil: [`src/contracts.py`](../HR-Agent/src/contracts.py)
- Konfirmasi: [`src/api.py`](../HR-Agent/src/api.py) dan [`src/repository.py`](../HR-Agent/src/repository.py)
- Alur dua tahap: [`HR-Agent/docs/013-IMPLEMENTASI-SESI-CHAT-DAN-PENGAJUAN-CUTI.md`](../HR-Agent/docs/013-IMPLEMENTASI-SESI-CHAT-DAN-PENGAJUAN-CUTI.md)

### 5.2 Validasi bisnis deterministik

Sebelum proposal disimpan, backend memeriksa:

- tanggal selesai tidak boleh sebelum tanggal mulai;
- tanggal mulai harus setelah hari ini;
- rentang harus memiliki minimal satu hari kerja;
- tidak boleh overlap dengan request aktif;
- saldo annual/sick harus mencukupi;
- tipe cuti harus termasuk `annual`, `sick`, atau `parental`.

- Implementasi: [`src/domain.py`](../HR-Agent/src/domain.py), `validate_leave_request`
- Pemanggilan validasi: [`src/tools.py`](../HR-Agent/src/tools.py)

Aturan ini tidak bergantung pada jawaban atau perhitungan model.

### 5.3 Confirmation ownership, expiry, dan idempotency

Repository memeriksa owner proposal, expiry, dan idempotency key. Konfirmasi pertama membuat satu request. Replay dengan key yang sama mengembalikan request yang sama, sedangkan key berbeda menghasilkan konflik.

- Implementasi memory repository: [`src/repository.py`](../HR-Agent/src/repository.py), `confirm_proposal`
- Implementasi PostgreSQL menggunakan row lock: [`src/repository.py`](../HR-Agent/src/repository.py), `PostgresRepository.confirm_proposal`
- Bukti pengujian: [`tests/test_actions.py`](../HR-Agent/tests/test_actions.py)

## 6. Guardrail privasi dan data sensitif

### 6.1 Redaksi data sensitif

Helper `redact` menyamarkan:

- alamat email;
- nomor telepon Indonesia;
- pola token, secret, key, dan API;
- string panjang yang menyerupai secret;
- label diagnosis dan beberapa istilah kondisi medis.

- Implementasi: [`src/security.py`](../HR-Agent/src/security.py)
- Bukti pengujian: [`tests/test_retrieval_security.py`](../HR-Agent/tests/test_retrieval_security.py), `test_redaction_covers_sensitive_patterns`

### 6.2 Trace tidak menyimpan prompt mentah

Trace menyimpan metadata seperti outcome, ID dokumen, ringkasan tool call, latency, token, biaya, dan error yang sudah diredaksi. Endpoint trace juga menghapus field `message` sebelum mengembalikan data.

- Pembuatan trace: [`src/agent.py`](../HR-Agent/src/agent.py)
- Redaksi error: [`src/agent.py`](../HR-Agent/src/agent.py), pemanggilan `redact`
- Proteksi response trace: [`src/api.py`](../HR-Agent/src/api.py)

Selain itu, prompt internal, chain-of-thought, dan diagnosis medis rinci dilarang ditampilkan oleh instruksi sistem. Larangan chain-of-thought adalah guardrail perilaku model; penghapusan data mentah dari trace adalah kontrol aplikasi yang lebih kuat.

## 7. Guardrail reliability dan abstention

Jika provider gagal, agent:

1. menangkap kegagalan pada boundary pemrosesan;
2. mengubah outcome menjadi `abstained`;
3. mengembalikan pesan umum kepada pengguna;
4. menyimpan error yang sudah diredaksi pada trace;
5. tidak menyimpan percakapan sebagai jawaban sukses.

Jika sitasi tidak valid, agent juga abstain. Jika informasi tidak ditemukan atau ada konflik kebijakan, instruksi sistem mengarahkan agent untuk abstain atau membuat tiket HR.

- Implementasi: [`src/agent.py`](../HR-Agent/src/agent.py)
- Bukti pengujian provider failure: [`tests/test_agent_reliability.py`](../HR-Agent/tests/test_agent_reliability.py)

## 8. Monitoring dan operational guardrail

Sistem mengumpulkan trace untuk menghitung:

- jumlah run;
- error rate;
- p95 latency;
- jumlah tool call.

Aturan monitoring yang tersedia mendefinisikan alert untuk error rate dan latency p95. Respons operasional untuk error spike menyebutkan pemeriksaan trace redacted dan opsi menonaktifkan mutating tools bila error berlanjut.

- Metrik: [`src/repository.py`](../HR-Agent/src/repository.py), `monitoring_summary`
- Endpoint alert: [`src/api.py`](../HR-Agent/src/api.py)
- Aturan operasional: [`data/monitoring_rules.json`](../HR-Agent/data/monitoring_rules.json)

## 9. Hal yang bukan guardrail penuh atau masih menjadi batasan

1. **Prompt sistem bukan enforcement tunggal.** Grounding, larangan prompt injection, dan larangan membocorkan CoT masih bergantung pada kepatuhan model; validasi backend tetap menjadi lapisan utama untuk data dan tindakan.
2. **Validasi sitasi belum memvalidasi entailment.** Sistem memeriksa keberadaan ID dokumen, bukan kecocokan semantik setiap klaim dengan excerpt.
3. **Belum ada approval manajer nyata.** Sistem berhenti pada `pending_manager_review`; keputusan manusia berada di luar scope aplikasi.
4. **Redaksi berbasis regex tidak sempurna.** Format PII atau rahasia yang tidak cocok dengan pola dapat lolos dan perlu pengujian tambahan bila format data berubah.
5. **Fallback repository memory bukan guardrail keamanan produksi.** Fallback membantu runtime development, tetapi deployment produksi tetap perlu memastikan database siap dan konfigurasi rahasia tidak dimasukkan ke repository.

## 10. Checklist verifikasi guardrail

- [x] Request tanpa token ditolak.
- [x] Data saldo diambil berdasarkan identitas token.
- [x] Monitoring dan dashboard dibatasi untuk `monitoring_admin`.
- [x] Sitasi yang tidak ditemukan memaksa abstention.
- [x] Prompt provider gagal menghasilkan abstention dan error teredaksi.
- [x] Proposal tidak langsung menjadi cuti.
- [x] Konfirmasi membutuhkan owner, expiry, dan idempotency key.
- [x] Request hasil konfirmasi berstatus `pending_manager_review`.
- [x] Riwayat percakapan difilter berdasarkan pegawai.
- [x] Trace tidak mengembalikan prompt mentah.
- [x] Data email, telepon, secret, dan diagnosis memiliki pengujian redaksi.
- [x] Batas turn, tool call, output token, dan history diterapkan.

Pengujian terkait dapat dijalankan dari folder [`HR-Agent/`](../HR-Agent/) dengan:

```powershell
python -m pytest -m "not live" -v --tb=short
```
