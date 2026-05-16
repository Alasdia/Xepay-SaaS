from reportlab.pdfgen import canvas

c = canvas.Canvas("test.pdf")
c.drawString(100, 750, "Facture Xepay")
c.save()

print("PDF créé")