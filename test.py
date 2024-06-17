from escpos.printer import Usb

p = Usb(0x04b8, 0x0202, profile="TM-T88II")

p.text("Hello World!\n")
p.cut()
print("Done")