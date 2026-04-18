from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="erpnext_pax8",
    version="1.0.0",
    description="Pax8 integration for ERPNext — import monthly invoices as Purchase and Sales Invoices",
    author="IPCONNEX Services",
    author_email="dev@ipconnex.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
