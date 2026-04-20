import os
import requests

downloads = {
    "Arabzadeh_2021_Sparse_vs_Dense.pdf": "https://arxiv.org/pdf/2109.10739.pdf",
    "Boer_2024_4StepFocus.pdf": "https://arxiv.org/pdf/2409.00861.pdf",
    "Boer_2025_Focus_Merge_Rank.pdf": "https://arxiv.org/pdf/2505.09246.pdf",
    "PathRAG_2025.pdf": "https://arxiv.org/pdf/2502.14902.pdf",
    "ARM_Chen_2025.pdf": "https://arxiv.org/pdf/2501.18539.pdf",
    "GraphRAG_Survey_Han_2024.pdf": "https://arxiv.org/pdf/2501.00309.pdf",
    "Edge_2024_GraphRAG_Local_to_Global.pdf": "https://arxiv.org/pdf/2404.16130.pdf",
    "HippoRAG_2024.pdf": "https://arxiv.org/pdf/2405.14831.pdf",
    "DPR_Karpukhin_2020.pdf": "https://aclanthology.org/2020.emnlp-main.550.pdf",
    "RAG_Lewis_2020.pdf": "https://arxiv.org/pdf/2005.11401.pdf",
    "HNSW_Malkov_2018.pdf": "https://arxiv.org/pdf/1603.09320.pdf",
    "Pan_2024_Unifying_LLM_KG.pdf": "https://arxiv.org/pdf/2306.08302.pdf",
    "Peng_2024_GraphRAG_Survey.pdf": "https://arxiv.org/pdf/2408.08921.pdf",
    "GNNRAG_Mavromatis_2024.pdf": "https://arxiv.org/pdf/2405.20139.pdf",
    "Sparse_Meets_Dense_Mandikal_2024.pdf": "https://arxiv.org/pdf/2401.04055.pdf"
}

target_dir = os.path.expanduser("~/src/agentic_memory_eval")
os.makedirs(target_dir, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

for filename, url in downloads.items():
    print(f"Downloading {filename}...")
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        with open(os.path.join(target_dir, filename), "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
