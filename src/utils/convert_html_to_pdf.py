# convert_html_to_pdf.py
from weasyprint import HTML

# read from a file on disk
HTML(filename="index.html").write_pdf("mlh_rfi_20250718.pdf")

# — or — convert from an HTML string:
# html_string = "<h1>Hello PDF</h1><p>This is a PDF!</p>"
# HTML(string=html_string).write_pdf("output.pdf")
