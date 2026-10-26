import os
from pypdf import PdfReader, PdfWriter

writer = PdfWriter()

cover_file = 'Project_Cover_Page_2.pdf' if os.path.exists('Project_Cover_Page_2.pdf') else 'Project_Cover_Page.pdf'
pref_file = 'Prefatory_Pages_2.pdf' if os.path.exists('Prefatory_Pages_2.pdf') else 'Prefatory_Pages.pdf'
main_file = 'Language_Agnostic_AI_Chatbot_Main_Report.pdf'

cover = PdfReader(cover_file)
pref = PdfReader(pref_file)
main = PdfReader(main_file)

# 1. Your original Cover Page
writer.add_page(cover.pages[0])

# 2. Your original Declaration, Certificate, Abstract, Acknowledgement (pages i to iv)
for p in pref.pages[0:4]:
    writer.add_page(p)

# 3. Synchronized ToC, List of Tables, List of Figures (pages v to viii from main report so page numbers 1-25 match)
for p in main.pages[5:9]:
    writer.add_page(p)

# 4. Your original List of Abbreviations (page ix)
writer.add_page(pref.pages[8])

# 5. All Main Report Chapters 1-6, References, and Appendices (Pages 1 to 25)
for p in main.pages[10:]:
    writer.add_page(p)

with open('Final_Synchronized_Report.pdf', 'wb') as f:
    writer.write(f)
print('Saved Final_Synchronized_Report.pdf with original cover/prefatory AND matching page numbers!')