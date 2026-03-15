cmake_minimum_required(VERSION 3.8)
project(eod_mesh_manager)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(moveit_ros_planning_interface REQUIRED)
find_package(geometric_shapes REQUIRED)
find_package(shape_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)

add_executable(mesh_manager_node src/mesh_manager_node.cpp)
ament_target_dependencies(mesh_manager_node
  rclcpp
  moveit_ros_planning_interface
  geometric_shapes
  shape_msgs
  geometry_msgs
)

install(TARGETS
  mesh_manager_node
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
