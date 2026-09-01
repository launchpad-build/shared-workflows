cmake_minimum_required(VERSION 3.8)
project(probe_ctest_nocase_pkg)

find_package(ament_cmake REQUIRED)

if(BUILD_TESTING)
  add_test(NAME no_result_file COMMAND ${CMAKE_COMMAND} -E false)
endif()

ament_package()
