
from qit.base.qitobject import QitObject, check_qit_object
from qit.base.exception import QitException
from qit.domains.generator import GeneratorIterator
from qit.base.int import Int

class Domain(QitObject):
    """ Basic class for domains """

    def __init__(self, type, iterator=None, generator=None, size=None, indexer=None):
        check_qit_object(type)
        assert type.is_type()
        self.type = type
        self.iterator = iterator
        self.generator = generator
        if size is not None:
            self.size = Int().value(size)
        else:
            self.size = None

        if iterator and self.size:
            iterator.size = self.size

        self.indexer = indexer

    def variable(self, name):
        """ Create variable of domain's type """
        return self.type.variable(name)

    def iterate(self):
        """ Return iterator of the domain """
        if self.iterator is None:
            raise QitException(
                    "Domain '{}' does not have an iterator".format(repr(self)))
        return self.iterator

    def is_iterable(self):
        """ Returns True if domain has an iterator """
        return self.iterator is not None

    def generate(self):
        """ Return generator of the domain """
        if self.generator is None:
            raise QitException(
                    "Domain '{}' does not have an generator".format(repr(self)))
        return GeneratorIterator(self.generator)

    def is_generable(self):
        """ Returns True if domain has an generator """
        return self.generator is not None

    def values(self, *values):
        """ Makes `Values` domain where self.type is used as underlying type"""
        return self.type.values(*values)

    def make_domain(self):
        return self

    def __mul__(self, other):
        return Product(self, other)

    def __add__(self, other):
        size1 = self.size
        size2 = other.size

        if size1 is None:
            size1 = 1
        if size2 is None:
            size2 = 1

        return Join((self, other), (size1, size2))

def check_domain(obj, have_iterator=False):
    if not isinstance(obj, Domain):
        raise QitException("{} is not domain".format(obj))

from qit.domains.product import Product
from qit.domains.join import Join
