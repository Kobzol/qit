
from qit.base.int import Int
from qit.base.vector import Vector
from qit.base.struct import Struct, KeyValue
from qit.base.variable import Variable
from qit.domains.iterator import Iterator


class Transformation(Iterator):
    pass


class TakeTransformation(Transformation):

    def __init__(self, iterator, count):
        count = Int().value(count)
        itype = Struct(Int(), iterator.itype)
        super().__init__(itype, iterator.element_type)

        self.reset_fn.code("""
            iter.v0 = {{count}};
            {{reset_fn}}(iter.v1);
        """, count=count, reset_fn=iterator.reset_fn)

        self.next_fn.code("""
            if (iter.v0 <= 1) {
                iter.v0 = 0;
                return;
            }
            iter.v0--;
            {{next_fn}}(iter.v1);
        """, next_fn=iterator.next_fn, itype=itype)

        self.is_valid_fn.code("""
            if (iter.v0 <= 0) {
                return false;
            } else {
                return {{is_valid_fn}}(iter.v1);
            }
        """, is_valid_fn=iterator.is_valid_fn)

        self.value_fn.code("return {{value_fn}}(iter.v1);",
                value_fn=iterator.value_fn)


class MapTransformation(Transformation):

    def __init__(self, iterator, function, keyval):
        if keyval:
            element_type = KeyValue(iterator.element_type,
                                    function.return_type)
        else:
            element_type = function.return_type
        super().__init__(iterator.itype,
                         element_type)
        assert function.return_type is not None
        # TODO: Check compatibility of function and valid return type
        self.reset_fn = iterator.reset_fn
        self.next_fn = iterator.next_fn
        self.is_valid_fn = iterator.is_valid_fn
        x = Variable(iterator.itype, "_x")
        if keyval:
            self.value_fn.code("""
                const auto &value = {{value_fn}}(iter);
                return { value, {{function}}(value) };
            """, value_fn=iterator.value_fn, function=function)
        else:
            self.value_fn = function(iterator.value_fn(x)).make_function((x,))


class SortTransformation(Transformation):

    def __init__(self, iterator, ascending=True):
        itype = Int() * Vector(iterator.element_type)
        super().__init__(itype, iterator.element_type)

        # Since iter.v1 is never changed, we use it to detect
        # if reset_fn is called for the first time,
        # or if reset is used to restart existing iterator
        self.reset_fn.code("""
            iter.v0 = 0;
            if (iter.v1.size() == 0) {
                iter.v1 = {{vector}};
                std::sort(iter.v1.begin(), iter.v1.end());
            }
        """, vector=iterator.to_vector())
        self.next_fn.code("iter.v0++;")
        self.is_valid_fn.code("return iter.v0 < iter.v1.size();")
        self.value_fn.code("return iter.v1[iter.v0];")


class FilterTransformation(Transformation):

    def __init__(self, iterator, function):
        super().__init__(iterator.itype, iterator.element_type)
        self.reset_fn.code("""
            {{reset_fn}}(iter);
            for(;;) {
                if (!{{is_valid_fn}}(iter)) {
                    return;
                }
                if ({{function}}({{value_fn}}(iter))) {
                    return; // We have found a value
                }
                {{next_fn}}(iter);
            }
            """,
            reset_fn=iterator.reset_fn,
            next_fn=iterator.next_fn,
            is_valid_fn=iterator.is_valid_fn,
            value_fn=iterator.value_fn,
            function=function)
        self.is_valid_fn = iterator.is_valid_fn
        self.value_fn = iterator.value_fn
        self.next_fn.code("""
            {{next_fn}}(iter);
            for(;;) {
                if (!{{is_valid_fn}}(iter)) {
                    return; // Iterator is empty
                }
                if ({{function}}({{value_fn}}(iter))) {
                    return; // We have found a value
                }
                {{next_fn}}(iter);
            }
            """,
            next_fn=iterator.next_fn,
            is_valid_fn=iterator.is_valid_fn,
            value_fn=iterator.value_fn,
            function=function)


class ShowTransformation(Transformation):

    def __init__(self, iterator, progress):
        progress = Int().value(progress)
        itype = Struct(Int(), iterator.itype)
        super().__init__(itype, iterator.element_type)

        self.reset_fn.code("""
            iter.v0 = 0;
            {{reset_fn}}(iter.v1);
        """, reset_fn=iterator.reset_fn)

        self.next_fn.code("""
            iter.v0++;

            if (iter.v0 % {{progress}} == 0)
            {
                qit_report(\"PROGRESS_UPDATE {{progress}}\");
            }

            {{next_fn}}(iter.v1);
        """, next_fn=iterator.next_fn, itype=itype, progress=progress)

        self.is_valid_fn.code("""
            return {{is_valid_fn}}(iter.v1);
        """, is_valid_fn=iterator.is_valid_fn)

        self.value_fn.code("return {{value_fn}}(iter.v1);",
                value_fn=iterator.value_fn)