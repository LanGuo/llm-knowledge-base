import os
import trafilatura
import requests
import fitz  # PyMuPDF
from pathlib import Path
from pdftext.extraction import plain_text_output
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class DocumentProcessor:
    def __init__(self, attachments_dir="attachments"):
        self.attachments_dir = Path(attachments_dir)
        self.attachments_dir.mkdir(exist_ok=True, parents=True)

    def process(self, file_path):
        """Processes a file and returns its text content, metadata, and attachment list."""
        path = Path(file_path)
        ext = path.suffix.lower()
        attachments = []

        try:
            if ext == '.pdf':
                text, meta = self._process_pdf(path)
                attachments = self._extract_pdf_images(path)
                return text, meta, attachments
            elif ext in ['.html', '.htm']:
                text, meta, attachments = self._process_web(path)
                return text, meta, attachments
            elif ext in ['.txt', '.md']:
                text, meta = self._process_text(path)
                return text, meta, []
            else:
                print(f"Unsupported file type: {ext}")
                return None, None, []
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            return None, None, []

    def _process_pdf(self, path):
        print(f"Processing PDF: {path}")
        text = ""
        try:
            # Try high-fidelity extraction first
            text = plain_text_output(str(path))
        except Exception as e:
            print(f"⚠️ High-fidelity PDF extraction failed for {path.name}, falling back to PyMuPDF. Error: {e}")
            try:
                # Fallback to robust PyMuPDF extraction
                doc = fitz.open(str(path))
                text = chr(12).join([page.get_text() for page in doc])
                doc.close()
            except Exception as fe:
                return f"Error extracting PDF: {str(fe)}", {"source": str(path), "type": "pdf"}

        if not text or not text.strip():
            return "Empty PDF content", {"source": str(path), "type": "pdf"}
            
        return text, {"source": str(path), "type": "pdf"}

    def _extract_pdf_images(self, path):
        """Extracts images from PDF and saves them to attachments/."""
        doc_name = path.stem
        paper_attachments_dir = self.attachments_dir / doc_name
        paper_attachments_dir.mkdir(exist_ok=True, parents=True)
        
        attachment_names = []
        try:
            doc = fitz.open(str(path))
            for page_index in range(len(doc)):
                for img_index, img in enumerate(doc.get_page_images(page_index)):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    ext = base_image["ext"]
                    
                    img_name = f"{doc_name}_p{page_index}_i{img_index}.{ext}"
                    img_path = paper_attachments_dir / img_name
                    
                    with open(img_path, "wb") as f:
                        f.write(image_bytes)
                    attachment_names.append(img_name)
            doc.close()
        except Exception as e:
            print(f"⚠️ Image extraction failed for {path.name}: {e}")
            
        return attachment_names

    def _process_web(self, path):
        print(f"Processing Web: {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='latin-1') as f:
                html_content = f.read()
        
        text = trafilatura.extract(html_content)
        if not text:
            text = "Could not extract text from HTML"
            
        attachments = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            doc_name = Path(path).stem
            web_attachments_dir = self.attachments_dir / doc_name
            web_attachments_dir.mkdir(exist_ok=True, parents=True)
            
            for idx, img in enumerate(soup.find_all('img')):
                src = img.get('src')
                if not src or src.startswith('data:'): continue
                img_name = f"{doc_name}_web_{idx}.png"
                attachments.append(img_name)
        except:
            pass

        return text, {"source": str(path), "type": "web"}, attachments

    def _process_text(self, path):
        print(f"Processing Text: {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='latin-1') as f:
                text = f.read()
        return text, {"source": str(path), "type": "text"}
