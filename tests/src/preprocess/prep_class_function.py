class A:
    def __init__(self) -> None:
        pass

    def good(self, a: str):
        return "good"


a = A()
a.good()  # E Too few arguments(missing a)
a.good("hello")
