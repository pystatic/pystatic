 from typing import Generic, Literal,Tuple,List, TypeVar,Union,overload,Any

# class B:
#     ...


# class A(B):
#     def __init__(self):
#         self.hj: int = "sdfs"


# aa: int = 1
# a: A = A()
# a = B()
# a = B
# a.hj = "dsdfsd"
# a.b = False

# # class B:
# #     ...


# # class A(B):
# #     def __init__(self):
# #        super().__init__()
# #        self.hj=1
# #        reveal_type(self.hj)
# #        self.hj = "sad"
# #        reveal_type(self.hj)

# # b:complex = 1 +2j


# # # a: Literal[0] = 0

# # # b: Literal[5] = 5
# # c: Tuple[int, str, List[float]]  = (3, "abc", [True, False])
# # print(type(c))
# # some_tuple: Tuple[int, str, List[bool]] = (3, "abc", [True, False])
# # reveal_type(some_tuple[a])   # Revealed type is 'int'    
# # some_tuple[b]                # Error: 5 is not a valid index into the tuple

# # _PathType = Union[str, bytes, int]

# # @overload
# # def open(path: _PathType,
# #          mode: Literal["r", "w", "a", "x", "r+", "w+", "a+", "x+"],
# #          ) : ...
# # @overload
# # def open(path: _PathType,
# #          mode: Literal["rb", "wb", "ab", "xb", "r+b", "w+b", "a+b", "x+b"],
# #          ): ...

# # # Fallback overload for when the user isn't using literal types

# # # def open(path: _PathType, mode: str): ...
# # # open('D:\\AliveProject\\Pystatic\\pystatic\\pystatic\\preprocess\\main.py','x+')
# # a = 1 
# # b=a
# # print(type(a)

# # T = TypeVar('T',int,float)
# # F = TypeVar('F',bound = int )
# # E = TypeVar('E',int,float,contravariant = True)

# # class A(Generic[T,E]):
# #     pass
# # a:A[int,float]

# # a=(1,2,3)
# # print(type(a))
a:Any= 1
a = "qeqe"