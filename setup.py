import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md"), "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name='sprintify-navigation',
    version=os.environ.get("RELEASE_VERSION", "1.0.6"),
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'PySide6==6.7.1',  # Specify the required version
        'numpy',
    ],
    author='Sami Spjuth',
    author_email='sami@spjuth.org',
    description='A navigation widget  based on PySide6',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/sspjuth/sprintify',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.6',
)