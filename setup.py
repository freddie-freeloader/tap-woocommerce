"""A setuptools based setup module.
See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
Modified by Madoshakalaka@Github (dependency links added)
"""

from setuptools import setup, find_packages
from os import path

from io import open

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="tap-woocommerce",
    version="0.3.1",
    long_description=long_description,  # Optional
    long_description_content_type="text/markdown",  # Optional (see note above)
    packages=find_packages(exclude=["contrib", "docs", "tests"]),  # Required
    python_requires=">=3.8, <4",
    install_requires=[
        "attrs==20.2.0",
        "backoff==1.8.0; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3'",
        "certifi==2020.6.20",
        "chardet==3.0.4",
        "ciso8601==2.1.3",
        "idna==2.10; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3'",
        "jsonschema==2.6.0",
        "ordereddict==1.1",
        "python-dateutil==2.8.1",
        "pytz==2018.4",
        "requests==2.24.0; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3, 3.4'",
        "simplejson==3.11.1",
        "singer-python==5.9.0",
        "six==1.15.0; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3'",
        "urllib3==1.25.10; python_version >= '2.7' and python_version not in '3.0, 3.1, 3.2, 3.3, 3.4' and python_version < '4'",
    ],
    extras_require={"dev": []},
    dependency_links=[
        "git+https://github.com/freddie-freeloader/wc-api-python.git@c4e7cf6bcb02daafc5ba61b1d5dbc70b928919f8#egg=woocommerce"
    ],
)
