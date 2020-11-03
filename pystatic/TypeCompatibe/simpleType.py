import ast
import enum
from typing import Callable, Tuple, Optional, Type, TypeVar, Union
from pystatic.typesys import TypeIns, TypeTemp, TypeOptionalTemp, TypeTupleTemp, TypeClassTemp


'''
phase2:
已经完成：基本类型,部分特别类型和直接子类型的判断和检查
把Literal的变量转为其所定义的类型
在查看Literal资料（PEP586)时：一些大家 需要知道的是：
    见md文件

    #把Union等特殊类型和容器类扁平化：Union[int,Union[str,float]]=Union[int,str,float] 
    把Optional转化为Union
    搞清楚陈瑄的测试用例
    需要cx和hj那边给予支持，现在的tuple list是不可测试的
 
    #下周可能做的事：关于别名和具体类型的子类型（这个应该不用特殊处理，直接当作一般类型判断就可以了吧） 
    a:A()=B实例和类型，type(B) 和B的temp具有相同的名字
'''

class compatibleState(enum.IntEnum):
    INVARIANT = 0
    CONVARIANT = 1
    CONTRIVARIANT = 2


class TypeCompatible:
    def __init__(self) -> None:
        self.baseTypestr = ['int', 'float', 'str', 'complex', 'byte', 'bool']
        self.collectionTypestr = ['Tuple', 'Set', 'List', 'Dict']
        self.specialTypestr = ['Callable', 'Literal', 'Any', 'None', 'Union', 'Optional']

    def TypeCompatible(self, a: TypeIns, b: TypeIns) -> bool:

        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        
        if  (isinstance(a,TypeIns) and not isinstance(b,TypeIns)) or (isinstance(b,TypeIns) and not isinstance(a,TypeIns)):
            return False

        if isinstance(a,TypeIns) and isinstance(b,TypeIns):
            return self.SpecificClassTypeCom(a, b, compatibleState.CONVARIANT)  # 此处语法有待丰富

        if tempb.name == 'Literal':
            return self.LiteralRightCom(a, b)

        elif tempa.name in self.baseTypestr:
            return self.BaseTypeCom(a, b, compatibleState.CONVARIANT)

        elif tempa.name in self.specialTypestr:
            return self.SpecialTypeCom(tempa, tempb, compatibleState.CONVARIANT)


        elif tempa.name in self.collectionTypestr:
            return self.CollectionsTypeCom(tempa, tempb, compatibleState.CONVARIANT)

        # need to change

        elif (str(type(tempa))[-15:-2] == 'TypeClassTemp'):

            return self.SpecificClassTypeCom(tempa, tempb, compatibleState.CONVARIANT)  # 此处语法有待丰富

        return False

    def LiteralRightCom(self, a: TypeIns, b: TypeIns) -> bool:
        rightstr: str = str(b)  # 暂时只是baseType
        if rightstr in self.baseTypestr and a.temp.name in self.baseTypestr:
            return self.Base2BaseTypeCom(a.temp.name, rightstr)
        if rightstr in self.baseTypestr and a.temp.name in self.specialTypestr:
            return self.Base2SpeTypeCom(rightstr, a.temp, compatibleState.CONVARIANT)

    def TypeCompatibleStrict(self, a: TypeIns, b: TypeIns) -> bool:
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp

        if tempa.name in self.baseTypestr:
            if tempa.name == tempb.name:
                return True
            else:
                return False

        elif tempa.name in self.specialTypestr:
            if self.SpecialTypeCom(tempa, tempb, compatibleState.INVARIANT):
                return True
            else:
                return False

        elif tempa.name in self.specialTypestr:
            if self.CollectionsTypeCom(tempa, tempb, compatibleState.INVARIANT):
                return True
            else:
                return False

        elif (str(type(tempa))[-15:-2] == 'TypeClassTemp'):
            if self.SpecificClassTypeCom(tempa, tempb, compatibleState.INVARIANT):
                return True
            else:
                return False
        else:
            return False

    def BaseTypeCom(self, a: TypeIns, b: TypeIns, state: compatibleState) -> bool:
        tempa = a.temp
        tempb = b.temp
        if tempa.name in self.baseTypestr and tempb.name in self.baseTypestr:
            return self.Base2BaseTypeCom(tempa.name, tempb.name)

        elif tempa.name in self.baseTypestr and tempb.name in self.specialTypestr:
            return self.Base2SpeTypeCom(tempa.name, tempb, compatibleState.CONVARIANT)

    def Base2BaseTypeCom(self, namea, nameb) -> bool:
        # print(namea)
        # print(nameb)
        if namea == nameb:
            return True
        elif namea == 'int':
            if nameb == 'bool':
                return True
            else:
                return False
        elif namea == 'float':
            if nameb == 'int':
                return True
            else:
                return False
        elif namea == 'complex':
            if nameb == 'int' or nameb == 'float':
                return True
            else:
                return False
        elif namea == 'str' or namea == 'bool' or namea == 'byte' or namea == 'Bytearray':
            return False
        else:
            return False

    def Base2SpeTypeCom(self, namea: str, tempb: TypeTemp, state: compatibleState) -> bool:
        nameb = tempb.name
        if nameb in self.specialTypestr:
            if nameb == 'Any':
                return True
            elif nameb == 'Optional':
                return self.OptionalCom(tempb, namea)
            elif nameb == 'None':
                return self.NoneCom(tempb, namea)
            elif nameb == 'Union':
                return self.UnionCom(tempb, namea)

    def SpecialTypeCom(self, tempa: TypeTemp, tempb: TypeTemp, state: compatibleState) -> bool:
        if tempa.name == 'Any' or tempb.name == 'Any':
            return True
        elif tempa.name == 'None' or tempb.name == 'None':
            return False  # None与其它类型的比较都返回False
        elif tempa.name == 'Literal' or tempb.name == 'Literal':  # 具体是如何存放的?
            if tempa.placeholders[0].name == tempb.placeholders[0].name:
                return True
            else:
                return False

        elif tempa.name == 'Optional':
            return self.OptionalCom(tempa, tempb)
        elif tempa.name == 'Union':
            return self.UnionCom(tempa, tempb)
        elif tempa.name == 'Callable':
            return self.CallableCom(tempa, tempb)
        else:
            return True

    def AnyCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        return True

    def UnionCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        # Union会遇到与Union的判断吗
        return False
        '''
        for index in range(len(a)):
            if a.placeholders[index].invariant==True and self.TypeCompatibleStrict(a.placeholders[index].constrains[0]:TypeIns,b:TypeIns):
                return True
            elif a.placeholders[index].convariant ==True and self.TypeCompatible(a,b):
                return True
            elif a.placeholders[index].contrivariant ==True and self.TypeCompatibletcontrivariant(a:TypeIns,b:TypeIns):
                return True
        return False
        '''

    def OptionalCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        return False

    def CallableCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        return False

    def NoneCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        return False

    def CollectionsTypeCom(self, a: TypeTemp, b: TypeTemp, state: compatibleState) -> bool:
        if a.name == 'Set':
            return self.SetCom(a, b)
        elif a.name == 'Tuple':
            return self.TupleCom(a, b, state)
        elif a.name == 'Dict':
            return self.DictCom(a, b)
        elif a.name == 'List':
            return self.ListCom(a, b)
        else:
            return False

    def SetCom(self, a: TypeTemp, b: TypeTemp) -> bool:  # 设定为Set的TypeTemp为TypeVar
        if self.TypeCompatibleStrict(a.constrains[0], b.constrains[0]):
            return True
        else:
            return False

    def TupleCom(self, a: TypeTemp, b: TypeTemp, state: compatibleState) -> bool:
        if state == compatibleState.CONVARIANT:
            if len(a.constrains) != len(b.constrains):
                return False
            for index in range(len(a.constrains)):
                if not self.TypeCompatible(a.constrains[index], b.constrains[index]):
                    return False
            return True
        elif state == compatibleState.INVARIANT:
            if len(a.constrains) != len(b.constrains):
                return False
            for index in range(len(a.constrains)):
                if not self.TypeCompatibleStrict(a.constrains[index], b.constrains[index]):
                    return False
            return True
        else:
            return False

    def DictCom(self, a: TypeTemp, b: TypeTemp) -> bool:
        if self.TypeCompatibleStrict(a.constrains[0], b.constrains[0]) and self.TypeCompatibleStrict(a.constrains[1],
                                                                                                     b.constrains[1]):
            return True
        else:
            return False

    def ListCom(self, a: TypeTemp, b: TypeTemp) -> bool:
        if self.TypeCompatibleStrict(a.constrains[0], b.constrains[0]):
            return True
        else:
            return False

    def SpecificClassTypeCom(self, a: TypeClassTemp, b: TypeClassTemp, state: compatibleState) -> bool:
        print(a.name)
        print(b.name)
        if a.name == b.name:
            return True
        elif state == compatibleState.INVARIANT:
            return False
        elif state == compatibleState.CONVARIANT:
            # 考虑继承关系时，暂时只考虑到一层，即：无法处理 class A(B): class B(C): a:A=c:C
            # 待补充#涉及到两层继承，无法使用最开始父类的值
            for index in range(len(a.baseclass)):
                if a.baseclass[index].temp.name == b.name:
                    return True
            return False
        elif state == compatibleState.CONTRIVARIANT:
            for index in range(len(b.baseclass)):
                if b.baseclass[index].temp.name == a.name:
                    return True
            return False
        else:
            return False

    def TypeVarCom(self, a: TypeVar, b: TypeVar) -> bool:

        if a.invariant == True:
            if len(a.constrains) != len(b.constrains):
                return False
            for index in range(len(a.constrains)):
                if not self.TypeCompatibleStrict(a.constrains[index], b.constrains[index]):
                    return False
            return True

        elif a.covariant == True:
            if len(a.constrains) != len(b.constrains):
                return False
            for index in range(len(a.constrains)):
                if not self.TypeCompatible(a.constrains[index], b.constrains[index]):
                    return False
            return True

        elif a.contravariant == True:
            if len(a.constrains) != len(b.constrains):
                return False
            for index in range(len(a.constrains)):
                if not self.TypeCompatible(a.constrains[index], b.constrains[index]):
                    return False
            return True

        else:
            return False


def type_consistent(tp1, tp2):
    # print(f"judge '{type(tp1)}' and '{type(tp2)}'")
    # print(f"judge '{tp1}' and '{tp2}'")
    res = TypeCompatible().TypeCompatible(tp1, tp2)
    print(f"type compatible of '{tp1}' and '{tp2}' is {res}")
    return res


def is_any(tp):
    return str(tp) == "Any"
 