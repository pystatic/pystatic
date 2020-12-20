import enum
from typing import Union
from pystatic.typesys import TypeAnyTemp, TypeIns, TypeTemp, TypeClassTemp, TypeType
from pystatic.predefined import *


class compatibleState(enum.IntEnum):
    INVARIANT = 0
    COVARIANT = 1
    CONTRAVARIANT = 2


class TypeCompatible:
    def __init__(self) -> None:
        self.baseType = [
            int_temp,
            float_temp,
            str_temp,
            complex_temp,
            byte_temp,
            bool_temp,
        ]
        self.collectionType = [TypeTupleTemp, TypeSetTemp, TypeListTemp, TypeDictTemp]
        self.specialType = [
            TypeCallableTemp,
            TypeAnyTemp,
            TypeNoneTemp,
            TypeUnionTemp,
            TypeOptionalTemp,
            TypeLiteralTemp,
        ]

    def baseclassify(self, temp: TypeTemp, mylist):
        for item in mylist:
            if temp == item:
                return True
        return False

    def classify(self, temp: TypeTemp, mylist):
        for item in mylist:
            if isinstance(temp, item):
                return True
        return False

    def TypeCompatible(self, a: TypeIns, b: TypeIns) -> bool:
        if a == any_ins or b == any_ins:
            return True
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        if self.baseclassify(tempa, self.baseType):
            return self.BaseTypeCom(a, b, compatibleState.COVARIANT)
        elif self.classify(tempa, self.specialType):
            return self.SpecialTypeCom(a, b, compatibleState.COVARIANT)
        elif self.classify(tempa, self.collectionType):
            return self.CollectionsTypeCom(a, b, compatibleState.COVARIANT)
        elif isinstance(a, TypeType) or isinstance(b, TypeType):
            if isinstance(a, TypeType) and isinstance(b, TypeType):
                return self.TypeTypeCom(
                    a, b, compatibleState.COVARIANT
                ) or self.TypeTypeCom(a, b, compatibleState.CONTRAVARIANT)
            else:
                return False
        elif isinstance(tempa, TypeClassTemp):
            return self.SpecificClassTypeCom(a, b, compatibleState.CONTRAVARIANT)
        return False

    def TypeCompatibleStrict(self, a: TypeIns, b: TypeIns) -> bool:
        if a == any_ins or b == any_ins:
            return True
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        if self.baseclassify(tempa, self.baseType):
            return self.BaseTypeCom(a, b, compatibleState.INVARIANT)
        elif self.classify(tempa, self.specialType):
            return self.SpecialTypeCom(a, b, compatibleState.INVARIANT)
        elif self.baseclassify(tempa, self.baseType):
            return self.CollectionsTypeCom(a, b, compatibleState.INVARIANT)
        elif isinstance(a, TypeType) or isinstance(b, TypeType):
            if isinstance(a, TypeType) and isinstance(b, TypeType):
                return self.TypeTypeCom(
                    a, b, compatibleState.INVARIANT
                ) or self.TypeTypeCom(a, b, compatibleState.INTRAVARIANT)
            else:
                return False
        elif isinstance(tempa, TypeVarTemp):
            return False
        elif isinstance(tempa, TypeClassTemp):
            return self.SpecificClassTypeCom(a, b, compatibleState.INVARIANT)
        return False

    def TypeTypeCom(self, a: TypeType, b: TypeType, state: compatibleState):
        return self.SpecificClassTypeCom(a, b, state)

    def BaseTypeCom(self, a: TypeIns, b: TypeIns, state: compatibleState) -> bool:
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        if isinstance(tempb, TypeLiteralTemp):
            assert isinstance(b, TypeLiteralIns)
            b = b.get_value_type()
            tempb = b.temp
        if self.baseclassify(tempa, self.baseType) and self.baseclassify(
            tempb, self.baseType
        ):
            return self.Base2BaseTypeCom(a, b)
        elif self.baseclassify(tempa, self.baseType) and self.classify(
            tempb, self.specialType
        ):
            return self.Base2SpecialTypeCom(a, b, compatibleState.COVARIANT)
        elif (
            self.baseclassify(tempa, self.baseType)
            and str(type(tempb))[-15:-2] == "TypeClassTemp"
        ):
            return self.Base2specificTypeCom(a, b, compatibleState.COVARIANT)
        return False

    def Base2specificTypeCom(self, a: TypeIns, b: TypeIns, state: compatibleState):
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        assert isinstance(tempb, TypeClassTemp)
        return self.inheritance_check(tempa, tempb)

    def Base2BaseTypeCom(self, a, b) -> bool:
        tempa = a.temp
        tempb = b.temp
        if tempa == tempb:
            return True
        elif tempa == int_temp:
            if tempb == bool_temp:
                return True
        elif tempa == float_temp:
            if tempb == int_temp:
                return True
        elif tempa == complex_temp:
            if tempb == int_temp or tempb == float_temp:
                return True
        return False

    def Base2SpecialTypeCom(
        self, a: TypeIns, b: TypeIns, state: compatibleState
    ) -> bool:
        tempb: TypeTemp = b.temp
        assert self.classify(tempb, self.specialType)
        if isinstance(tempb, TypeAnyTemp):
            return False
        elif isinstance(tempb, TypeOptionalTemp):
            # TODO: implement this
            return True
        elif isinstance(tempb, TypeNoneTemp):
            return self.NoneCom(b, a)
        elif isinstance(tempb, TypeUnionTemp):
            return self.UnionRightCom(b, a)
        elif isinstance(tempb, TypeLiteralTemp):
            return self.Literal_com(b, a)

    def SpecialTypeCom(self, a: TypeIns, b: TypeIns, state: compatibleState) -> bool:
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp

        if isinstance(tempa, TypeAnyTemp) or tempb == TypeAnyTemp:
            return True
        elif isinstance(tempa, TypeNoneTemp):
            return self.NoneCom(a, b)
        elif isinstance(tempa, TypeLiteralTemp):
            assert isinstance(tempa, TypeLiteralTemp)
            return self.Literal_com(a, b)
        elif isinstance(tempa, TypeOptionalTemp):
            return self.OptionalLeftCom(a, b)
        elif isinstance(tempa, TypeUnionTemp):
            return self.UnionLeftCom(a, b)
        elif isinstance(tempa, TypeCallableTemp):
            return self.CallableCom(a, b)
        else:
            return False

    def AnyCom(self, a: TypeTemp, b: Union[TypeTemp, str]) -> bool:
        return True

    def UnionLeftCom(self, a: TypeIns, b: TypeIns) -> bool:
        tempb = b.temp
        if a.bindlist is None:
            return False
        for index in range(len(a.bindlist)):
            typeinsi = a.bindlist[index]
            if self.TypeCompatible(typeinsi, b):
                return True
        return False

    def UnionRightCom(self, a: TypeIns, b: TypeIns) -> bool:
        tempb = b.temp
        assert a.bindlist != None
        for index in range(len(a.bindlist)):
            typeinsi = a.bindlist[index]
            if not self.TypeCompatible(typeinsi, b):
                return False
        return True

    def OptionalLeftCom(self, a: TypeIns, b: TypeIns) -> bool:
        type1 = a.bindlist[0]
        if self.TypeCompatible(type1, b):
            return True
        elif isinstance(b.temp, TypeNoneTemp):
            return True
        return False

    def CallableCom(self, a: TypeIns, b: Union[TypeIns, str]) -> bool:
        return False

    def NoneCom(self, a: TypeIns, b: TypeIns) -> bool:
        if isinstance(b.temp, TypeNoneTemp):
            return True
        return False

    def CollectionsTypeCom(
        self, a: TypeIns, b: TypeIns, state: compatibleState
    ) -> bool:
        tempa: TypeTemp = a.temp
        tempb: TypeTemp = b.temp
        if isinstance(tempa, TypeSetTemp):
            return self.SetCom(a, b)
        elif isinstance(tempa, TypeTupleTemp):
            if not isinstance(tempb, TypeTupleTemp):
                return False
            return self.TupleCom(a, b, state)
        elif isinstance(tempa, TypeDictTemp):
            return self.DictCom(a, b)
        elif isinstance(tempa, TypeListTemp):
            if not isinstance(b, TypeListTemp):
                return False
            return self.ListCom(a, b)
        else:
            return False

    def SetCom(self, a: TypeIns, b: TypeIns) -> bool:
        if a.bindlist and not b.bindlist:
            return False
        elif b.bindlist and not a.bindlist:
            return False

        if len(a.bindlist) != len(b.bindlist):
            return False
        if self.TypeCompatibleStrict(a.bindlist[0], b.bindlist[0]):
            return True
        else:
            return False

    def TupleCom(self, a: TypeIns, b: TypeIns, state: compatibleState) -> bool:
        if state == compatibleState.COVARIANT:
            assert a.bindlist != None
            assert b.bindlist != None
            if len(a.bindlist) != len(b.bindlist):
                return False
            for index in range(len(a.bindlist)):
                if not self.TypeCompatible(a.bindlist[index], b.bindlist[index]):
                    return False
            return True
        elif state == compatibleState.INVARIANT:
            assert a.bindlist != None and b.bindlist != None
            if len(a.bindlist) != len(b.bindlist):
                return False
            for index in range(len(a.bindlist)):
                if not self.TypeCompatibleStrict(a.bindlist[index], b.bindlist[index]):
                    return False
            return True
        else:
            return False

    def DictCom(self, a: TypeIns, b: TypeIns) -> bool:
        if not a.bindlist or not b.bindlist:
            return False
        if self.TypeCompatibleStrict(
            a.bindlist[0], b.bindlist[0]
        ) and self.TypeCompatibleStrict(a.bindlist[1], b.bindlist[1]):
            return True
        else:
            return False

    def ListCom(self, a: TypeIns, b: TypeIns) -> bool:
        a = a.bindlist[0]
        b = b.bindlist[0]
        return self.TypeCompatible(a, b)

    def Literal_com(self, a: TypeLiteralIns, b: TypeLiteralIns) -> bool:
        return a.equiv(b)

    def SpecificClassTypeCom(
        self,
        a: Union[TypeIns, TypeType],
        b: Union[TypeIns, TypeType],
        state: compatibleState,
    ) -> bool:
        assert isinstance(a.temp, TypeClassTemp)
        tempa: TypeClassTemp = a.temp
        tempb: TypeClassTemp = b.temp
        if a.equiv(b):
            return True
        elif state == compatibleState.INVARIANT:
            return False
        elif state == compatibleState.COVARIANT:
            for index in range(len(tempa.baseclass)):
                if tempa.baseclass[index].temp.name == tempb.name:
                    return True
            return False
        elif state == compatibleState.CONTRAVARIANT:
            if isinstance(tempb, TypeClassTemp):
                return self.inheritance_check(tempa, tempb)
            else:
                return False
        else:
            return False

    def inheritance_check(self, tempa: TypeClassTemp, tempb: TypeTemp):
        if tempa == tempb:
            return True
        if not isinstance(tempb, TypeClassTemp):
            return False
        for index in range(len(tempb.baseclass)):
            if tempb.baseclass[index].temp.name == tempa.name:
                return True
            else:
                return self.inheritance_check(tempa, tempb.baseclass[index].temp)
        return False

    def TypeVarCom(self, a: TypeIns, b: TypeIns, state: compatibleState):
        for i in range(len(a.constraints)):
            return True


def type_consistent(left_ins, right_ins) -> bool:
    """check left_ins = right_ins safety"""
    res = TypeCompatible().TypeCompatible(left_ins, right_ins)
    return res


def is_any(tp):
    return str(tp) == "Any"


def is_none(tp):
    return str(tp) == "None"
