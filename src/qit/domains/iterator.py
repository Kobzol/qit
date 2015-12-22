
from qit.base.function import Function
from qit.base.bool import Bool
from qit.base.vector import Vector
from qit.base.qitobject import QitObject
from qit.base.union import Maybe

class Iterator(QitObject):

    def __init__(self, itype, element_type):
        self.itype = itype
        self.element_type = element_type
        self.reset_fn = Function().takes(itype, "iter", const=False)
        self.next_fn = Function().takes(itype, "iter", const=False)
        self.is_valid_fn = Function().takes(itype, "iter").returns(Bool())
        self.value_fn = Function().takes(itype, "iter").returns(element_type)

    @property
    def childs(self):
        return (self.itype,
                self.reset_fn,
                self.next_fn,
                self.is_valid_fn,
                self.value_fn)

    # Transformations

    def take(self, count):
        return TakeTransformation(self, count)

    def map(self, function):
        return MapTransformation(self, function, False)

    def map_kv(self, function):
        return MapTransformation(self, function, True)

    def sort(self, asceding=True):
        return SortTransformation(self, asceding)

    def filter(self, function):
        return FilterTransformation(self, function)

    def show(self, progress):
        return ShowTransformation(self, progress)

    # To single value

    def reduce(self, function):
        f = Function(returns=self.element_type)
        f.code(
            """
                {{itype}} iterator;
                {{reset_fn}}(iterator);
                if (!({{is_valid_fn}}(iterator))) {
                    fprintf(stderr, "Reduce on empty iterator\\n");
                    exit(1);
                }
                {{type}} value = {{value_fn}}(iterator);
                {{next_fn}}(iterator);
                while({{is_valid_fn}}(iterator)) {
                    value = {{function}}(value, {{value_fn}}(iterator));
                    {{next_fn}}(iterator);
                }
                return value;
            """,
            function=function,
            itype=self.itype,
            type=self.element_type,
            value_fn=self.value_fn,
            next_fn=self.next_fn,
            reset_fn=self.reset_fn,
            is_valid_fn=self.is_valid_fn)
        return f()

    def is_empty(self):
        f = Function(returns=Bool())
        f.code(
            """
                {{itype}} iterator;
                {{reset_fn}}(iterator);
                return !({{is_valid_fn}}(iterator));
            """,
            itype=self.itype,
            reset_fn=self.reset_fn,
            is_valid_fn=self.is_valid_fn)
        return f()

    def is_nonempty(self):
        f = Function(returns=Bool())
        f.code(
            """
                {{itype}} iterator;
                {{reset_fn}}(iterator);
                return {{is_valid_fn}}(iterator);
            """,
            itype=self.itype,
            reset_fn=self.reset_fn,
            is_valid_fn=self.is_valid_fn)
        return f()

    def first(self, if_empty_value=None):
        f = Function(returns=self.element_type)
        if if_empty_value is None:
            f.code(
                """
                    {{itype}} iterator;
                    {{reset_fn}}(iterator);
                    assert ({{is_valid_fn}}(iterator));
                    return {{value_fn}}(iterator);
                """,
                itype=self.itype,
                reset_fn=self.reset_fn,
                is_valid_fn=self.is_valid_fn,
                value_fn=self.value_fn)
        else:
            f.code(
                """
                    {{itype}} iterator;
                    {{reset_fn}}(iterator);
                    if ({{is_valid_fn}}(iterator)) {
                        return {{value_fn}}(iterator);
                    } else {
                        return {{if_empty_value}};
                    }
                """,
                itype=self.itype,
                reset_fn=self.reset_fn,
                is_valid_fn=self.is_valid_fn,
                value_fn=self.value_fn,
                if_empty_value=self.element_type.value(if_empty_value))
        return f()

    def first_maybe(self):
        maybe = Maybe(self.element_type)
        f = Function(returns=maybe)
        f.code(
            """
                {{itype}} iterator;
                {{reset_fn}}(iterator);
                if ({{is_valid_fn}}(iterator)) {
                    return {{maybe}}(Just, {{value_fn}}(iterator));
                } else {
                    return {{maybe}}(Nothing);
                }
            """,
            itype=self.itype,
            reset_fn=self.reset_fn,
            is_valid_fn=self.is_valid_fn,
            value_fn=self.value_fn,
            maybe=maybe)
        return f()

    def to_vector(self):
        vector = Vector(self.element_type)
        f = Function(returns=vector)
        f.code(
            """
                {{vector}} output;
                {{itype}} iterator;
                {{reset_fn}}(iterator);
                while({{is_valid_fn}}(iterator)) {
                    output.push_back({{value_fn}}(iterator));
                    {{next_fn}}(iterator);
                };
                return output;
            """,
            itype=self.itype,
            reset_fn=self.reset_fn,
            next_fn=self.next_fn,
            is_valid_fn=self.is_valid_fn,
            value_fn=self.value_fn,
            vector=vector)
        return f()

    def make_function(self, *args, **kw):
        return self.get_expression().make_function(*args, **kw)

    def get_expression(self):
        return self.to_vector()


# To broke import cycle, we import following packages at the end
from qit.domains.transformation import TakeTransformation, FilterTransformation, ShowTransformation
from qit.domains.transformation import MapTransformation
from qit.domains.transformation import SortTransformation
