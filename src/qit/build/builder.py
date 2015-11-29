
#import writer as writer

from qit.base.system import RuleType
from qit.build.writer import CppWriter
from qit.base.atom import sort_variables

class CppBuilder(object):

    def __init__(self, env):
        self.env = env
        self.writer = CppWriter()
        self.id_counter = 100
        self.declaration_keys = []
        self.autonames = []
        self.included_filenames = set()

    def get_autoname(self, key, prefix):
        for k, name in self.autonames:
            if key == k:
                return name
        name = self.new_id(prefix)
        self.autonames.append((key, name))
        return name

    def include_filename(self, filename):
        if filename in self.included_filenames:
            return
        self.included_filenames.add(filename)
        self.writer.line("#include \"{}\"", filename)

    def build_collect(self, iterator, args):
        self.write_header()
        iterator.declare_all(self)
        self.main_begin()
        self.init_fifo()
        self.init_variables(args)
        variable = iterator.make_iterator(self)
        element = self.make_element(iterator.output_type.basic_type)
        self.writer.line("while ({}.next({}))", variable, element)
        self.writer.block_begin()
        self.writer.line("qit::write(output, {});", element)
        self.writer.block_end()
        self.main_end()

    def make_sequence_from_iterator(self, iterator):
        result_variable = self.new_id("result")
        self.writer.line("std::vector<{} > {};",
                         iterator.output_type.get_element_type(self),
                         result_variable)
        iterator_variable = iterator.make_iterator(self)
        element = self.make_element(iterator.output_type.basic_type)
        self.writer.line("while ({}.next({}))", iterator_variable, element)
        self.writer.block_begin()
        self.writer.line("{}.push_back({});", result_variable, element)
        self.writer.block_end()
        return result_variable

    def make_element_from_iterator(self, iterator):
        iterator_variable = iterator.make_iterator(self)
        element = self.make_element(iterator.output_type.basic_type)
        self.writer.line("assert({}.next({}));", iterator_variable, element)
        return element

    def init_fifo(self):
        self.writer.line("assert(argc > 1);")
        self.writer.line("FILE *output = fopen(argv[1], \"w\");")

    def init_variables(self, args):
        for variable, value in sorted(args.items(), key=lambda v: v[0].name):
            self.writer.line("{} {}({});",
                             variable.type.get_element_type(self),
                             variable.name,
                             value.get_code(self))

    def write_header(self):
        self.writer.line("/*")
        self.writer.line("       QIT generated file")
        self.writer.line("*/")
        self.writer.emptyline()
        self.writer.line("#include <qit.h>")
        self.writer.emptyline()
        self.writer.line("#include <vector>")
        self.writer.line("#include <set>")
        self.writer.line("#include <iostream>")
        self.writer.line("#include <assert.h>")
        self.writer.line("#include <stdlib.h>")
        self.writer.line("#include <time.h>")

        self.writer.emptyline()
        self.writer.emptyline()

    def main_begin(self):
        self.writer.line("int main(int argc, char **argv)")
        self.writer.block_begin()
        self.writer.line("srand(time(NULL));")

    def main_end(self):
        self.writer.line("return 0;")
        self.writer.block_end();

    def new_id(self, prefix="v"):
        self.id_counter += 1
        return "{}{}".format(prefix, self.id_counter)

    def make_element(self, basic_type):
        variable = self.new_id()
        self.writer.line("{} {};",
                         basic_type.get_element_type(self),
                         variable)
        return variable

    def declare_type_alias(self, type):
        if self.check_declaration_key(type):
            return
        if type.name is not None:
            self.writer.line("typedef {} {};",
                             type.basic_type.get_element_type(self),
                             type.name)

    ## Method for multiple dispatch of base classes

    def get_generator_iterator(self, transformation):
        return "qit::GeneratorIterator<{} >" \
                .format(transformation.generator.get_generator_type(self))

    def make_basic_iterator(self, iterator, iterators=(), args=()):
        return self.make_iterator(iterator,
                                  tuple(c.make_iterator(self)
                                     for c in iterators) + args)

    def make_instance(self, type, prefix, args=()):
        variable = self.new_id(prefix)
        if args:
            self.writer.line("{} {}({});", type, variable, ",".join(args))
        else:
            self.writer.line("{} {};", type, variable)
        return variable

    def make_iterator(self, iterator, args):
        return self.make_instance(iterator.get_iterator_type(self),
                                  "i",
                                  args)

    def make_basic_generator(self, iterator, iterators=(), args=()):
        return self.make_generator(iterator,
                                  tuple(c.make_generator(self)
                                     for c in iterators) + args)

    def make_generator(self, iterator, args):
        return self.make_instance(iterator.get_generator_type(self),
                                  "i",
                                  args)

    def check_declaration_key(self, key):
        if key in self.declaration_keys:
            return True
        self.declaration_keys.append(key)
        self.writer.line("/* Declaration: {} */", key)
        return False

    # Int

    def get_int_type(self):
        return "int"

    def make_int_instance(self, value):
        assert isinstance(value, int)
        return str(value)

    # Bool

    def get_bool_type(self):
        return "bool"

    def make_bool_instance(self, value):
        assert isinstance(value, bool)
        return "true" if value else "false"

    # Range

    def get_range_iterator(self):
        return "qit::RangeIterator"

    def get_range_generator(self):
        return "qit::RangeGenerator"

    # Take

    def get_take_iterator(self, take):
        return "qit::TakeIterator<{} >" \
                .format(take.parent_iterator.get_iterator_type(self))

    # Sort

    def get_sort_iterator(self, sort):
        return "qit::SortIterator<{} >" \
                .format(sort.parent_iterator.get_iterator_type(self))

    # Map

    def get_map_iterator(self, map):
        return "qit::MapIterator<{}, {}, {} >" \
                .format(map.parent_iterator.get_iterator_type(self),
                        map.function.return_type.get_element_type(self),
                        self.get_autoname(map.function, "f"))

    # Filter

    def get_filter_iterator(self, filter):
        return "qit::FilterIterator<{}, {} >" \
                .format(filter.parent_iterator.get_iterator_type(self),
                        self.get_autoname(filter.function, "f"))

    # Product

    def make_product_instance(self, product, value):
        assert len(value) == len(product.names)
        args = ",".join(t.make_instance(self, v)
                        for t, v in zip(product.basic_types, value))
        return "{}({})".format(self.get_product_type(product), args)

    def get_product_type(self, product):
        if product.name is None:
            return self.get_autoname(product.basic_type, "Product")
        else:
            return product.name

    def get_product_iterator(self, iterator):
        type_name = self.get_product_type(iterator.output_type)
        return self.get_autoname(iterator, type_name + "Iterator")

    def get_product_generator(self, generator):
        type_name = self.get_product_type(generator.output_type)
        return self.get_autoname(generator, type_name + "Generator")

    def declare_product_class(self, product):
        if self.check_declaration_key(product):
            return
        product_type = self.get_product_type(product)
        self.writer.class_begin(product_type)
        self.writer.line("public:")

        ## Attributes
        for name, t in zip(product.names, product.types):
            self.writer.line("{} {};",
                             t.basic_type.get_element_type(self),
                             name)

        args = ",".join("const {} &{}".format(t.get_element_type(self), name)
                        for t, name in zip(product.basic_types, product.names))

        consts = ",".join("{0}({0})".format(name)
                        for name in product.names)

        self.writer.line("{}({}) : {} {{}}", product_type, args, consts)
        self.writer.line("{}() {{}}", product_type)

        # Write
        self.writer.line("void write(FILE *f) const")
        self.writer.block_begin()
        for name in product.names:
            self.writer.line("qit::write(f, {});", name)
        self.writer.block_end()

        # Operator <
        self.writer.line("bool operator <(const {} &other) const", product_type)
        self.writer.block_begin()
        for name in product.names:
            self.writer.if_begin("{0} < other.{0}", name)
            self.writer.line("return true;")
            self.writer.block_end()
            self.writer.if_begin("{0} == other.{0}", name)
        for name in product.names:
            self.writer.block_end()
        self.writer.line("return false;")
        self.writer.block_end()

        # Operator ==
        self.writer.line("bool operator ==(const {} &other) const", product_type)
        self.writer.block_begin()
        self.writer.line("return {};",
                         " && ".join("({0} == other.{0})".format(name)
                             for name in product.names))
        self.writer.block_end()
        self.writer.class_end()

        ## Stream
        """
        self.writer.line("std::ostream& operator<<(std::ostream& os, const {}& v)",
                  product_type)
        self.writer.block_begin()
        self.writer.line("os << \"{{\";")
        for i, name in enumerate(product.names):
            if i != 0:
                self.writer.line("os << \",\";")
            self.writer.line("os << v.{};", name)
        self.writer.line("return os << \"}}\";")
        self.writer.block_end()
        """


    def declare_product_iterator(self, iterator):
        if self.check_declaration_key(iterator):
            return

        product = iterator.output_type
        iterator_type = iterator.get_iterator_type(self)
        element_type = product.get_element_type(self)

        self.writer.class_begin(iterator_type)
        self.writer.line("public:")
        self.writer.line("typedef {} value_type;", element_type)

        names_iterators = list(zip(product.names, iterator.iterators))

        # Attributes
        for name, i in names_iterators:
            self.writer.line("{} {};",
                             i.get_iterator_type(self),
                             name)
        self.writer.line("bool _inited;")

        # Contructor
        args = [ "{} &{}".format(i.get_iterator_type(self), name)
                 for name, i in names_iterators ]
        constructors = [ "{0}({0})".format(name) for name in product.names ]
        constructors.append("_inited(false)")
        self.writer.line("{}({}) {} {}",
                         iterator_type,
                         ",".join(args),
                         ":" if constructors else "",
                         ",".join(constructors))
        self.writer.block_begin()
        self.writer.block_end()

        # Next
        self.writer.line("bool next({} &v)", element_type)
        self.writer.block_begin()
        self.writer.if_begin("_inited")
        for i, name in enumerate(product.names):
            self.writer.if_begin("{0}.next(v.{0})", name)
            self.writer.line("return true;")
            self.writer.block_end()
            if i != len(product.names) - 1:
                self.writer.line("{}.reset();", name)
                self.writer.line("{0}.next(v.{0});", name)
        self.writer.line("return false;")
        self.writer.else_begin()
        for name in product.names:
            self.writer.if_begin("!{0}.next(v.{0})", name)
            self.writer.line("return false;")
            self.writer.block_end()
        self.writer.line("_inited = true;")
        self.writer.line("return true;")
        self.writer.block_end()
        self.writer.block_end()

        # Reset
        self.writer.line("void reset()")
        self.writer.block_begin()
        self.writer.line("_inited = false;")
        for name in product.names:
            self.writer.line("{}.reset();", name)

        self.writer.block_end()

        self.writer.class_end()


    def declare_product_generator(self, generator):
        if self.check_declaration_key(generator):
            return

        product = generator.output_type
        generator_type = generator.get_generator_type(self)
        element_type = product.get_element_type(self)
        self.writer.class_begin(generator_type)
        self.writer.line("public:")
        self.writer.line("typedef {} value_type;", element_type)

        # Attributes
        names_generators = list(zip(product.names, generator.generators))
        for name, generator in names_generators:
            self.writer.line("{} {};",
                             generator.get_generator_type(self),
                             name)

        # Contructor
        args = [ "{} &{}".format(generator.get_generator_type(self), name)
                 for name, generator in names_generators ]
        constructors = [ "{0}({0})".format(name) for name in product.names ]
        self.writer.line("{}({}) {} {}",
                         generator_type,
                         ",".join(args),
                         ":" if constructors else "",
                         ",".join(constructors))
        self.writer.block_begin()
        self.writer.block_end()

        # Next
        self.writer.line("void generate({} &v)", element_type)
        self.writer.block_begin()
        for name in product.names:
            self.writer.line("{0}.generate(v.{0});", name)
        self.writer.block_end()

        self.writer.class_end()

    # Sequences

    def make_sequence_instance(self, sequence, value):
        basic_type = sequence.element_type.basic_type
        args = ",".join(basic_type.make_instance(self, v) for v in value)
        return "{{ {} }}".format(args)

    def get_sequence_iterator(self, iterator):
        return "qit::SequenceIterator<{} >".format(
            iterator.element_iterator.get_iterator_type(self))

    def get_sequence_generator(self, iterator):
        return "qit::SequenceGenerator<{} >".format(
            iterator.element_generator.get_generator_type(self))

    def get_sequence_type(self, sequence):
        return "std::vector<{} >".format(
            sequence.element_type.get_element_type(self))

    # Values

    def get_values_iterator_type(self, iterator):
        return self.get_autoname(iterator, "ValuesIterator")

    def get_values_generator_type(self, iterator):
        return self.get_autoname(iterator, "ValuesGenerator")

    def declare_values_iterator(self, iterator):
        if self.check_declaration_key(iterator):
            return
        output_type = iterator.output_type
        iterator_type = self.get_values_iterator_type(iterator)
        element_type = output_type.get_element_type(self)
        self.writer.class_begin(iterator_type)
        self.writer.line("public:")
        self.writer.line("typedef {} value_type;", element_type)
        variables = sort_variables(iterator.get_variables())
        args = ",".join("const {} &{}".format(v.type.get_element_type(self), v.name)
                        for v in variables)
        inits = ",".join(("counter(0)",) +
                         tuple("{0}({0})".format(v.name) for v in variables))
        self.writer.line("{}({}) : {} {{}}", iterator_type, args, inits)

        self.writer.line("bool next(value_type &out)")
        self.writer.block_begin()
        self.writer.line("switch(counter)")
        self.writer.block_begin()
        for i, value in enumerate(iterator.values):
            self.writer.line("case {}:", i)
            self.writer.line("out = {};", value.get_code(self))
            self.writer.line("counter++;")
            self.writer.line("return true;")
        self.writer.line("default:")
        self.writer.line("return false;")
        self.writer.block_end()
        self.writer.block_end()

        self.writer.line("void reset()")
        self.writer.block_begin()
        self.writer.line("counter = 0;")
        self.writer.block_end()

        self.writer.line("protected:")
        self.writer.line("int counter;")
        for v in variables:
            self.writer.line(
                    "const {} &{};", v.type.get_element_type(self), v.name)
        self.writer.class_end()

    def declare_values_generator(self, generator):
        if self.check_declaration_key(generator):
            return
        output_type = generator.output_type
        generator_type = self.get_values_generator_type(generator)
        element_type = output_type.get_element_type(self)
        self.writer.class_begin(generator_type)
        self.writer.line("public:")
        self.writer.line("typedef {} value_type;", element_type)

        self.writer.line("void generate(value_type &out)")
        self.writer.block_begin()
        self.writer.line("switch(rand() % {})", len(generator.values))
        self.writer.block_begin()
        for i, value in enumerate(generator.values):
            self.writer.line("case {}:", i)
            self.writer.line("out = {};", value.get_code(self))
            self.writer.line("return;")
        self.writer.line("default:")
        self.writer.line("assert(0);")
        self.writer.block_end()
        self.writer.block_end()

        self.writer.class_end()

    # Function

    def get_function_call_code(self, function_call):
        function = function_call.function
        function_name = self.get_autoname(function, "function")
        variables = ",".join(v.get_code(self) for v in function.variables)
        args = ",".join(e.get_code(self) for e in function_call.args)
        return "{}({})({})".format(function_name, variables, args)

    def make_functor(self, function):
        return self.make_instance(self.get_autoname(function, "function"),
                                  "f",
                                  [ v.get_code(self) for v in function.variables ])

    def declare_function(self, function):
        if self.check_declaration_key((function, "function")):
            return

        if function.is_external():
            self.include_filename(self.env.get_function_filename(function))

        function_name = self.get_autoname(function, "function")
        self.writer.class_begin(function_name)

        if function.variables and function.is_external():
            self.writer.line("struct Env {{")
            self.writer.indent_push()
            self.writer.line("Env({}) : {} {{}}",
                             ",".join("const {} &{}".format(v.type.get_element_type(self),
                                                      v.name)
                                      for v in function.variables),
                             ",".join("{0}({0})".format(v.name)
                                      for v in function.variables)
                             )

            for variable in function.variables:
                self.writer.line("const {} &{};",
                             variable.type.get_element_type(self),
                             variable.name)

            self.writer.indent_pop()
            self.writer.line("}};")

        self.writer.line("public:")

        if function.variables:
            self.writer.line("{}({}) : {} {{}}",
                             function_name,
                             ",".join("const {} &{}".format(v.type.get_element_type(self),
                                                      v.name)
                                      for v in function.variables),
                             ",".join("{0}({0})".format(v.name)
                                      for v in function.variables))

        params = [ "const {} &{}".format(c.get_element_type(self), name)
                   for c, name in function.params ]
        self.writer.line("{} operator()({})",
                         function.return_type.get_element_type(self),
                         ",".join(params))
        self.writer.block_begin()
        function.write_code(self)
        self.writer.block_end()

        for variable in function.variables:
            self.writer.line("const {} &{};",
                             variable.type.get_element_type(self),
                             variable.name)

        self.writer.class_end()

    def write_function_from_iterator(self, function, sequence):
        if sequence:
            variable = self.make_sequence_from_iterator(function.iterator)
        else:
            variable = self.make_element_from_iterator(function.iterator)
        self.writer.line("return {};", variable)

    def write_function_inline_code(self, function):
        self.writer.text(function.inline_code)

    def write_function_external_call(self, function):
        if function.variables:
            self.writer.line("Env env({0});", ",".join([var.name for var in function.variables]))

        call = ""

        if function.return_type is not None:
            call += "return "

        call += function.name

        if function.variables:
            call += "<Env>(env, "
        else:
            call += "("

        call += ", ".join([param[1] for param in function.params])  # param names

        self.writer.line(call + ");")

    def get_function_declaration(self, function):
        declaration = "template <typename Env>\n"

        if function.return_type is not None:
            declaration += function.return_type.get_element_type(self) + " "
        else:
            declaration += "void "

        declaration += function.name + "(Env env, "
        declaration += ", ".join([ "const {} &{}".format(c.get_element_type(self), name)
                   for c, name in function.params ])  # param names
        return declaration + ")"


    # System

    def get_system_iterator_type(self, iterator):
        return self.get_autoname(iterator, "SystemIterator")

    def declare_system_iterator(self, iterator):
        if self.check_declaration_key(iterator):
           return
        system = iterator.system
        iterator_type = self.get_system_iterator_type(iterator)
        element_iterator_type = system.initial_states_iterator.get_iterator_type(self)
        element_type = system.state_type.get_element_type(self)

        self.writer.class_begin(iterator_type)
        self.writer.line("public:")
        self.writer.line("typedef {} value_type;", element_type)
        self.writer.line("{}(const {} &iterator) "
                         ": inited(false), rule(0), depth(0), "
                         "queue2_emit(0), iterator(iterator) {{}}",
                         iterator_type, element_iterator_type)

        self.writer.line("bool next(value_type &out)")
        self.writer.block_begin()
        self.writer.if_begin("queue2_emit")
        self.writer.line("out = queue2[queue2.size() - queue2_emit--];")
        self.writer.line("return true;")
        self.writer.block_end();
        self.writer.if_begin("!inited")
        self.writer.if_begin("iterator.next(out)")
        self.writer.line("queue1.push_back(out);")
        self.writer.line("discovered.insert(out);")
        self.writer.line("return true;")
        self.writer.block_end()
        self.writer.line("inited = true;")
        self.writer.if_begin("0 == {}", iterator.depth.get_code(self))
        self.writer.line("return false;")
        self.writer.block_end()
        self.writer.block_end()

        self.writer.line("for(;;)")
        self.writer.block_begin()
        self.writer.if_begin("queue1.size() == 0")
        self.writer.if_begin("queue2.size() == 0")
        self.writer.line("return false;")
        self.writer.block_end()
        self.writer.line("depth++;")
        self.writer.if_begin("depth >= {}", iterator.depth.get_code(self))
        self.writer.line("return false;")
        self.writer.block_end()
        self.writer.line("std::swap(queue1, queue2);")
        self.writer.block_end()
        self.writer.block_begin()
        self.writer.line("switch(rule)")
        self.writer.block_begin()
        for i, rule in enumerate(system.rules):
            self.writer.line("case {}:", i)
            self.writer.block_begin()
            self.writer.line("{} rule_fn;", self.get_autoname(rule, "f"), i)
            if system.get_rule_type(rule) == RuleType.one_to_one:
                self.writer.line("rule++;")
                self.writer.line("out = rule_fn(queue1.back());", element_type)
                self.writer.if_begin("discovered.find(out) == discovered.end()")
                self.writer.line("discovered.insert(out);")
                self.writer.line("queue2.push_back(out);")
                self.writer.line("return true;")
                self.writer.line("// no break!")
                self.writer.block_end()
            else:
                assert system.get_rule_type(rule) == RuleType.one_to_many
                self.writer.line("rule++;")
                self.writer.line("std::vector<{} > v;", element_type)
                self.writer.line("v = rule_fn(queue1.back());", element_type)
                self.writer.line("size_t found = 0;")
                self.writer.line("for (const auto &i : v)")
                self.writer.block_begin()
                self.writer.if_begin("discovered.find(i) == discovered.end()")
                self.writer.line("discovered.insert(i);")
                self.writer.line("queue2.push_back(i);")
                self.writer.line("found++;")
                self.writer.block_end()
                self.writer.block_end()
                self.writer.if_begin("found")
                self.writer.line("queue2_emit = found - 1;")
                self.writer.line("out = queue2[queue2.size() - found];")
                self.writer.line("return true;")
                self.writer.block_end()
            self.writer.block_end()
        self.writer.line("default: break;")
        self.writer.block_end()
        self.writer.line("rule = 0;")
        self.writer.line("queue2_emit = 0;")
        self.writer.line("queue1.pop_back();")
        self.writer.block_end()
        self.writer.block_end()
        self.writer.block_end()

        self.writer.line("void reset()")
        self.writer.block_begin()
        self.writer.line("inited = false;")
        self.writer.line("rule = 0;")
        self.writer.line("depth = 0;")
        self.writer.line("queue2_emit = 0;")
        self.writer.line("discovered.clear();")
        self.writer.line("queue1.clear();")
        self.writer.line("queue2.clear();")
        self.writer.line("iterator.reset();")
        self.writer.block_end()

        self.writer.line("protected:")
        self.writer.line("bool inited;")
        self.writer.line("int rule;")
        self.writer.line("int depth;")
        self.writer.line("std::vector<{} > queue1;", element_type)
        self.writer.line("std::vector<{} > queue2;", element_type)
        self.writer.line("std::set<{} > discovered;", element_type)
        self.writer.line("size_t queue2_emit;", element_type)
        self.writer.line("{} iterator;", element_iterator_type)
        self.writer.class_end()
