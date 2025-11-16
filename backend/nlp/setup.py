import glob
import os

import numpy
from Cython.Build import cythonize
from setuptools import setup, Extension

# Automatically find all .pyx files under src/lang3s/
ext_modules = []
for pyx_file in glob.glob("src/lang3s/**/*.pyx", recursive=True):
    module_name = pyx_file.replace("src/", "").replace("/", ".").replace(".pyx", "")
    # Ensure the directory exists where the .so will be written
    out_dir = os.path.dirname(pyx_file.replace("src/", ""))
    os.makedirs(out_dir, exist_ok=True)
    ext_modules.append(Extension(module_name, [pyx_file], include_dirs=[numpy.get_include()], language="c++"))

setup(
    ext_modules=cythonize(ext_modules, language_level="3"),
    package_dir={"": "src"},  # Tell setuptools your source root
)
