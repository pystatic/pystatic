if False:
    a = 1  # E This code is unreachable
if "":
    a = 1  # E This code is unreachable
if 0:
    a = 1  # E This code is unreachable

if True:
    a = 1
if "test":
    a = 1
if 99:
    a = 1

if True:
    a = 1
else:
    a = 1  # E This code is unreachable

while False:
    a = 1  # E This code is unreachable

while True:
    if False:
        a = 1  # E This code is unreachable
    else:
        a = 1


class A:
    ...


a = A()
while a:
    if a:
        b = 1
        if True:
            b = 1
        else:
            b = 1  # E This code is unreachable
    else:
        b = 1

while True:
    break
    b = 1  # E This code is unreachable

while True:
    if False:
        break  # E This code is unreachable
    else:
        b = 1
        break
        b = 1  # E This code is unreachable
    b = 1  # E This code is unreachable
