from setuptools import setup, find_packages
import os
import re

# Read version from __init__.py
with open(os.path.join("subverses", "__init__.py"), encoding="utf-8") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = f.read().splitlines()

setup(
    name="subverses",
    version=version,
    author="Mariusz Woloszyn",
    author_email="emsi@users.noreply.github.com",
    description="A tool for translating and processing subtitles",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "subverses=subverses.main:main",
        ],
    },
)