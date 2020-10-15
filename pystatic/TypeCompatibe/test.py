myint:int=1
myfloat:float=3.0
mystr:str='hello'
mycomplex:complex=2+2j
mybool:bool=False
mybyte:bytes=b''
mybytearray:bytearray=bytearray(b'\n')
string=('int','float','str','complex','bool','bytes','bytearray')

myint=myfloat
myint=mystr
myint=mycomplex
myint=mybool
myint=mybyte
myint=mybytearray

myfloat=myint
myfloat=myfloat
myfloat=mystr
myfloat=mycomplex
myfloat=mybool
myfloat=mybyte
myfloat=mybytearray


mycomplex=myint
mycomplex=myfloat
mycomplex=mystr
mycomplex=mycomplex
mycomplex=mybool
mycomplex=mybyte
mycomplex=mybytearray

mystr=myint
mystr=myfloat
mystr=mystr
mystr=mycomplex
mystr=mybool
mystr=mybyte
mystr=mybytearray

mybool=myint
mybool=myfloat
mybool=mycomplex
mybool=mystr
mybool=mybool
mybool=mybyte
mybool=mybytearray

mybyte=myint
mybyte=myfloat
mybyte=mycomplex
mybyte=mystr
mybyte=mybool
mybyte=mybyte
mybyte=mybytearray

mybytearray=myint
mybytearray=myfloat
mybytearray=mycomplex
mybytearray=mystr
mybytearray=mybool
mybytearray=mybyte
mybytearray=mybytearray


class TypeTemp:
    def __init__(self,
                 name: str,
                 module_uri: str,
    ):
        self.name = name
        self.placeholders = []

        self.module_uri = module_uri  # the module uri that define this type


class TypeClassTemp(TypeTemp):
    # FIXME: remove None of symtable and defnode
    def __init__(self,
                 clsname: str,
                 module_uri: str,
                 defnode= None):
        super().__init__(clsname, module_uri)

t:TypeTemp=TypeClassTemp('hello','world')
print(type(t))
print(str(type(t))[-15:-2])


