class A:
    pass


class A:  # E 'A' has already defined(A previously defined at line 1)
    pass


B = 3  # E 'B' is a class(B defined as a class at line 12)


class B:
    class C:
        pass

    class C:  # E 'C' has already defined(C previously defined at line 13)
        pass


class C:
    pass


C = 2  # E 'C' is a class(C defined as a class at line 20)

a: int = 2
b = 3
a: str = '3'  # E 'a' has already defined(a previously defined at line 26)
c = 3  # type: int
b: str = '2'
c: int = 2  # E 'c' has already defined(c previously defined at line 29)
