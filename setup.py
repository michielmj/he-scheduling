from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
import os

# Define the Cython extension module
extensions = [
    Extension(
        name="he_scheduling.services.single_resource_scheduler",
        sources=["he_scheduling/services/single_resource_scheduler.pyx"],
        language="c++",
        extra_compile_args=["-std=c++11"],
    ),
]

setup(
    name="he_scheduling",
    version="0.5.1",
    description="A FastAPI scheduling microservice",
    author="Michiel Jansen",
    author_email="michiel.mj@gmail.com",
    url="https://github.com/michielmj/he-scheduling",
    packages=find_packages(),
    include_package_data=True,
    ext_modules=cythonize(extensions),
    zip_safe=False,
    install_requires=[
        "fastapi>=0.115.0,<0.116.0",
        "uvicorn>=0.30.0,<0.31.0",
        "ortools>=9.11.4210,<9.12.0",
        "pydantic>=2.0.0,<3.0.0",
        "celery>=5.4.0,<5.5.0",
        "pydantic-settings>=2.6.1,<2.7.0",
        "sqlalchemy>=2.0.36,<2.1.0",
        "psycopg2-binary>=2.9.10,<2.10.0",
        "flower>=2.0.1,<2.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.3,<8.4.0",
            "black>=24.8.0,<25.0.0",
            "flake8>=7.1.1,<7.2.0",
            "httpx>=0.27.2,<0.28.0",
            "mypy>=1.11.2,<1.12.0",
            "setuptools>=75.1.0,<76.0.0",
            "cython>=3.0.11,<3.1.0",
            "pytest-mock>=3.14.0,<3.15.0",
            "pika>=1.3.2,<1.4.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "start-fastapi-server=he_scheduling.main:run",
        ],
    },
)
