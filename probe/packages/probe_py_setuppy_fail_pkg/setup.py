from setuptools import find_packages, setup

package_name = 'probe_py_setuppy_fail_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    test_suite='test',
    zip_safe=True,
    maintainer='Ewan Stewart',
    maintainer_email='estewart@launchpad.build',
    description='Throwaway package used to probe linter exclusion',
    license='Apache-2.0',

)
