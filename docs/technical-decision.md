OPEN AI
AGENT_MODEL=gpt-6-luna





Untuk generate skema table pakai metode di container. tapi kelemahannya untuk data besar bisa bermasalah. jadi data besar kaya seeding untuk Chunk data unstructure dieksekusi pakai python


Teknis yang sudah terbayang


| Jenis Outcome | Makna | Contoh |
|---|---|---|
| `answered` | Jawaban berhasil diberikan berdasarkan dokumen yang ditemukan dan relevan. | Menjawab bahwa jatah cuti tahunan adalah 12 hari dengan sitasi `[HR-LEAVE-001]`. |
| `abstained` | Sistem menolak menjawab karena bukti tidak cukup, permintaan tidak valid, atau terjadi kegagalan domain. Tidak ada fakta yang dipaksakan. | Tanggal cuti sudah lewat, kebijakan subsidi Mars tidak ditemukan, atau citasi tidak dapat diverifikasi. |
| `action_proposed` | Sistem telah menyiapkan proposal tindakan, tetapi belum dijalankan atau disetujui. | Menyiapkan cuti sebagai proposal dengan status `requires_confirmation: true`. |
| `escalated` | Permintaan tidak dapat diselesaikan sistem dan diteruskan melalui tiket atau mekanisme peninjauan manusia. | Konflik kebijakan dibuat menjadi tiket HR untuk ditinjau. |

- [x] 1. Bagaimana mengambil data cuti RDBMS untuk ditampilkan di Streamlit — tools sudah ada
- [x] 2. Otentikasi apakah login di Streamlit? — simulasi saja
- [ ] 3. Cara memasukkan payload dan riwayat
- [ ] 4. Penggunaan unstructured database
- [ ] 5. Menyetel system prompt supaya detail internal tidak terlihat, misalnya saat user meminta tools yang dimiliki agent
- [ ] 6. Guardrail
- [ ] 7. Membuat arsitektur.md
- [ ] 8. Membaca outline presentasi
- [ ] 9. Menentukan pakai vektor atau di RDBMS untuk chunk
