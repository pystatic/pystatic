import ast
import enum  
from typesys import TypeClassTemp, TypeTupleTemp, TypeVar
from typing import Callable, Tuple, Optional, Type
from pystatic.typesys import TypeIns,TypeTemp,TypeOptionalTemp,TypeTupleTemp


class compatibleState(enum.IntEnum):
    INVARIANT = 0
    CONVARIANT= 1
    CONTRIVARIANT=2 


class TypeCompatible:

    def __init__(self) -> None:
        self.baseTypestr=['Int','Float','Str','Complex','byte']
        self.collectionTypestr=['Tuple','Set','List','Dict']
        self.specialTypestr=['Callable','Literal','Any','None','Union','Optional']

    def TypeCompatible(self,a:TypeIns,b:TypeIns)->bool:
        tempa:TypeTemp=a.temp
        tempb:TypeTemp=b.temp
        
        if tempa.name in self.baseTypestr:
            return self.BaseTypeCom(tempa,tempb)
         

        elif tempa.name in self.specialTypestr:
            return self.SpecialTypeCom(tempa,tempb,compatibleState.CONVARIANT)
                
 
            
        elif (str(type(a))[-15:-2]=='TypeClassTemp'):
            return self.SpecificClassTypeCom(tempa,tempb,compatibleState.CONVARIANT)#此处语法有待丰富
              
        return False 



    def TypeCompatibleStrict(self,a:TypeIns,b:TypeIns)->bool:
        tempa:TypeTemp=a.temp
        tempb:TypeTemp=b.temp
        
        if tempa.name in self.baseTypestr:
            if tempa.name == tempb.name:
                return  True
            else:
                return False

        elif tempa.name in self.specialTypestr:
            if self.SpecialTypeCom(tempa,tempb,compatibleState.INVARIANT):
                return True
            else:
                return False

        elif tempa.name in self.collectionTypestr:
            if self.CollectionsTypeCom(tempa,tempb,compatibleState.INVARIANT):
                return True
            else:
                return False

        elif (str(type(a))[-15:-2]=='TypeClassTemp'):
            if self.SpecificClassTypeCom(tempa,tempb,compatibleState.INVARIANT):
                return True
            else:
                return False
        else:
            return False

    def BaseTypeCom(self,a:TypeTemp,b:TypeTemp)->bool:
        namea=a.name
        nameb=b.name
        if a== b:
            return True
        elif a=='Int' :
            if b== 'Bool':
                return True
            else :
                return False
        elif a== 'Float':
            if b=='Int' :
                return True
            else:
                return False
        elif a=='Complex':
            if b=='Int' or b=='Float':
                return True
            else :
                return False
        elif a=='Str' or a=='Bool' or a=='Byte' or a=='Bytearray':
            return False
        else:
            return False

    def SpecialTypeCom(self,tempa:TypeTemp,tempb:TypeTemp,state:compatibleState):    
        if  tempa.name=='Any' or tempb.name == 'Any':
            return True
        elif tempa.name=='None' or tempb.name == 'None':
            return False #None与其它类型的比较都返回False
        elif tempa.name=='Literal'or tempb.name=='Literal':#具体是如何存放的?
            if tempa.placeholders[0].name == tempb.placeholders[0].name:
                return True
            else:
                return False
        
        elif tempa.name == 'Optional':
            return self.OptionalCom(tempa,tempb)
        elif tempa.name == 'Union':
            return self.UnionCom(tempa,tempb,state)
        elif tempa.name == 'Callable':
            return self.CallableCom(tempa,tempb)
        else:
            return True

    def OptionalCom(self,a:TypeTemp,b:TypeTemp)->bool:
        return False
   


    def CallableCom(self,a:TypeTemp,b:TypeTemp)->bool:
        return False


    def CollectionsTypeCom(self,a:TypeTemp,b:TypeTemp,state:compatibleState)->bool:
        if a.name=='Set':
            return self.SetCom(a,b)
        elif a.name=='Tuple':
            return self.TupleCom(a,b,state)
        elif a.name == 'Dict':
            return self.DictCom(a,b)
        elif a.name=='List':
            return self.ListCom(a,b)
        else :
            return False

    def SetCom(self,a:TypeTemp,b:TypeTemp)->bool:#设定为Set的TypeTemp为TypeVar
        if self.TypeCompatibleStrict(a.placeholders[0].placeholders[0].constrains[0],b.placeholders[0].placeholders[0].constrains[0]):
            return True
        else:
            return False
            
    def TupleCom(self,a:TypeTemp,b:TypeTemp,state:compatibleState)->bool:
        if state==compatibleState.CONVARIANT:
            if len(a.placeholders[0].placeholders[0].constrains) != len(b.placeholders[0].placeholders[0].constrains):
                return False
            for index in range(len(a.placeholders[0].constrains)):
                if not self.TypeCompatible(a.placeholders[0].constrains[index],b.placeholders[0].constrains[index]):
                    return False
            return True
        elif state==compatibleState.INVARIANT:
            if len(a.placeholders[0].constrains) != len(b.placeholders[0].constrains):
                return False
            for index in range(len(a.placeholders[0].constrains)):
                if not self.TypeCompatibleStrict(a.placeholders[0].constrains[index],b.placeholders[0].constrains[index]):
                    return False
            return True
        else:
            return False

    def DictCom(self,a:TypeTemp,b:TypeTemp)->bool:
        if self.TypeCompatibleStrict(a.placeholders[0].constrains[0],b.placeholders[0].constrains[0]) and self.TypeCompatibleStrict(a.placeholders[0].constrains[1],b.placeholders[0].constrains[1]):
            return True
        else :
            return False

    def ListCom(self,a:TypeTemp,b:TypeTemp)->bool:
        if self.TypeCompatibleStrict(a.placeholders[0].constrains[0],b.placeholders[0].constrains[0]):
            return True
        else :
            return False


    
    def SpecificClassTypeCom(self,a:TypeClassTemp,b:TypeClassTemp,state:compatibleState)->bool:
        if a.name==b.name:
            return True
        elif state==compatibleState.INVARIANT:
            return False
        elif state==compatibleState.CONVARIANT:
            #考虑继承关系时，暂时只考虑到一层，即：无法处理 class A(B): class B(C): a:A=c:C
            #待补充#涉及到两层继承，无法使用最开始父类的值
            for index in range(len(a.baseclass)):
                if a.baseclass[index].temp.name==b.name:
                    return True
            return False 
        elif state==compatibleState.CONTRIVARIANT:
            for index in range(len(b.baseclass)):
                if b.baseclass[index].temp.name==a.name:
                    return True
            return False
        else :
            return False

                 
    def UnionCom(self,a:TypeTemp,b:TypeTemp,state:compatibleState)->bool:
        #Union会遇到与Union的判断吗
        return False
        '''
        for index in range(len(a)):
            if a.placeholders[index].invariant==True and self.TypeCompatibleStrict(a.placeholders[index].placeholders[0].constrains[0]:TypeIns,b:TypeIns):
                return True
            elif a.placeholders[index].convariant ==True and self.TypeCompatible(a,b):
                return True
            elif a.placeholders[index].contrivariant ==True and self.TypeCompatibletcontrivariant(a:TypeIns,b:TypeIns):
                return True
        return False
        '''

                
    def TypeVarCom(self,a:TypeVar,b:TypeVar)->bool:

        if a.invariant==True:
            if len(a.placeholders[0].constrains)!=len(b.placeholders[0].constrains):
                return False
            for index in range(len(a.placeholders[0].constrains)):
                if not self.TypeCompatibleStrict(a.placeholders[0].constrains[index],b.placeholders[0].constrains[index]):
                    return False
            return True
        
        elif a.covariant == True:
            if len(a.placeholders[0].constrains)!=len(b.placeholders[0].constrains):
                return False
            for index in range(len(a.placeholders[0].constrains)):
                if not self.TypeCompatible(a.placeholders[0].constrains[index],b.placeholders[0].constrains[index]):
                    return False
            return True

        elif a.contravariant == True:
            if len(a.placeholders[0].constrains)!=len(b.placeholders[0].constrains):
                    return False
            for index in range(len(a.placeholders[0].constrains)):
                if not self.TypeCompatible(a.placeholders[0].constrains[index],b.placeholders[0].constrains[index]):
                    return False
            return True

        else:
            return False
