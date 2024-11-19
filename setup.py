from setuptools import setup, find_packages

setup(
    name='sprintify-navigation',
    version='0.1.0',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'PyQt6==6.2.0',  # Specify the required version
        'numpy',
        'matplotlib',
    ],
    author='Your Name',
    author_email='your.email@example.com',
    description='A library for navigation components',
    url='https://github.com/yourusername/navigation',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.6',
)