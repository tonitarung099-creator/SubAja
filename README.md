# SubAja

**SubAja** adalah aplikasi Windows untuk menyempurnakan subtitle film Indonesia dari hasil transkripsi kasar CapCut tanpa menulis ulang dialog.

## Prinsip utama: Word Lock

SubAja memperlakukan kata dari SRT sebagai data terkunci. Aplikasi boleh mengubah:

- huruf besar/kecil,
- tanda baca,
- spasi dan line-break,
- pemisahan satu caption menjadi beberapa caption saat speaker berganti,
- timing hasil pemisahan.

Aplikasi **tidak boleh** mengganti `nggak` menjadi `tidak`, `udah` menjadi `sudah`, meringkas kalimat, menerjemahkan, atau mengubah urutan kata. Hasil Gemini divalidasi lagi secara lokal; bila urutan kata berubah, hasil AI otomatis ditolak.

## Gaya output default

SubAja mengikuti pola subtitle film Indonesia dari file referensi yang dipakai saat pengembangan:

- maksimal 2 baris,
- maksimal 42 karakter per baris,
- QC memberi tanda jika kecepatan baca melewati 19 karakter/detik,
- satu pembicara ditulis tanpa label nama,
- bila satu caption CapCut berisi dua pembicara dan pemisahannya cukup aman, hasil akhir memakai:
  `- dialog pembicara pertama`
  `- dialog pembicara kedua`,
- kata sumber tetap dikunci oleh Word Lock.

## Hemat Gemini Free

Gemini bersifat opsional. Speaker diarization, pemisahan dialog, formatting, QC, preview, dan export berjalan lokal. Mode Gemini Hemat hanya mengirim caption yang masih tampak memerlukan bantuan tanda baca/konteks. Caption yang sudah rapi dilewati dan hasil yang sudah pernah diproses memakai cache.

## Fitur MVP

- Import video film (`mp4`, `mkv`, `mov`, dll.).
- Import SRT CapCut.
- Preview video dan lompat ke timestamp subtitle dengan double-click.
- Speaker diarization lokal/offline memakai `sherpa-onnx`.
- Pemisahan caption ketika speaker berubah dengan Word Lock.
- Formatter lokal: kapitalisasi, spasi, line-break maksimal 2 baris.
- Gemini opsional untuk tanda baca/konteks **tanpa boleh mengubah kata**.
- Gemini API Manager dengan 100 slot dan satu key aktif.
- Tidak ada auto-rotation key saat terkena rate limit.
- Cache Gemini sehingga proses film panjang dapat dilanjutkan tanpa mengulang hasil yang sudah selesai.
- Export SRT bersih; label speaker opsional dan default-nya tidak ditampilkan.

## Menjalankan dari source

Direkomendasikan Python 3.11 64-bit.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/download_models.py
python run.py
```

## Membuat Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Hasil:

```text
dist/SubAja.exe
```

Workflow GitHub Actions juga tersedia untuk build otomatis pada Windows runner.

## Model speaker

Build memakai model speaker diarization offline yang didukung `sherpa-onnx`: model segmentasi Pyannote 3.0 ONNX int8 dan `nemo_en_titanet_small.onnx` sebagai speaker embedding extractor. Model diunduh oleh `scripts/download_models.py` saat build dan dibundel ke EXE.

## Catatan kualitas

Speaker diarization menentukan **siapa berbicara kapan**, bukan isi teks. SRT CapCut tetap menjadi sumber kata. Bila satu caption CapCut ternyata mencakup dua speaker, SubAja dapat membaginya berdasarkan boundary audio dan membagi kata secara proporsional tanpa mengubah kata. Karena SRT CapCut tidak memiliki timestamp per kata, pemisahan di tengah caption tetap perlu dicek pada kasus dialog yang sangat cepat atau tumpang tindih.
