from setuptools import setup, find_packages

setup(
    name='netbox-fiber-panel-utilization',
    version='1.0.0',
    description='A read-only NetBox plugin for fiber patch panel utilization tracking',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Marshall Hollis',
    author_email='hollisma@cec.sc.edu',
    license='Apache 2.0',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'netbox_fiber_panel_utilization': [
            'templates/**/*.html',
            'static/**/*.css',
            'static/**/*.js',
        ],
    },
    python_requires='>=3.10',
    classifiers=[
        'Framework :: Django',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Apache Software License',
    ],
)
