"""Setup script — run: pip install -e ."""
from setuptools import setup

setup(
    name="agentbridge-admin",
    py_modules=["bridge_client"],
    install_requires=["requests"],
)
