"""Run the updater's RPM %check suite in repository source checks too."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'bootchain_tests', Path(__file__).resolve().parents[1] /
    'packages/update-m1n1/test_bootchain.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def load_tests(loader, tests, pattern):
    return loader.loadTestsFromModule(module)
