#!/usr/bin/env python3


from setuptools import find_packages, setup

# Read package description
with open("README.md", "r") as f:
    long_description = f.read()


# Read common requirements
requirements = []
with open("requirements.txt") as fp:
    for line in fp:
        requirements.append(line.strip())


setup(
    name="argusloop",
    version="0.0.1",
    packages=["argusloop"],
    description="High-fidelity simulator for the development of the Argus flight software suite and GNC algorithms.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cmu-spacecraft-design-build-fly-2023/argus-simulator",
    author_email="isow@andrew.cmu.edu",
    license="MIT",
    install_requires=requirements,
    include_package_data=True,
    python_requires=">=3.8.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
