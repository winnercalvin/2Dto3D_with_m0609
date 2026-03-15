#include <rclcpp/rclcpp.hpp>
#include <moveit/planning_scene_interface/planning_scene_interface.h>
#include <moveit_msgs/msg/collision_object.hpp>
#include <geometric_shapes/shapes.h>
#include <geometric_shapes/mesh_operations.h>
#include <geometric_shapes/shape_operations.h>
#include <shape_msgs/msg/mesh.hpp>

// 🔥 boost::variant에서 값을 꺼내기 위한 헤더 추가
#include <boost/variant/get.hpp> 

class MeshObjectManager : public rclcpp::Node
{
public:
    MeshObjectManager() : Node("mesh_object_manager")
    {
        object_id_ = "extracted_target_mesh";
        frame_id_ = "base_link"; // 로봇 기준 좌표계

        // 지정해주신 절대 경로
        std::string obj_file_path = "/home/rokey/robot_share/extracted_mesh_1773598262169.obj";

        add_mesh_to_scene(obj_file_path);
    }

private:
    void add_mesh_to_scene(const std::string& file_path)
    {
        moveit_msgs::msg::CollisionObject collision_object;
        collision_object.id = object_id_;
        collision_object.header.frame_id = frame_id_;

        std::string file_uri = "file://" + file_path;
        RCLCPP_INFO(this->get_logger(), "불러올 메쉬 경로: %s", file_uri.c_str());

        Eigen::Vector3d scale(1.0, 1.0, 1.0); 
        shapes::Mesh* m = shapes::createMeshFromResource(file_uri, scale);
        
        if (m == nullptr) {
            RCLCPP_ERROR(this->get_logger(), "❌ 메쉬 파일을 불러오는데 실패했습니다.");
            return;
        }

        shape_msgs::msg::Mesh mesh_msg;
        shapes::ShapeMsg shape_msg;
        shapes::constructMsgFromShape(m, shape_msg);
        
        // 🔥 std::get 대신 boost::get 사용!
        mesh_msg = boost::get<shape_msgs::msg::Mesh>(shape_msg); 
        
        delete m; 

        collision_object.meshes.push_back(mesh_msg);

        geometry_msgs::msg::Pose pose;
        pose.position.x = -3.0;
        pose.position.y = -3.3;
        pose.position.z = 0.1;
        pose.orientation.w = 1.0;
        collision_object.mesh_poses.push_back(pose);

        collision_object.operation = collision_object.ADD;

        planning_scene_interface_.applyCollisionObject(collision_object);
        RCLCPP_INFO(this->get_logger(), "✅ 성공적으로 메쉬를 MoveIt 씬에 추가했습니다!");
    }

    moveit::planning_interface::PlanningSceneInterface planning_scene_interface_;
    std::string object_id_;
    std::string frame_id_;
};

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<MeshObjectManager>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
