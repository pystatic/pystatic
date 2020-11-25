import ast
import enum
from pystatic.predefined import TypeLiteralIns
from typing import Callable, Tuple, Optional, Type, TypeVar, Union
from pystatic.typesys import TypeIns, TypeTemp,  TypeClassTemp,TypeType
from pystatic.predefined import TypeOptionalTemp, TypeTupleTemp,TypeCallableTemp
from pystatic.TypeCompatible.type2TypeTemp import Literal2Type

class compatibleState(enum.IntEnum):
    INVARIANT = 0
    COVARIANT = 1
    CONTRAVARIANT = 2


class TypeCompatible:
    def __init__(self) -> None:
        self.baseTypestr = ['int', 'float', 'str', 'complex', 'bytes', 'bool']
        self.collectionTypestr = ['Tuple', 'Set', 'List', 'Dict']
        self.specialTypestr = [
            'Callable', 'Literal', 'Any', 'None', 'Union', 'Optional'
        ]
        self.literal2Type = Literal2Type()

    def TypeCompatible(self, a: TypeIns, b: TypeIns) -> bool:    
        print(a,b,a.temp.name,b.temp.name) 
        print(type(a),type(b))   
        # c = a.bindlist[0]
        # print('CCCC')
        # print(c, b, c.temp.name, b.temp.name) 
        # print(type(a),type(b))   
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp 
        if tempa.name in self.baseTypestr:
            print('In  bastType')
            return self.BaseTypeCom(a, b,\
                                    compatibleState.COVARIANT)
        elif tempa.name in self.specialTypestr:
            print('{tempa.name} In specialTyperStr')
            return self.SpecialTypeCom(a, b,\
                                       compatibleState.COVARIANT)

        elif tempa.name in self.collectionTypestr:
            print('{tempa.name} In collection')
            return self.CollectionsTypeCom(a,b,
                                           compatibleState.COVARIANT)

        elif isinstance(a,TypeType) or isinstance(b,TypeType):
            if isinstance(a,TypeType) and isinstance(b,TypeType):
                return self.TypeTypeCom(a,b,compatibleState.COVARIANT) or self.TypeTypeCom(a,b,compatibleState.CONTRAVARIANT)
            else:
                return False

        elif (str(type(tempa))[-15:-2] == 'TypeClassTemp'):
            print('TypeclassTemp')
            return self.SpecificClassTypeCom(
                a, b, compatibleState.CONTRAVARIANT)  # 此处语法有待丰富

        return False



    def TypeCompatibleStrict(self, a: TypeIns, b: TypeIns) -> bool:
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        print(a,b,tempa.name,tempb.name)
       
        
     
        if tempa.name in self.baseTypestr:
            #print('{tempa.name} In baseTyperstr')
            return self.BaseTypeCom(a, b, compatibleState.COVARIANT)

        elif tempa.name in self.specialTypestr:
            #print('{tempa.name} In specialTyperStr')
            return self.SpecialTypeCom(a, b,
                                       compatibleState.COVARIANT)

        elif tempa.name in self.collectionTypestr:
            #print('{tempa.name} In collection')
            return self.CollectionsTypeCom(a,b,
                                           compatibleState.COVARIANT)

        elif isinstance(a,TypeType) or isinstance(b,TypeType):
            if isinstance(a,TypeType) and isinstance(b,TypeType):
                return self.TypeTypeCom(a,b,compatibleState.COVARIANT) or self.TypeTypeCom(a,b,compatibleState.CONTRAVARIANT)
            else:
                return False

        elif (str(type(tempa))[-15:-2] == 'TypeClassTemp'):
            print('TypeclassTemp')
            return self.SpecificClassTypeCom(
                a, b, compatibleState.CONTRAVARIANT)  # 此处语法有待丰富

        return False

    def TypeTypeCom(self,a:TypeType,b:TypeType,state:compatibleState):
        return self.SpecificClassTypeCom(a,b,state)

    def BaseTypeCom(self, a: TypeIns, b: TypeIns,
                    state: compatibleState) -> bool:
        print("IN BaseTypeCom")
        tempa:TypeTemp = a.temp
        tempb:TypeTemp = b.temp
        print(tempb.name)
        if tempb.name == 'Literal':
            print("IN BaseTypeCom1")
            b = self.literal2Type.Literal2SpecTypeIns(b)
            tempb= b.temp

        if tempa.name in self.baseTypestr and tempb.name in self.baseTypestr:
            print("IN BaseTypeCom12")
            return self.Base2BaseTypeCom(a, b)

        elif tempa.name in self.baseTypestr and tempb.name in self.specialTypestr:
            print("IN BaseTypeCom13")
            return self.Base2SpeTypeCom(a, b,
                                        compatibleState.COVARIANT)
        elif tempa.name in self.baseTypestr and str(type(tempb))[-15:-2] == 'TypeClassTemp':
            print('BASE SPECI')
            return  self.base_speci_com(a, b,
                                       compatibleState.COVARIANT)
        return False #此处如果涉及到定义基本类型的子类，待补充
    
    def base_speci_com(self, a:TypeIns, b:TypeIns, state:compatibleState):
        print('BASE SPECI')
        tempa:TypeTemp = a.temp
        tempb:TypeTemp = b.temp
        return self.specific_fa_com(tempa,tempb)
       

    def Base2BaseTypeCom(self,a, b) -> bool:
        namea=a.temp.name
        nameb=b.temp.name
        if namea == nameb:
            return True
        elif namea == 'int':
            if nameb == 'bool':
                return True
        elif namea == 'float':
            if nameb == 'int':
                return True
        elif namea == 'complex':
            if nameb == 'int' or nameb == 'float':
                return True
        return False

    def Base2SpeTypeCom(self, a:TypeIns, b: TypeIns,
                        state: compatibleState) -> bool:
        nameb = b.temp.name
        if nameb in self.specialTypestr:
            if nameb == 'Any':
                return True
            elif nameb == 'Optional':
                return self.OptionalCom(b, a)
            elif nameb == 'None':
                return self.NoneCom(b, a)
            elif nameb == 'Union':
                return self.UnionCom(b,a)

    def SpecialTypeCom(self,a:TypeIns, b:TypeIns,
                       state: compatibleState) -> bool:
        tempa:TypeTemp= a.temp
        tempb:TypeTemp=b.temp
       
        tempb = b.temp
        if tempa.name == 'Any' or tempb.name == 'Any':
            return True
        elif tempa.name == 'None':
            if tempb.name == 'None ':
                return True
            else:
                return False  # None与其它类型的比较都返回False

        if tempb.name == 'Literal' and tempa.name != 'Literal': #Literal只能存放None 和简单类型
            b = self.literal2Type.Literal2SpecTypeIns(b)
            print('Here')
            print(b)

        if tempa.name == 'Literal':  # 具体是如何存放的?
            return self.Literal_com(a,b)

        elif tempa.name == 'Optional':
            return self.OptionalCom(a, b)


        elif tempa.name == 'Union':
            return self.UnionCom(a, b)
        
        elif tempa.name == 'Callable':
            return self.CallableCom(a, b)
        else:
            return True

    def AnyCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        return True

    def UnionCom(self, a:TypeIns, b:TypeIns) -> bool:
        #print("UnionCom")
        tempb = b.temp
        for index in range(len(a.bindlist)):
            typeinsi= a.bindlist[index]
            ##print(typeinsi)
            ##print(type(typeinsi))
            if self.TypeCompatible(typeinsi,b):
                return True
        return False
        
        # ##print('In Tuple')
        # type1=a.bindlist[0]
        # type1Ins = type1.get_default_ins()
        # ##print(type1Ins)
        # ##print(type(type1Ins))
        # ##print(type(b))
        
        # if isinstance(b,TypeTemp):
        #     ##print('typetemp')
        #     return self.Base2BaseTypeCom(type1Ins.temp,b)

        # return False

    def OptionalCom(self, a: TypeIns, b: TypeIns) -> bool:
        print("OptionalCom")
        type1=a.bindlist[0]
        type1Ins = type1.get_default_ins()
        if self.TypeCompatible(type1Ins,b):
            return True
        elif b.temp.name == 'None':
            return True
        return False

    def CallableCom(self, a: TypeIns, b: Union[TypeIns, str]) -> bool:
        return False

    def NoneCom(self, a: TypeIns, b:TypeIns) -> bool:
        return False

    def CollectionsTypeCom(self, a: TypeIns, b: TypeIns,
                           state: compatibleState) -> bool:
        tempa:TypeTemp = a.temp
        tempb:TypeTemp = b.temp
        
        
        if tempa.name == 'Set':
            return self.SetCom(a, b)
        elif tempa.name == 'Tuple':
            return self.TupleCom(a, b, state)
        elif tempa.name == 'Dict':
            return self.DictCom(a, b)
        elif tempa.name == 'List':
            return self.ListCom(a, b)
        else:
            return False

    def SetCom(self, a: TypeIns,
               b: TypeIns) -> bool:  # 设定为Set的TypeTemp为TypeVar
        if self.TypeCompatibleStrict(a.bindlist[0], b.bindlist[0]):
            return True
        else:
            return False

    def TupleCom(self, a: TypeIns, b: TypeIns,
                 state: compatibleState) -> bool:
        if state == compatibleState.COVARIANT:
            if len(a.bindlist) != len(b.bindlist):
                return False
            for index in range(len(a.bindlist)):
                if not self.TypeCompatible(a.bindlist[index],
                                           b.bindlist[index]):
                    return False
            return True
        elif state == compatibleState.INVARIANT:
            if len(a.bindlist) != len(b.bindlist):
                return False
            for index in range(len(a.bindlist)):
                if not self.TypeCompatibleStrict(a.bindlist[index],
                                                 b.bindlist[index]):
                    return False
            return True
        else:
            return False

    def DictCom(self, a: TypeIns, b: TypeIns) -> bool:
        if self.TypeCompatibleStrict(
                a.bindlist[0],
                b.bindlist[0]) and self.TypeCompatibleStrict(
                    a.bindlist[1], b.bindlist[1]):
            return True
        else:
            return False

                

    def ListCom(self, a: TypeIns, b: TypeIns) -> bool:
        a = a.bindlist[0]
        tempb = self.literal2Type.Literal2SpecTypeTemp(b.bindlist[0])
       
        if a.temp.name==tempb.name:
            return True
        else:
            return False

    def Literal_com(self,a:TypeLiteralIns,b:TypeLiteralIns)->bool:
        print(a,b,a.temp.name,b.temp.name)
        print(type(a),type(b))
        print(type(a.value),type(b.value))
        return type(a.value)==type(b.value) and  a.value == b.value
        
    def SpecificClassTypeCom(self, a: Union[TypeIns,TypeType], b: Union[TypeIns,TypeType],
                             state: compatibleState) -> bool:
        tempa:TypeClassTemp = a.temp
        tempb:TypeClassTemp = b.temp
        if tempa.name == tempb.name:
            return True
        elif state == compatibleState.INVARIANT:
            return False
        elif state == compatibleState.COVARIANT:
            print(tempa.name)
            for index in range(len(tempa.baseclass)):
                print(tempa.baseclass[index].temp.name)
                if tempa.baseclass[index].temp.name == tempb.name:
                    return True
            return False
        elif state == compatibleState.CONTRAVARIANT:
            print(tempb.name)
            if str(type(tempb))[-15:-2] == 'TypeClassTemp':
                return self.specific_fa_com(tempa, tempb)
            else:
                return False 
        else:
            return False

    def specific_fa_com(self, tempa: TypeClassTemp, tempb: TypeClassTemp):
        print('SPECIFIC')
        print(tempa.name,tempb.name)
        if tempa == tempb :
            return True
        for index in range(len(tempb.baseclass)):
            print(tempb.baseclass[index].temp.name)
            if tempb.baseclass[index].temp.name == tempa.name:
                return True
            else :
                return self.specific_fa_com(tempa,tempb.baseclass[index].temp)
        return False
    # def TypeVarCom(self, a: TypeVar, b: TypeVar) -> bool:

    #     if a.invariant == True:
    #         if len(a.bindlist) != len(b.bindlist):
    #             return False
    #         for index in range(len(a.bindlist)):
    #             if not self.TypeCompatibleStrict(a.bindlist[index],
    #                                              b.bindlist[index]):
    #                 return False
    #         return True

    #     elif a.COVARIANT == True:
    #         if len(a.bindlist) != len(b.bindlist):
    #             return False
    #         for index in range(len(a.bindlist)):
    #             if not self.TypeCompatible(a.bindlist[index],
    #                                        b.bindlist[index]):
    #                 return False
    #         return True

    #     elif a.contravariant == True:
    #         if len(a.bindlist) != len(b.bindlist):
    #             return False
    #         for index in range(len(a.bindlist)):
    #             if not self.TypeCompatible(a.bindlist[index],
    #                                        b.bindlist[index]):
    #                 return False
    #         return True

    #     else:
    #         return False


def type_consistent(tp1, tp2):
    # print(f"judge '{tp1}' and '{tp2}'")
    res = TypeCompatible().TypeCompatible(tp1, tp2)
    # print(f"type compatible of '{tp1}' and '{tp2}' is {res}")
    return res


def is_any(tp):
    return str(tp) == "Any"

