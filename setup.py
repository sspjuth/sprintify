from setuptools import setup, find_packages

setup(
    name='sprintify-navigation',
    version='1.0.5',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'PySide6==6.7.1',  # Specify the required version
        'numpy',
    ],
    author='Sami Spjuth',
    author_email='sami@spjuth.org',
    description='A navigation widget  based on PySide6',
    url='https://github.com/sspjuth/navigation',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.6',
)