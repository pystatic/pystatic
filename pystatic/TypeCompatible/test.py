from typing import List, Union, Optional
from typing import Tuple,Dict,Literal,List,Set
# b:Dict[int,str] = {1:12}

# c:Tuple[int,int,str]=(12,23,'a')
# d:Tuple[int,int,str]=(12,23,1)

# a = 1
# b:Literal[1] =a 
t1 = "s"
if random():
    t1 = 1
t2: Union[int, bool] = input()
t3: Optional[int] = input()
a: int = t1
b: int = t2
c: None = t3

# test1:Literal['test']=1
# f = 'test'
# test1:Literal['test']=f

# w:List[int]=[1,2,'a',1]
# s:Set[int]={1,3,'a',1}

# # (1) there is a correct test, but the error is shown below. 
# class A:
#     pass

# class B(A):
#     pass

# class C(B):
#     pass

# a: A = C()

# # (2) there is a correct test, but the error is shown below. 
# # there're some problems when it is about base type
# class D(int):
#     pass

# t: int = D()

# t: int = float(1)