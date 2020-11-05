from typing import Tuple,List,Set,Dict,Union,Literal,Optional
#'Callable', 'Literal', 'Any', 'None', 'Union', 'Optional',
# myint:int =1
# mystr:str='a'


# myfloat: float = 3.0
# mystr: str = 'hello'
# mycomplex: complex = 2 + 2j
# mybool: bool = False


# myfloat: float = 3.0
# mystr: str = 'hello'
# mycomplex: complex = 2 + 2j
# mybool: bool = False



# myfloat: float = 3.0
# mystr: str = 'hello'
# mycomplex: complex = 2 + 2j
# mybool: bool = False

# myint = myfloat
# myint = mystr
# myint = mycomplex
# myint = mybool

# myfloat = myint
# myfloat = myfloat
# myfloat = mystr
# myfloat = mycomplex
# myfloat = mybool

# mycomplex = myint
# mycomplex = myfloat
# mycomplex = mystr
# mycomplex = mycomplex
# mycomplex = mybool

# mystr = myint
# mystr = myfloat
# mystr = mystr
# mystr = mycomplex
# mystr = mybool

# mybool = myint
# mybool = myfloat
# mybool = mycomplex
# mybool = mystr
# mybool = mybool






# mytuple:Tuple[int,str]=(1,'s')

myoptional:Optional[int]= 'a'
myoptional2:Optional[int]= 'str'
myoptional1  = myoptional2


mylist:List[int]=[1]
mylist2:List[str]=['a']
mylist = mylist2

myunion:Union[int,str]=1
myunion2:Union[int,str]='a'
myunion = myunion2
# myinstance1:Union[int,float]='a'
# muyints:Union[float,bool]=myinstance1