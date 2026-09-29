# Chạy phần mềm bằng Docker

Tài liệu này dùng để đóng gói và chạy phần mềm trên máy khác bằng Docker.

## 1. Cấu trúc cần mang sang máy khác

Cần mang các thư mục/file chính:

```text
Dockerfile
docker-compose.yml
requirements.txt
requirements-semantic.txt
cli.py
app/
models/
corpus/
data/          # có thể để trống nếu muốn build index lại
.env          # tùy chọn, dùng cho OpenAI API
```

Không cần mang:

```text
.venv/
__pycache__/
.pytest_cache/
```

## 2. Chuẩn bị file .env nếu dùng đánh giá online

Copy file mẫu:

```powershell
copy .env.example .env
```

Sửa `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_EVAL_MODEL=gpt-5.5
ONLINE_SEARCH_RESULTS=30
```

Nếu chỉ dùng kiểm tra local thì có thể để `OPENAI_API_KEY` trống.

## 3. Build container

```powershell
docker compose build
```

Image sẽ cài:

- Python dependencies.
- Tesseract OCR tiếng Việt và tiếng Anh.
- LibreOffice Writer để hỗ trợ đọc/chuyển đổi `.doc`.
- Poppler tools.
- Font Unicode/Noto để xử lý tài liệu tiếng Việt.

## 4. Build index trong container

Lần đầu hoặc khi muốn làm lại toàn bộ:

```powershell
docker compose run --rm plagiarism-checker python cli.py index --corpus /app/corpus --store /app/data --rebuild
```

Các lần sau, chỉ thêm file mới:

```powershell
docker compose run --rm plagiarism-checker python cli.py index --corpus /app/corpus --store /app/data
```

Kết quả index nằm trong thư mục host:

```text
data/
```

Nếu semantic embedding chạy đúng sẽ có:

```text
data/semantic_embeddings.npy
```

## 5. Chạy web

```powershell
docker compose up
```

Mở trình duyệt:

```text
http://127.0.0.1:8000
```

## 6. Thư mục volume

Docker Compose mount:

```text
./corpus  -> /app/corpus
./data    -> /app/data
./models  -> /app/models
```

Vì vậy:

- Thêm tài liệu cần index vào `corpus/`.
- Model embedding local đặt ở `models/vietnamese-sbert`.
- Báo cáo Word xuất ra nằm trong `data/reports`.

## 7. Kiểm tra OCR trong container

```powershell
docker compose run --rm plagiarism-checker tesseract --list-langs
```

Cần thấy:

```text
eng
vie
```

## 8. Kiểm tra model embedding trong container

```powershell
docker compose run --rm plagiarism-checker python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('/app/models/vietnamese-sbert'); print('OK')"
```

Nếu hiện `OK`, container đọc được model local.

## 9. Ghi chú

- Container không dùng `.venv` của Windows.
- Nếu sửa code, cần build lại image:

```powershell
docker compose build
```

- Nếu chỉ thêm tài liệu vào `corpus/`, không cần build image lại, chỉ chạy lại lệnh index.
