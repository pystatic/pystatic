# constant
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

# unary op
if -0:
    a = 1  # E This code is unreachable
if -1:
    a = 1
else:
    a = 1  # E This code is unreachable
if +1:
    a = 1
else:
    a = 1  # E This code is unreachable
if not 1:
    a = 1  # E This code is unreachable

# compare
if sys.version_info >= (3,):
    a = 1
else:
    a = 1  # E This code is unreachable
if sys.version_info <= (3,):
    a = 1  # E This code is unreachable

# bool op
if True and False:
    a = 1  # E This code is unreachable
if False and True:
    a = 1  # E This code is unreachable
if False and False:
    a = 1  # E This code is unreachable
if True and True:
    a = 1
if True or True:
    a = 1
if False or True:
    a = 1
if True or False:
    a = 1
if False or False:
    a = 1  # E This code is unreachable

# error condition
if unknown:  # E Cannot determine type of 'unknown'(unresolved reference 'unknown')
    a = 1  # E This code is unreachable
t: int = 1

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

c = False
if c:
    a = 1  # E This code is unreachable
c = True
if c:
    a = 1
