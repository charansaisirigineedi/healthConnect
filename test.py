from reportlab.lib.pagesizes import LETTER  
from reportlab.lib.units import inch 
from reportlab.pdfgen.canvas import Canvas  
from reportlab.lib.colors import purple  
from pypdf import PdfMerger


# creating the pdf file  
my_canvas = Canvas("textfile.pdf", pagesize = LETTER)  
# setting up the font and the font size  
my_canvas.setFont("Courier", 18)  
# setting up the color of the font as red  
my_canvas.setFillColor(purple)  
# writing this text on the PDF file   
my_canvas.drawString(2 * inch, 8 * inch, "Signature Page")  
my_canvas.save()

pdf1 = "existing.pdf"
pdf2 = "textfile.pdf"

# Create merger object 
merged_pdf = PdfMerger()

# Append PDFs
merged_pdf.append(pdf1)  
merged_pdf.append(pdf2)

# Write merged PDF
merged_pdf.write("combined.pdf") 

# Close object 
merged_pdf.close()

print("PDFs merged successfully!")