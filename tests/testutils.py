import os
import sys

TEST_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.dirname(TEST_DIR)
SRC_DIR = os.path.join(ROOT_DIR, "src")

def init():
    if SRC_DIR not in sys.path:
        sys.path.append(SRC_DIR)

def Qit():
    import qit
    return qit.Qit(debug=True)
