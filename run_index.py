from app.indexer import build_index
from app.config import DEFAULT_STORE_DIR

if __name__ == "__main__":
    print("Bắt đầu build index với Semantic Model...")
    
    summary = build_index(
        corpus_dir=r"D:\local_plagiarism_checker\corpus", 
        store_dir=DEFAULT_STORE_DIR,
        semantic_model_path="keepitreal/vietnamese-sbert"
    )
    
    print("Hoàn tất quá trình Index!")
    print("Chi tiết:", summary)