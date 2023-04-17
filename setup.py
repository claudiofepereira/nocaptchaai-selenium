"""nocaptchaai-selenium

nocaptchaai-selenium is a Python library that uses Selenium and NoCaptchaAI.com API to solve hCaptcha challenges.

An example of how to use this library can be found in examples/nopecha_solver_example.py.

"""

from setuptools import setup, find_packages

DOCLINES = (__doc__ or "").split("\n")

setup(
    name="nocaptchaai_selenium",
    version="0.0.1",
    description="Selenium implementation of the NoCaptchaAI API",
    long_description="\n".join(DOCLINES[2:]),
    url="https://github.com/claudiofepereira/nocaptchaai-playwright",
    author="Cláudio Pereira",
    license="MIT",
    packages=["nocaptchaai_selenium"],
    install_requires=[
        "selenium",
        "requests",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
