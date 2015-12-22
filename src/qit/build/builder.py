
from qit.build.writer import CppWriter
from qit.base.utils import sorted_variables
import jinja2

class CppBuilder(object):

    def __init__(self, env):
        self.env = env
        self.writer = CppWriter()
        self.id_counter = 100
        self.declaration_keys = []
        self.autonames = {}
        self.included_filenames = set()

    def get_autoname(self, obj):
        name = self.autonames.get(obj)
        if name is not None:
            return name
        name = self.new_id(obj.autoname_prefix)
        self.autonames[obj] = name
        return name

    def get_report_file_name(self):
        return "report_file"

    def include_filename(self, filename):
        if filename in self.included_filenames:
            return
        self.included_filenames.add(filename)
        self.writer.line("#include \"{}\"", filename)

    def build_collect(self, obj, args):
        write_function = obj.type.write_function
        self.write_header()
        obj.declare_all(self)
        write_function.declare_all(self)
        self.main_begin()
        self.init_fifo()
        self.init_variables(args)
        self.writer.line(
             "{}(output, {});", write_function.build(self), obj.build(self))
        self.writer.line("fclose(output);")
        self.report_call("hey", "arg")
        self.writer.line("fclose({});".format(self.get_report_file_name()))
        self.main_end()

    def write_expression_into_variable(self, expr):
        variable = self.new_id()
        self.writer.line("{} {} = {};",
                         expr.type.build(self),
                         variable,
                         expr.build(self))
        return variable

    def build_object(self, type, args):
        args = ",".join(a.build(self) for a in args)
        return "{}({})".format(type.build(self), args)

    def write_iterator_write_method(self):
        self.writer.line("QIT_ITERATOR_WRITE_METHOD")

    def make_sequence_from_iterator(self, iterator):
        result_variable = self.new_id("result")
        self.writer.line("{} {};",
                         iterator.output_type.build(self),
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
        self.writer.line("assert(argc > 2);")
        self.writer.line("report_file = fopen(argv[1], \"w\");")
        self.writer.line("FILE *output = fopen(argv[2], \"w\");")

    def init_variables(self, args):
        for variable, value in sorted(args.items(), key=lambda v: v[0].name):
            self.writer.line("{} {}({});",
                             variable.type.build(self),
                             variable.name,
                             value.build(self))

    def write_header(self):
        self.writer.line("/*")
        self.writer.line("       QIT generated file")
        self.writer.line("*/")
        self.writer.emptyline()
        self.writer.line("#include <vector>")
        self.writer.line("#include <set>")
        self.writer.line("#include <map>")
        self.writer.line("#include <iostream>")
        self.writer.line("#include <assert.h>")
        self.writer.line("#include <stdlib.h>")
        self.writer.line("#include <time.h>")
        self.writer.line("#include <algorithm>")
        self.writer.line("#include <random>")
        self.writer.emptyline()
        self.writer.line("std::default_random_engine QIT_GENERATOR(time(nullptr));")
        self.writer.line("typedef int32_t qint;")
        self.writer.emptyline()
        self.writer.line("FILE *{};".format(self.get_report_file_name()))
        self.report_function_body()
        self.writer.emptyline()
        self.writer.emptyline()

    def main_begin(self):
        self.writer.line("int main(int argc, char **argv)")
        self.writer.block_begin()

    def main_end(self):
        self.writer.line("return 0;")
        self.writer.block_end()

    def new_id(self, prefix="v"):
        self.id_counter += 1
        return "{}{}".format(prefix, self.id_counter)

    ## Method for multiple dispatch of base classes

    def check_declaration_key(self, key):
        if key in self.declaration_keys:
            return True
        self.declaration_keys.append(key)
        self.writer.line("/* Declaration: {} */", key)
        return False

    # Report
    def report_function_body(self):
        report_file = self.get_report_file_name()

        self.writer.line("void qit_report(std::string tag, std::string arg = \"\")")
        self.writer.line("{{")
        self.writer.indent_push()
        self.writer.line("fprintf({}, \"%s %s\\n\", tag.c_str(), arg.c_str());".format(report_file))
        self.writer.indent_pop()
        self.writer.line("}}")

    def report_call(self, tag, arg=""):
        self.writer.line("qit_report(\"{}\", \"{}\");".format(str(tag), str(arg)))

    # Struct

    def declare_struct(self, struct):
        if self.check_declaration_key(struct):
            return
        struct_type = struct.build(self)
        self.writer.class_begin(struct_type)
        self.writer.line("public:")

        ## Attributes
        for name, t in zip(struct.names, struct.types):
            self.writer.line("{} {};",
                             t.build(self),
                             name)

        if struct.names:
            params = ",".join(t.build_param(self, name)
                            for t, name in zip(struct.types, struct.names))

            consts = ": " + ",".join("{0}({0})".format(name)
                            for name in struct.names)
            self.writer.line("{}({}) {} {{}}", struct_type, params, consts)
        self.writer.line("{}() {{}}", struct_type)

        # Operator <
        self.writer.line("bool operator <(const {} &other) const", struct_type)
        self.writer.block_begin()
        for name in struct.names:
            self.writer.if_begin("{0} < other.{0}", name)
            self.writer.line("return true;")
            self.writer.block_end()
            self.writer.if_begin("{0} == other.{0}", name)
        for name in struct.names:
            self.writer.block_end()
        self.writer.line("return false;")
        self.writer.block_end()

        # Operator ==
        self.writer.line("bool operator ==(const {} &other) const", struct_type)
        self.writer.block_begin()
        if struct.names:
            self.writer.line("return {};",
                             " && ".join("({0} == other.{0})".format(name)
                                 for name in struct.names))
        else:
            self.writer.line("return true;")
        self.writer.block_end()
        self.writer.class_end()

    # Function

    def build_function_call(self, function_call):
        functor = self.build_functor(function_call.function)
        args = ",".join(e.build(self) for e in function_call.args)
        return "{}({})".format(functor, args)

    def build_functor(self, function, prefix=""):
        function_name = self.get_autoname(function)
        variables = sorted_variables(function.get_variables())
        if variables:
            v = ",".join(prefix + v.build(self) for v in variables)
            return "({}({}))".format(function_name, v)
        else:
            return "{}()".format(function_name)

    def declare_function(self, function):
        if self.check_declaration_key(function):
            return

        if function.is_external():
            self.include_filename(self.env.get_function_filename(function))

        function_name = self.get_autoname(function)
        self.writer.class_begin(function_name)
        self.writer.line("public:")

        variables = function.get_variables()
        if variables:
            variables = sorted_variables(variables)
            self.writer.line("{}({}) : {} {{}}",
                             function_name,
                             ",".join("const {} &{}".format(v.type.build(self),
                                                      v.name)
                                      for v in variables),
                             ",".join("{0}({0})".format(v.name)
                                      for v in variables))
        self.writer.line("{}", function.build_declaration(self, "operator()"))
        self.writer.block_begin()
        function.write_code(self)
        self.writer.block_end()

        for variable in variables:
            self.writer.line("const {} &{};",
                             variable.type.build(self),
                             variable.name);

        self.writer.class_end()

    def write_return_expression(self, expression):
        self.writer.line("return {};", expression.build(self))

    def write_code(self, inline_code, inline_code_vars):
        if isinstance(inline_code_vars, dict):
            inline_code_vars = tuple(inline_code_vars.items())
        d = {}
        for name, obj in inline_code_vars:
            if name.startswith("_"):
                d[name] = obj
            else:
                d[name] = obj.build(self)
        template = jinja2.Template(inline_code)
        template.globals.update(b=lambda obj: obj.build(self))
        template.globals["_builder"] = self
        self.writer.text(template.render(d))

    def write_function_external_call(self, function):
        call = ""

        if function.return_type is not None:
            call += "return "

        call += function.name + "("
        call += ", ".join([param.name for param in function.params])  # param names

        self.writer.line(call + ");")

    def get_function_declaration(self, function):
        args = ", ".join(p.type.build_param(self, p.name, p.const)
                         for p in function.params)
        if function.return_type is not None:
            return_type = function.return_type.build(self)
        else:
            return_type = "void"
        return "{} {}({})".format(return_type, function.name, args)
