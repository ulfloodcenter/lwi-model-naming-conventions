import setuptools

long_description = 'CARMA data harvesters'

setuptools.setup(
    name="lwi-model-naming-conventions",
    version="1.0.0",
    author="Brian Miles",
    author_email="brian.miles@louisiana.edu",
    description="Louisiana Watershed Initiative (LWI) model naming convention utilities",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        'base32-crockford'
    ],
    tests_require=[
    ],
    entry_points={
        'console_scripts': [
            'lwi-label-nhd-streams=lwi_model_naming_conventions.cmd.lwi_label_nhd_streams:main'
    ]},
    include_package_data=False,
    zip_safe=False
)
