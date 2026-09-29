import os
from pathlib import Path
import joblib
from scipy import sparse

# 1. Kiểm tra chính xác đường dẫn đang được dùng
store = Path(os.getenv("PLAGIARISM_STORE", "./data")).resolve()
print(f"🔍 Đang kiểm tra thư mục: {store}\n")

try:
    # 2. Load các file vectorizer và matrix
    word_vec = joblib.load(store / "word_vectorizer.joblib")
    char_vec = joblib.load(store / "char_vectorizer.joblib")
    word_mat = sparse.load_npz(store / "word_matrix.npz")
    char_mat = sparse.load_npz(store / "char_matrix.npz")

    # 3. Lấy ra kích thước (số chiều) của từ điển và ma trận
    word_vocab_size = len(word_vec.vocabulary_)
    word_matrix_cols = word_mat.shape[1]
    
    char_vocab_size = len(char_vec.vocabulary_)
    char_matrix_cols = char_mat.shape[1]

    print("--- KIỂM TRA WORD (TỪ) ---")
    print(f"Từ điển Word có: {word_vocab_size} đặc trưng")
    print(f"Ma trận Word có: {word_matrix_cols} đặc trưng")
    if word_vocab_size == word_matrix_cols:
        print("✅ KHỚP NHAU!\n")
    else:
        print("❌ LỆCH NHAU!\n")

    print("--- KIỂM TRA CHAR (KÝ TỰ) ---")
    print(f"Từ điển Char có: {char_vocab_size} đặc trưng")
    print(f"Ma trận Char có: {char_matrix_cols} đặc trưng")
    if char_vocab_size == char_matrix_cols:
        print("✅ KHỚP NHAU!\n")
    else:
        print("❌ LỆCH NHAU!\n")

except Exception as e:
    print(f"🚨 Không thể đọc file. Lỗi: {e}")