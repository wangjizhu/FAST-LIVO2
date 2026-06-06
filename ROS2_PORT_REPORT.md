# FAST-LIVO2 ROS1 → ROS2 移植报告（`dashuai` 分支）

> 由 Claude Opus 4.8 完成。本报告记录将 FAST-LIVO2 从 **ROS1 (catkin)** 移植到
> **ROS2 (ament_cmake / rclcpp)** 的完整过程、设计决策、验证结果与注意事项。

---

## 1. 任务与范围

- **目标**：把原 ROS1 工程就地改造为 ROS2 兼容（目标发行版：**Humble**，兼容 Foxy）。
- **解释**：`改成 ROS2 兼容` 理解为**就地移植到 ROS2**（替换 ROS1 API），原 ROS1 版本保留在 `main` 分支，本移植在 `dashuai` 分支。
- **改动规模**：31 个文件，约 +1187 / -1455 行；覆盖原工程 13 个含 ROS API 的文件中全部 317 处 ROS1 调用点。
- **构建验证状态**：本机为 **Windows、无 ROS2 环境**，无法编译。移植正确性通过 **静态核对 + 4 路并行对抗式审查（multi-agent review）** 完成，发现的问题已修复（见 §5）。请在 ROS2 工作区用 `colcon build` 做最终编译验证。

---

## 2. 按类别的改动

### 2.1 构建系统
- `package.xml`：format 1 → **format 3**，`catkin` → `ament_cmake`；依赖改为
  `rclcpp, builtin_interfaces, std_msgs, sensor_msgs, geometry_msgs, nav_msgs,
  visualization_msgs, tf2, tf2_ros, tf2_geometry_msgs, tf2_eigen,
  pcl_conversions, cv_bridge, image_transport, livox_ros_driver2, vikit_common`。
  删除 `message_generation/runtime`（本包无自定义消息）、`eigen_conversions`（→ `tf2_eigen`）、`rospy`。
- `CMakeLists.txt`：`catkin_package` → `ament_target_dependencies` + `ament_package()`；
  保留原有架构优化标志（x86 / ARM）、`MP_PROC_NUM`、OpenMP、mimalloc、`ROOT_DIR`；
  新增 `install(TARGETS ... RUNTIME DESTINATION lib/${PROJECT_NAME})` 与 `install(DIRECTORY launch config rviz_cfg ...)`。

### 2.2 节点模型
- `LIVMapper` 现 **继承 `rclcpp::Node`**（节点名 `laserMapping`），构造函数 `LIVMapper(const rclcpp::NodeOptions&)`。
- `main.cpp`：`ros::init/NodeHandle` → `rclcpp::init` + `std::make_shared<LIVMapper>()` + `mapper->run()` + `rclcpp::shutdown()`。
- 主循环 `run()`：`ros::ok()/ros::spinOnce()/ros::Rate` → `rclcpp::ok()/rclcpp::spin_some(get_node_base_interface())/rclcpp::Rate`。

### 2.3 发布/订阅/定时器
- `nh.advertise<T>` → `create_publisher<T>`（成员类型 `rclcpp::Publisher<T>::SharedPtr`，发布用 `->publish`）。
- `nh.subscribe` → `create_subscription<T>(topic, qos, std::bind(...))`；雷达订阅按类型在
  `livox_ros_driver2::msg::CustomMsg` 与 `sensor_msgs::msg::PointCloud2` 间二选一，存入 `rclcpp::SubscriptionBase::SharedPtr`。
- `nh.createTimer(ros::Duration(0.004), ...)` → `create_wall_timer(4ms, ...)`，回调签名去掉 `ros::TimerEvent`。
- 图像发布：`image_transport::ImageTransport::advertise` → `image_transport::create_publisher(this, "/rgb_img")`。

### 2.4 消息与智能指针
- 头文件 `sensor_msgs/Imu.h` 等 → `sensor_msgs/msg/imu.hpp` 等；类型 `sensor_msgs::Imu` → `sensor_msgs::msg::Imu`，
  `nav_msgs::Odometry/Path`、`geometry_msgs::*`、`visualization_msgs::*` 同理。
- 回调参数 `::ConstPtr` → `::ConstSharedPtr`；`MeasureGroup::imu` 等容器元素类型同步更新。
- **Livox**：`livox_ros_driver::CustomMsg` → `livox_ros_driver2::msg::CustomMsg`（字段名 `timebase/point_num/lidar_id/points[].{offset_time,x,y,z,reflectivity,tag,line}` 不变）；删除内置的 ROS1 生成头 `include/livox_ros_driver/`。

### 2.5 时间
- 新增辅助函数（`LIVMapper.cpp` / `IMU_Processing.cpp`）：
  - `toSec(builtin_interfaces::msg::Time) = rclcpp::Time(t).seconds()`
  - `toRosTime(double) → builtin_interfaces::msg::Time`（按 `floor(sec)+nsec` 分解，保持与 ROS1 `fromSec` 同精度）。
- 所有 `stamp.toSec()` / `ros::Time().fromSec()` / `ros::Time::now()` 分别替换为 `toSec(...)` / `toRosTime(...)` / `this->now()`。

### 2.6 TF
- `tf::TransformBroadcaster` → 成员 `std::shared_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster_`（`make_shared<...>(*this)`），
  发送 `geometry_msgs::msg::TransformStamped`。
- `tf::createQuaternionMsgFromRollPitchYaw` → `tf2::Quaternion::setRPY` + `tf2::toMsg`（`LIVMapper.cpp`、`voxel_map.cpp` 各一处）。

### 2.7 参数
- `nh.param<T>("a/b", var, def)` → `var = this->declare_parameter<T>("a.b", def)`；**参数名分隔符 `/` → `.`**。
- `loadVoxelConfig(ros::NodeHandle&)` → `loadVoxelConfig(rclcpp::Node*)`，`LIVMapper` 以 `this` 调用。
- `vector<int>` 不是合法的 ROS2 参数类型：`lio.layer_init_num` 以 `vector<int64_t>` 读取后转换为 `vector<int>`。

### 2.8 相机加载（重要设计决策）
- 原 `vk::camera_loader::loadFromRosNs("laserMapping", cam)` 依赖 ROS1 全局参数服务器，ROS2 无此机制。
- 改为 **包内自带的相机构造**（`LIVMapper::initializeComponents`）：从节点参数读取
  `cam_model / cam_width / cam_height / scale / cam_fx/fy/cx/cy` 及畸变参数，直接构造
  `vk::PinholeCamera`（`cam_d0..d3`）或 `vk::EquidistantCamera`（`k1..k4`）。
  → 因此本分支**不再依赖 `vikit_ros`，仅依赖 `vikit_common`**。

### 2.9 日志
- `ROS_INFO/WARN/ERROR` → `RCLCPP_INFO/WARN/ERROR(get_logger(), ...)`；无节点上下文处用 `rclcpp::get_logger("ImuProcess")`。
- `ROS_ASSERT` → `assert()`（`<cassert>`）。

### 2.10 launch 与 config
- 4 个 `*.launch`（XML）→ `*.launch.py`（Python launch）：`rviz` → `rviz2`，主/相机 YAML 通过 `parameters=[...]` 传入，
  `image_transport republish` 用 ROS2 remap 形式（`in/compressed`、`out`）。
- 9 个 YAML 包裹为 `'/**: ros__parameters:'`，分组仍用点状嵌套（与 `declare_parameter("group.key")` 对应）。
- **修正 ROS2 严格类型**：声明为 `double` 的参数其 YAML 值必须带小数点 —
  `outlier_threshold`、`img_point_cov`、`sliding_thresh` 由整数改为 `*.0`；
  整数数组 `extrinsic_R: [1,0,...]` 改为 `[1.0,0.0,...]`（声明为 `vector<double>`）。

---

## 3. 文件改动一览（vs `main`）

| 类别 | 文件 |
|---|---|
| 构建 | `CMakeLists.txt`、`package.xml` |
| 入口/节点 | `src/main.cpp`、`include/LIVMapper.h`、`src/LIVMapper.cpp` |
| 头文件 | `common_lib.h`、`preprocess.h`、`IMU_Processing.h`、`voxel_map.h`（`vio.h`/`feature.h`/`frame.h`/`visual_point.h` 无需改） |
| 源文件 | `preprocess.cpp`、`IMU_Processing.cpp`、`voxel_map.cpp`（`vio.cpp`/`frame.cpp`/`visual_point.cpp` 仅含注释级 ROS，无需改） |
| 删除 | `include/livox_ros_driver/CustomMsg.h`、`CustomPoint.h`、4 个 `*.launch` |
| 新增 | 4 个 `*.launch.py` |
| 配置 | 9 个 `config/*.yaml` |

---

## 4. 关键设计决策汇总

1. **`LIVMapper` 继承 `rclcpp::Node`**：最贴近 ROS2 习惯，`this` 即节点，参数/发布/订阅/时钟统一从 `this` 取。
2. **单线程执行模型保留**：`run()` 内 `spin_some` + `Rate`，与原 ROS1 `spinOnce` 主循环语义一致；250 Hz IMU 传播定时器在 `spin_some` 中触发。
3. **相机加载自带化**：避免绑定某个特定 ROS2 vikit fork 的 `camera_loader` API（见 §6 假设）。
4. **参数文件用 `/**` 通配**：与节点名解耦，重映射后仍生效。

---

## 5. 对抗式审查发现的问题与修复

用 4 路并行子代理分别审查「节点 API / 消息与时间 / voxel+tf / 构建+launch+config」，共 5 条发现：

| 级别 | 位置 | 问题 | 处理 |
|---|---|---|---|
| **Blocker** | `IMU_Processing.cpp:553` | `ROS_ASSERT` 是 ROS1 宏，rclcpp 无此宏，**无法编译** | 改为 `assert()`（加 `<cassert>`）✅ 已修复 |
| **Major** | `IMU_Processing.h:22` | `time_list()` 在头文件中以外部链接定义，静态链接时 `imu_proc` 与 `laser_mapping` 同时链入会**重复定义** | 加 `inline` ✅ 已修复 |
| Minor | `config/avia.yaml`、`HILTI22.yaml` | `imu.b_acc_cov / b_gyr_cov` 在 YAML 中但 C++ 从未声明（偏置协方差为硬编码） | **原 ROS1 即如此**，非本次回归；ROS2 中未声明参数被静默忽略，无害，保留并在此说明 |
| Minor | `src/LIVMapper.cpp` | `grid_n_width` 未经参数初始化即赋给 `vio_manager` | **原 ROS1 即如此**；`initializeVIO()` 会用 `width/grid_size` 重新计算并覆盖，无实际影响，保留 |

> 结论：2 个真实问题（1 阻断 + 1 链接）已修复；3 个 minor 均为**原工程既有行为**，非移植引入，保留以维持原语义。

---

## 6. 使用者需提供 / 需注意的假设与事项

1. **`vikit_common` 的 ROS2(ament) 版本**：本包深度使用其相机与数学库（`vk::AbstractCamera/PinholeCamera/EquidistantCamera`、`vikit/math_utils.h` 等）。需在同一工作区构建可被 `ament_target_dependencies(vikit_common)` 找到的版本。
2. **相机构造函数签名假设**：移植假定
   `vk::PinholeCamera(width,height,scale,fx,fy,cx,cy,d0,d1,d2,d3)`、
   `vk::EquidistantCamera(width,height,scale,fx,fy,cx,cy,k1,k2,k3,k4)`（与 `cam->scale()` 的存在一致）。
   若你的 fork 签名不同，请改 `src/LIVMapper.cpp` 的 `initializeComponents` 相机构造块（仅此一处）。
3. **`livox_ros_driver2`**：需先构建并 source，提供 `livox_ros_driver2/msg/CustomMsg`。
4. **`cv_bridge` 头文件**：本移植用 `cv_bridge/cv_bridge.h`（Humble）。若用更新发行版（Iron/Jazzy）需改为 `cv_bridge/cv_bridge.hpp`。
5. **QoS**：订阅沿用原工程的大队列深度 `KeepLast(200000)`（RELIABLE）。如与驱动 QoS 不匹配或资源吃紧，可调小或改 `SensorDataQoS()`（见 `initializeSubscribersAndPublishers`）。
6. **RViz**：`rviz_cfg/*.rviz` 仍为 RViz1 配置，RViz2 可能无法直接加载，必要时在 RViz2 中重存一份。
7. **Release 与 `assert`**：colcon Release 默认定义 `NDEBUG`，§5 改用的 `assert` 会被编译掉；若需保留运行期空指针检查可改为显式 `if(...) return;`。
8. **rosbag**：ROS2 用 `ros2 bag`（sqlite3/mcap）。原 ROS1 `.bag` 需用 `rosbags-convert` 转换或经 `ros1_bridge` 回放。

---

## 7. 构建与运行

```bash
# 1) 准备工作区（同一 src 下需有 vikit_common、livox_ros_driver2 的 ROS2 版本）
cd ~/ros2_ws/src
git clone -b dashuai https://github.com/wangjizhu/FAST-LIVO2

# 2) 构建
cd ~/ros2_ws
colcon build --symlink-install
source install/setup.bash

# 3) 运行（以 AVIA 为例）
ros2 launch fast_livo mapping_avia.launch.py
ros2 bag play YOUR_DOWNLOADED_BAG
```

---

## 8. 提交记录（`dashuai`）

```
b26cce7  [ROS2] start ROS1->ROS2 port branch          (连通性验证)
76baabe  [ROS2] add branch banner to README + ament package.xml
fe80039  [ROS2] port build system + all headers to ament/rclcpp
8d6a3a5  [ROS2] port all source files to rclcpp
0f0873c  [ROS2] convert launch files to launch.py and config to ROS2 params
d96b77e  [ROS2] update README for ROS2 + add builtin_interfaces dep
2b0c4ba  [ROS2] fix issues found in adversarial verification
```
（外加本报告一次提交。）
