# 014 — Arahan Penyelesaian Sisa Task Milestone

Dokumen ini berisi urutan pekerjaan yang disarankan berdasarkan checkpoint minimal pipeline.

## 1. Jalankan deterministic test

Dari PowerShell:

```powershell
cd C:\Users\Lenovo\Main\AIeng\repo\milestone1-omnichannel_retail\PHASE2\HR-Agent

docker compose -p p2m2_demo run --rm api python -m pytest -m "not live" -v
```

Simpan bukti output:

```powershell
docker compose -p p2m2_demo run --rm api python -m pytest -m "not live" -v `
  | Tee-Object test-output.txt
```

Target: seluruh test lulus tanpa menjalankan test live.

## 2. Jalankan live evaluation 15 kasus

Pastikan service aktif:

```powershell
docker compose -p p2m2_demo up -d postgres redis
docker compose -p p2m2_demo run --rm api python -m src.setup_lab
docker compose -p p2m2_demo up -d api streamlit
```

Verifikasi endpoint:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
Invoke-RestMethod http://localhost:8000/readyz
```

Jalankan evaluator:

```powershell
docker compose -p p2m2_demo exec -T api `
  python -m src.run_evaluation http://localhost:8000 token-alya
```

> Catatan: `src/run_evaluation.py` menerima argumen positional, bukan `--base-url`
> dan `--token` seperti yang tertulis di beberapa dokumentasi.

Salin report ke workspace:

```powershell
docker compose -p p2m2_demo cp api:/app/outputs/evaluation_report.json .\outputs\evaluation_report.json
```

Target:

- 15 kasus dijalankan
- hard gate lulus 100%
- pass rate minimal 80%
- release decision: `GO`

## 3. Lengkapi diagram arsitektur

Isi [`HR-Agent/architecture.md`](../HR-Agent/architecture.md), bukan hanya template.

Diagram minimal harus menunjukkan:

- Streamlit ke FastAPI
- Bearer token dan identity boundary
- Agent loop dan tool execution
- PostgreSQL serta pgvector
- Redis cache dan fallback ketika Redis gagal
- OpenAI/provider boundary
- Confirmation flow: `prepare proposal` → konfirmasi pengguna → `pending_manager_review`
- Telemetry dan redaksi PII
- Evaluation runner
- Human/manager review
- Failure atau abstention flow

Gunakan referensi awal dari [`templates/architecture.md`](../HR-Agent/templates/architecture.md).

## 4. Buat risk register

Gunakan data awal dari [`templates/risk-register.csv`](../HR-Agent/templates/risk-register.csv).

Lengkapi kolom:

- `evidence`: bukti file, test, endpoint, atau screenshot
- `status`: misalnya `Mitigated`, `Monitoring`, atau `Open`
- owner dan mitigation yang masih kosong

Contoh evidence:

```text
R-001: tests/test_agent_reliability.py::test_fake_citation_abstains
R-004: tests/test_actions.py::test_cross_identity_blocked
R-006: repository.py confirmation path; status pending_manager_review
```

Ikuti lokasi yang diminta checkpoint: `PHASE2/docs/risk-register.md`.

## 5. Perbarui README

Perbarui [`HR-Agent/README.md`](../HR-Agent/README.md) dengan:

- model agent dan embedding yang digunakan
- perintah Docker dari checkout bersih
- perintah seed
- perintah deterministic test
- perintah live evaluation
- endpoint health dan readiness
- hasil test aktual
- batasan: tidak ada auto-approval, semua request berstatus `pending_manager_review`

Jangan mencantumkan API key atau isi `.env`.

## 6. Ambil bukti screenshot

Simpan screenshot ke folder [`HR-Agent/assets`](../HR-Agent/assets):

1. UI Streamlit dengan pertanyaan kebijakan dan citation
2. Saldo Alya
3. Proposal cuti sebelum konfirmasi
4. Hasil konfirmasi dengan status `pending_manager_review`
5. Monitoring/admin dashboard
6. Terminal test yang menunjukkan test lulus
7. Health/readiness endpoint bila diperlukan

Gunakan nama file yang jelas, misalnya:

```text
ui-policy-citation.png
ui-leave-proposal.png
ui-confirmation-pending.png
test-result.png
monitoring-dashboard.png
```

## 7. Lengkapi demo script

Isi [`templates/demo-script.md`](../HR-Agent/templates/demo-script.md) dengan alur:

1. Masalah dan target user
2. Diagram arsitektur
3. Policy Q&A dengan citation
4. Cek saldo sendiri
5. Percobaan akses pegawai lain yang diblokir
6. Proposal cuti
7. Konfirmasi dan status `pending_manager_review`
8. Idempotent replay
9. Abstention/failure
10. Evaluation dan residual risk

Sediakan backup berupa screenshot dan `evaluation_report.json`.

## 8. Pilih satu test prompt untuk dokumentasi manual

Disarankan memilih **Prompt 1** karena paling mudah dibuktikan:

- kebijakan: jatah tahunan 12 hari kerja
- database: saldo aktual Alya 8 hari
- jawaban harus memisahkan keduanya
- jawaban harus menyertakan citation kebijakan

Catat dengan format:

```text
Prompt:
Persona:
Expected behavior:
Actual behavior:
Pass/fail:
Failure reason:
Improvement step:
Evidence:
```

Jika model gagal, tidak perlu memperbaiki kode untuk prompt tersebut. Cukup jelaskan
penyebabnya, misalnya retrieval tidak menemukan dokumen yang tepat, citation validator
menolak citation, atau model mencampur policy balance dengan saldo database.

## Definition of Done

Milestone dapat dianggap selesai apabila:

- `pytest -m "not live"` lulus
- evaluator menjalankan 15 kasus
- hard gate lulus 100%
- report menghasilkan `GO`
- diagram final tersedia
- risk register lengkap
- README dapat diikuti dari environment bersih
- screenshot tersedia
- demo script dan backup output tersedia
- tidak ada `.env`, API key, database dump, atau data pribadi yang ikut dikumpulkan
