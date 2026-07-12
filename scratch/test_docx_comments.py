import sys
from docx import Document
from docx.oxml.ns import qn

def extract_comments_and_formatting(docx_path: str):
    doc = Document(docx_path)
    
    # Extract comment metadata from comments part
    comments_meta = {}
    comments_part = None
    for rel in doc.part.rels.values():
        if "comments" in rel.reltype:
            comments_part = rel.target_part
            break
            
    if comments_part:
        for c in comments_part.element.findall(".//w:comment", namespaces=comments_part.element.nsmap):
            c_id = c.get(qn('w:id'))
            author = c.get(qn('w:author'), "")
            date = c.get(qn('w:date'), None)
            text = "".join(t.text for t in c.findall(".//w:t", namespaces=c.nsmap) if t.text)
            comments_meta[c_id] = {"author": author, "date": date, "text": text}
            
    # Now scan paragraphs for commentRangeStart/End and runs
    for para_idx, para in enumerate(doc.paragraphs):
        p_xml = para._element
        active_comments = set()
        
        for child in p_xml:
            tag = child.tag
            if tag == qn('w:commentRangeStart'):
                c_id = child.get(qn('w:id'))
                if c_id in comments_meta:
                    active_comments.add(c_id)
                    # We might want to track text for this comment
                    if "highlighted_text" not in comments_meta[c_id]:
                        comments_meta[c_id]["highlighted_text"] = []
                        
            elif tag == qn('w:commentRangeEnd'):
                c_id = child.get(qn('w:id'))
                if c_id in active_comments:
                    active_comments.remove(c_id)
                    
            elif tag == qn('w:r'):
                # Extract text for this run
                t_elements = child.findall(".//w:t", namespaces=child.nsmap)
                run_text = "".join(t.text for t in t_elements if t.text)
                if run_text and active_comments:
                    for c_id in active_comments:
                        comments_meta[c_id]["highlighted_text"].append(run_text)
                        
    for c_id, meta in comments_meta.items():
        htext = "".join(meta.get("highlighted_text", []))
        if htext:
            print(f"Comment {c_id}: '{htext}' -> {meta['text']} ({meta['date']})")
        else:
            print(f"Comment {c_id}: (no text) -> {meta['text']}")

extract_comments_and_formatting("test.docx")
