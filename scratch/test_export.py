import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from highlight_extractor.schema import Highlight
from highlight_extractor.exporters import export_pdf, export_docx

hl = [
    Highlight(id="1", source_format="pdf", location="page 1", color="yellow", text="Hello world", note=None, order=0),
    Highlight(id="2", source_format="pdf", location="page 1", color="red", text="Danger text", note="Fix this", order=1),
]

try:
    pdf_bytes = export_pdf(hl)
    print(f"PDF bytes length: {len(pdf_bytes)}")
    with open("test.pdf", "wb") as f:
        f.write(pdf_bytes)
except Exception as e:
    print(f"PDF Error: {e}")

try:
    docx_bytes = export_docx(hl)
    print(f"DOCX bytes length: {len(docx_bytes)}")
    with open("test.docx", "wb") as f:
        f.write(docx_bytes)
except Exception as e:
    print(f"DOCX Error: {e}")
