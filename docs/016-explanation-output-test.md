1. Tahap Build Image (p2m2_demo-api)
Sebelum test berjalan, Docker Compose membangun image container api:

Base image python:3.11-slim digunakan.
Dependensi dari requirements.txt diambil dari cache (CACHED).
Kode program src/, data/, tests/, assets/, serta file UI (app.py, ui_contract.py) disalin ke dalam container.
User non-root appuser (UID 1000) disiapkan untuk keamanan container.
2. Eksekusi Pytest (Deterministic Tests)
Waktu eksekusi: Sangat cepat (0.65 detik).
Total test: 29 test terdaftar.
1 Deselected: 1 test di tests/test_live_api.py dilewati karena Anda menyertakan flag -m "not live" (test live ke LLM asli sengaja tidak dijalankan pada tahap ini).
28 Passed (100% Lulus): Seluruh 28 unit & integration test lokal lulus tanpa error.
3. Komponen yang Berhasil Divalidasi
Kategori / File Test	Jumlah	Hal yang Terbukti Berhasil
Action & Konfirmasi
test_actions.py	3	Flow konfirmasi cuti bersifat idempoten, menolak employee ID / key yang salah, dan menolak proposal cuti yang sudah kedaluwarsa (expired).
Keandalan Agen (Reliability)
test_agent_reliability.py	3	Jika LLM provider gagal/down sistem aman tanpa efek samping (side-effect free), sitasi dokumen palsu/tidak valid memaksa agen untuk abstain (no hallucination), dan chunking metadata stabil.
API Endpoints & Kontrak
test_api.py	6	Endpoint /healthz, /readyz, dan otentikasi token valid; chat menghasilkan audit trace; isolasi data antar-karyawan aman (karyawan A tidak bisa membaca trace karyawan B); dan akses dashboard monitoring hanya untuk admin.
Sesi Chat Multi-Turn
test_chat_session.py	5	Riwayat percakapan tersimpan dengan benar per karyawan, LLM menerima konteks pesan sebelumnya, dan pergantian session ID memulai sesi baru yang bersih.
Domain Logic Cuti
test_domain.py	5	Kalkulasi hari kerja tidak menghitung akhir pekan, penolakan tanggal lampau atau tanggal selesai sebelum tanggal mulai, pencegahan cuti bentrok (overlap), serta pencegahan jika saldo cuti tidak mencukupi.
Keamanan & Retrieval
test_retrieval_security.py	3	Hybrid search memprioritaskan pencocokan leksikal, sistem menyensor data sensitif (PII), dan tool pengecekan saldo dikunci hanya untuk ID karyawan yang sedang login (no cross-employee parameter manipulation).
UI Streamlit
test_supplied_ui.py	3	Persona demo cocok dengan kontrak data, pergantian persona mereset state/proposal lama, dan UI memanggil rute API yang benar.
4. Dua Catatan Warning (Non-Fatal)
Starlette Deprecation Warning: Mengingatkan versi pustaka httpx pada TestClient.
PytestUnknownMarkWarning: Peringatan bahwa custom marker @pytest.mark.live belum didaftarkan di pytest.ini, bukan kegagalan logika program.