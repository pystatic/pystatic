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