import sys

from qit.build.builder import CppBuilder
from qit.base.utils import makedir_if_not_exists
from qit.base.exception import MissingFiles, ProgramCrashed

import tempfile
import os
import subprocess
import logging

from qit.build.report import ReportHandler

LOG = logging.getLogger("qit")

class CppEnv(object):

    def __init__(self, qit):
        self.qit = qit
        self.build_dir = os.path.abspath(qit.build_dir)
        self.compiler = "/usr/bin/g++"
        self.cpp_flags = ("-O3",
                          "-std=c++11",
                          "-march=native")
        self.report_callbacks = []

    def _handle_callback(self, tag, args):
        print((tag, args))
        sys.stdout.flush()
        for cb in self.report_callbacks:
            if cb[0] == tag:
                cb[1](tag, args)

    def run_collect(self, obj, args):
        self.check_all(obj)
        builder = CppBuilder(self)
        builder.build_collect(obj, args)
        return self.compile_builder(builder, obj.type)

    def get_file(self):
        makedir_if_not_exists(self.build_dir)
        if self.qit.debug:
            filename = os.path.join(self.build_dir, "debug.cpp")
            return open(filename, "w")
        else:
            return tempfile.NamedTemporaryFile(
                      mode="w",
                      prefix="qit-",
                      suffix=".cpp",
                      dir=self.build_dir,
                      delete=False)

    def compile_builder(self, builder, type):
        text = builder.writer.get_string()
        makedir_if_not_exists(self.build_dir)
        with self.get_file() as f:
            filename = f.name
            logging.debug("Creating file %s", filename)
            f.write(text)
        exe_filename = filename[:-4]
        args = (self.compiler, "-o", exe_filename, filename) + self.cpp_flags
        subprocess.check_call(args)
        output_fifo = exe_filename + "-output"
        report_fifo = exe_filename + "-report"

        return self.run_program(exe_filename, report_fifo, output_fifo, type)

    def run_program(self, exe_filename, report_fifo, output_fifo, type):
        report_handler = ReportHandler(report_fifo)

        try:
            os.mkfifo(report_fifo)
            os.mkfifo(output_fifo)

            args = (exe_filename, report_fifo, output_fifo)
            logging.debug("Running: %s", args)

            report_handler.start()
            report_handler.subscribe(lambda tag, args: self._handle_callback(tag, args))

            popen = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            with open(output_fifo, "rb") as f:
                result = type.read(f)

            stdout, stderr = popen.communicate()
            if popen.returncode != 0:
                raise ProgramCrashed(stdout, stderr)
            return result
        finally:
            os.unlink(report_fifo)
            os.unlink(output_fifo)
            report_handler.stop()

    def declarations(self, obj):
        builder = CppBuilder(self)
        return [builder.get_function_declaration(fn) for fn in obj.get_functions()
                if fn.is_external()]

    def get_function_filename(self, function):
        return os.path.abspath(
                os.path.join(self.qit.source_dir, function.filename))

    def get_function_filenames(self, functions):
        filenames = {}
        for function in functions:
            if function.is_external():
                filename = self.get_function_filename(function)
                if filename in filenames:
                    filenames[filename].append(function)
                else:
                    filenames[filename] = [function]
        return filenames

    def get_missing_function_filenames(self, functions):
        result = {}
        for filename, functions in \
                self.get_function_filenames(functions).items():
            if not os.path.isfile(filename):
                result[filename] = functions
        return result

    def set_report_callback(self, tag, callback):
        self.report_callbacks.append((tag, callback))

    def check_all(self, iterator):
        self.check_functions(iterator)

    def check_functions(self, iterator):
        functions = iterator.get_functions()
        missing_filenames = self.get_missing_function_filenames(functions)
        if not missing_filenames:
            return
        if self.qit.auto_create_files:
            self.create_source_files(iterator)
        builder = CppBuilder(self)
        filenames = list(sorted(missing_filenames.keys()))
        functions = sum(missing_filenames.values(), [])
        message = "File(s) {} are required because " \
                  "of the following function(s):\n {}\n".format(
                          ",".join(filenames),
                          ",".join(builder.get_function_declaration(f)
                                   for f in functions))
        raise MissingFiles(message, filenames)

    def create_source_files(self, obj):
        builder = CppBuilder(self)
        filenames = self.get_missing_function_filenames(obj.get_functions())
        for path, functions in filenames.items():
            logging.warning("Creating file %s", path)
            with open(path, "w") as f:
                for fn in functions:
                    f.write(builder.get_function_declaration(fn))
                    f.write("\n{\n\n}\n\n")
