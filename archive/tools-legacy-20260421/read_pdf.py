import pdfplumber

pdf_path = r'C:/Users/z1376/Zotero/storage/YU6XTEUF/Jazani和Pirhadi - 2018 - Design of dual-polarised (RHCPLHCP) quad-ridged horn antenna with wideband septum polariser wavegui.pdf'

with pdfplumber.open(pdf_path) as pdf:
    print(f'Total pages: {len(pdf.pages)}')
    for i, page in enumerate(pdf.pages[:15]):
        text = page.extract_text()
        if text:
            print(f'\n=== Page {i+1} ===')
            print(text[:3000] if len(text) > 3000 else text)