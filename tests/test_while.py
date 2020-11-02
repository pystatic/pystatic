import os
import binascii
import struct

misc = open("misc.png", "rb").read()

for i in range(1024000):
    data = misc[12:20] + struct.pack('>i', i) + misc[24:29]
    crc32 = binascii.crc32(data) & 0xffffffff
    if crc32 == 0xCDBE08A5:
        print(i)

# data = misc[16:19] + struct.pack('>i',1)+ misc[20:29]
# crc32 = binascii.crc32(data) & 0xffffffff
# print(crc32)
