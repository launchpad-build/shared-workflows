cmake_minimum_required(VERSION 3.8)
project(probe_pass_pkg)

find_package(ament_cmake REQUIRED)

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(${PROJECT_NAME}_test test/test_probe.cpp)
endif()

ament_package()
