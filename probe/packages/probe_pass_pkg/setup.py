from setuptools import setup

package_name = "probe_pass_pkg"

setup(
    name=package_name,
    version="0.0.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Ewan Stewart",
    maintainer_email="estewart@launchpad.build",
    description="Throwaway probe package",
    license="Apache-2.0",
)
